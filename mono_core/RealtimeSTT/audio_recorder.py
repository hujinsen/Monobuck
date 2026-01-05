"""

AudioToTextRecorder 类用于实现快速的语音转文字功能。

该类使用 SenseVoice 相关模型对录制的音频进行转写，可以在 GPU 或 CPU 上运行。
内置语音活动检测（VAD），能够根据是否存在语音自动开始或停止录音。
同时集成了通过 pvporcupine / OpenWakeWord 等库实现的唤醒词检测，可以在检测到
特定唤醒词后自动触发录音。系统支持实时反馈，并且可以根据需求进行二次开发和定制。

主要特性：
- 语音活动检测：在检测到语音开始/结束时自动开始或停止录音；
- 唤醒词检测：在检测到指定唤醒词（可配置多个）时触发录音；
- 事件回调：可在录音开始、结束、转写开始等时机挂接自定义回调；
- 快速转写：尽可能以较低延迟返回音频对应的文本结果。

作者: Kolja Beigel

"""

from funasr_onnx import SenseVoiceSmall
from funasr_onnx.utils.postprocess_utils import rich_transcription_postprocess
from silero_vad import load_silero_vad
from typing import Iterable, List, Optional, Union
from openwakeword.model import Model
import torch.multiprocessing as mp
from scipy.signal import resample
from ctypes import c_bool
from scipy import signal
import soundfile as sf
import openwakeword
import collections
import numpy as np
import pvporcupine
import traceback
import threading
import webrtcvad
import datetime
import platform
import logging
import struct
import base64
import queue
import torch
import halo
import time
import copy
import os
import re
import gc
import psutil

try:  # 在作为 RealtimeSTT 包使用时，优先采用包内相对导入
    from .state_machine import RecorderState, StateCallbacks, transition_state
    from .utils import check_parent_process
    from .vad import VadConfig, silero_is_speech, webrtc_is_speech
    from .wakeword import IWakeWordDetector, PorcupineWakeWordDetector, OpenWakeWordDetector
    from .transcriber_client import SenseVoiceTranscriber
except ImportError:  # 当在 RealtimeSTT/ 目录下以脚本运行时使用本地导入作为回退方案
    from state_machine import RecorderState, StateCallbacks, transition_state
    from utils import check_parent_process
    from vad import VadConfig, silero_is_speech, webrtc_is_speech
    from wakeword import IWakeWordDetector, PorcupineWakeWordDetector, OpenWakeWordDetector
    from transcriber_client import SenseVoiceTranscriber

# 设置 OpenMP 运行时在重复加载库时不报错（仅建议在开发环境中使用）
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

INIT_SILERO_SENSITIVITY = 0.4
INIT_WEBRTC_SENSITIVITY = 3
INIT_POST_SPEECH_SILENCE_DURATION = 0.6
INIT_MIN_LENGTH_OF_RECORDING = 0.5
INIT_MIN_GAP_BETWEEN_RECORDINGS = 0
INIT_WAKE_WORDS_SENSITIVITY = 0.6
INIT_PRE_RECORDING_BUFFER_DURATION = 1.0
INIT_WAKE_WORD_ACTIVATION_DELAY = 0.0
INIT_WAKE_WORD_TIMEOUT = 5.0
INIT_WAKE_WORD_BUFFER_DURATION = 0.1
ALLOWED_LATENCY_LIMIT = 100

TIME_SLEEP = 0.02
SAMPLE_RATE = 16000
BUFFER_SIZE = 512
INT16_MAX_ABS_VALUE = 32768.0

INIT_HANDLE_BUFFER_OVERFLOW = False
if platform.system() != 'Darwin':
    INIT_HANDLE_BUFFER_OVERFLOW = True


class bcolors:
    OKGREEN = '\033[92m'  # 绿色：用于表示检测到语音
    WARNING = '\033[93m'  # 黄色：用于表示检测到静音
    ENDC = '\033[0m'      # 重置为终端默认颜色


class AudioToTextRecorder:
    """
    负责从麦克风采集音频、检测语音活动，并使用 `sensevoice_small` 模型
    对捕获到的音频进行转写的核心类。
    """

    def __init__(self,
                 model_path: str = "",
                 language: str = "auto",
                 input_device_index: int = None,
                 on_recording_start=None,
                 on_recording_stop=None,
                 on_transcription_start=None,
                 ensure_sentence_starting_uppercase=True,
                 ensure_sentence_ends_with_period=True,
                 use_microphone=True,
                 spinner=True,
                 level=logging.WARNING,

                 # Voice activation parameters
                 silero_sensitivity: float = INIT_SILERO_SENSITIVITY,
                 silero_use_onnx: bool = False,
                 silero_deactivity_detection: bool = False,
                 webrtc_sensitivity: int = INIT_WEBRTC_SENSITIVITY,
                 post_speech_silence_duration: float = (
                     INIT_POST_SPEECH_SILENCE_DURATION
                 ),
                 min_length_of_recording: float = (
                     INIT_MIN_LENGTH_OF_RECORDING
                 ),
                 min_gap_between_recordings: float = (
                     INIT_MIN_GAP_BETWEEN_RECORDINGS
                 ),
                 pre_recording_buffer_duration: float = (
                     INIT_PRE_RECORDING_BUFFER_DURATION
                 ),
                 on_vad_detect_start=None,
                 on_vad_detect_stop=None,

                 # Wake word parameters
                 wakeword_backend: str = "pvporcupine",
                 openwakeword_model_paths: str = None,
                 openwakeword_inference_framework: str = "onnx",
                 wake_words: str = "",
                 wake_words_sensitivity: float = INIT_WAKE_WORDS_SENSITIVITY,
                 wake_word_activation_delay: float = (
                    INIT_WAKE_WORD_ACTIVATION_DELAY
                 ),
                 wake_word_timeout: float = INIT_WAKE_WORD_TIMEOUT,
                 wake_word_buffer_duration: float = INIT_WAKE_WORD_BUFFER_DURATION,
                 on_wakeword_detected=None,
                 on_wakeword_timeout=None,
                 on_wakeword_detection_start=None,
                 on_wakeword_detection_end=None,
                 on_recorded_chunk=None,
                 handle_buffer_overflow: bool = INIT_HANDLE_BUFFER_OVERFLOW,
                 buffer_size: int = BUFFER_SIZE,
                 sample_rate: int = SAMPLE_RATE,
                 print_transcription_time: bool = False,
                 early_transcription_on_silence: int = 0,
                 allowed_latency_limit: int = ALLOWED_LATENCY_LIMIT,
                 no_log_file: bool = True,
                 ):
        """
        初始化音频录制器、转写引擎以及唤醒词检测相关组件。

        参数说明：
        - model_path (str): SenseVoice 模型目录路径，需为已下载好的 ONNX 模型；
        - language (str, 默认 "auto"): 语音识别语言代码，不指定时由模型自动判断；
        - input_device_index (int, 默认 0): 要使用的音频输入设备索引；
        - on_recording_start (callable): 录音开始时触发的回调；
        - on_recording_stop (callable): 录音结束时触发的回调；
        - on_transcription_start (callable): 开始进行语音转文字时触发的回调；
        - ensure_sentence_starting_uppercase (bool): 是否保证句首字母大写；
        - ensure_sentence_ends_with_period (bool): 是否在结尾缺少标点时自动补“.”；
        - use_microphone (bool): 是否使用麦克风作为输入源；为 False 时使用 feed_audio 传入的音频；
        - spinner (bool): 是否在终端显示状态旋转指示器；
        - level (int): 日志等级；
        - silero_sensitivity (float): Silero VAD 的敏感度，范围 0～1；
        - silero_use_onnx (bool): 是否使用 ONNX 版本的 Silero 模型；
        - silero_deactivity_detection (bool): 是否使用 Silero 检测语音结束，相比 WebRTC 对噪声更鲁棒；
        - webrtc_sensitivity (int): WebRTC VAD 的模式（0 最敏感，3 最保守）；
        - post_speech_silence_duration (float): 检测到语音结束后需持续静音的秒数，超过则认为录音结束；
        - min_gap_between_recordings (float): 连续两段录音之间的最小时间间隔；
        - min_length_of_recording (float): 每段录音的最短时长，避免录到过短的片段；
        - pre_recording_buffer_duration (float): 录音前置缓冲时长，用于补偿 VAD 延迟；
        - on_vad_detect_start (callable): 开始监听语音活动时的回调；
        - on_vad_detect_stop (callable): 停止监听语音活动时的回调；
        - wakeword_backend (str): 唤醒词检测后端，支持 "pvporcupine" 或 "oww/openwakeword"；
        - openwakeword_model_paths (str): OpenWakeWord 模型文件路径，逗号分隔；
        - openwakeword_inference_framework (str): OpenWakeWord 推理框架，"onnx" 或 "tflite"；
        - wake_words (str): 使用 pvporcupine 时的唤醒词列表，逗号分隔；
        - wake_words_sensitivity (float): 唤醒词检测敏感度，0～1；
        - wake_word_activation_delay (float): 进入监听后，延迟多少秒再启用唤醒词模式；0 表示立即启用；
        - wake_word_timeout (float): 检测到唤醒词后，如果在该时间内未说话则回到非激活状态；
        - wake_word_buffer_duration (float): 检测唤醒词时额外缓冲的音频时长，用于从最终录音里裁掉唤醒词；
        - on_wakeword_detected (callable): 检测到唤醒词时的回调；
        - on_wakeword_timeout (callable): 唤醒后超时未检测到语音时的回调；
        - on_wakeword_detection_start (callable): 开始监听唤醒词时的回调；
        - on_wakeword_detection_end (callable): 停止监听唤醒词时的回调（如超时或已检测到唤醒词）；
        - on_recorded_chunk (callable): 每录到一块音频数据时调用的回调；
        - handle_buffer_overflow (bool): 是否在输入缓冲溢出时记录警告并丢弃多余数据；
        - buffer_size (int): 音频录制缓冲区大小，随意修改可能导致功能异常；
        - sample_rate (int): 音频采样率，WebRTC VAD 对采样率非常敏感，一般保持 16000；
        - print_transcription_time (bool): 是否打印主模型转写耗时；
        - early_transcription_on_silence (int): 当静音达到指定毫秒数时提前转写，加快最终返回速度；
        - allowed_latency_limit (int): 队列中允许未处理音频块的最大数量，超出会丢弃旧数据；
        - no_log_file (bool): 是否跳过写入调试日志文件，只输出到控制台。

        异常：
            Exception: 初始化转写模型、唤醒词检测或音频录制失败时抛出。
        """

        self.language = language
        self.input_device_index = input_device_index
        self.wake_words = wake_words
        self.wake_word_activation_delay = wake_word_activation_delay
        self.wake_word_timeout = wake_word_timeout
        self.wake_word_buffer_duration = wake_word_buffer_duration
        self.ensure_sentence_starting_uppercase = (
            ensure_sentence_starting_uppercase
        )
        self.ensure_sentence_ends_with_period = (
            ensure_sentence_ends_with_period
        )
        self.use_microphone = mp.Value(c_bool, use_microphone)
        self.min_gap_between_recordings = min_gap_between_recordings
        self.min_length_of_recording = min_length_of_recording
        self.pre_recording_buffer_duration = pre_recording_buffer_duration
        self.post_speech_silence_duration = post_speech_silence_duration
        self.on_recording_start = on_recording_start
        self.on_recording_stop = on_recording_stop
        self.on_wakeword_detected = on_wakeword_detected
        self.on_wakeword_timeout = on_wakeword_timeout
        self.on_vad_detect_start = on_vad_detect_start
        self.on_vad_detect_stop = on_vad_detect_stop
        self.on_wakeword_detection_start = on_wakeword_detection_start
        self.on_wakeword_detection_end = on_wakeword_detection_end
        self.on_recorded_chunk = on_recorded_chunk
        self.on_transcription_start = on_transcription_start
        self.model_path = model_path

        self.handle_buffer_overflow = handle_buffer_overflow
        self.allowed_latency_limit = allowed_latency_limit

        self.level = level
        self.audio_queue = mp.Queue()
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self.recording_start_time = 0
        self.recording_stop_time = 0
        self.last_recording_start_time = 0
        self.last_recording_stop_time = 0
        self.wake_word_detect_time = 0
        self.silero_check_time = 0
        self.silero_working = False
        self.speech_end_silence_start = 0
        self.silero_sensitivity = silero_sensitivity
        self.silero_deactivity_detection = silero_deactivity_detection
        self.listen_start = 0
        self.spinner = spinner
        self.halo = None
        self.state = RecorderState.INACTIVE.value
        self.wakeword_detected = False
        self.text_storage = []
        self.is_webrtc_speech_active = False
        self.is_silero_speech_active = False
        # 唤醒词检测器实例（根据配置选择具体实现）
        self.wakeword_detector: Optional[IWakeWordDetector] = None
        self.recording_thread = None
        self.audio_interface = None
        self.audio = None
        self.stream = None
        self.start_recording_event = threading.Event()
        self.stop_recording_event = threading.Event()
        self.backdate_stop_seconds = 0.0
        self.backdate_resume_seconds = 0.0
        self.last_transcription_bytes = None
        self.last_transcription_bytes_b64 = None
        self.use_wake_words = wake_words or wakeword_backend in {'oww', 'openwakeword', 'openwakewords'}
        self.transcription_lock = threading.Lock()
        self.shutdown_lock = threading.Lock()
        self.transcribe_count = 0
        self.print_transcription_time = print_transcription_time
        self.early_transcription_on_silence = early_transcription_on_silence

        # 使用指定的日志级别初始化日志配置
        log_format = 'RealTimeSTT: %(name)s - %(levelname)s - %(message)s'

        # 文件日志格式中加入毫秒时间戳
        file_log_format = '%(asctime)s.%(msecs)03d - ' + log_format

        # 获取根 logger
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)  # Set the root logger's level to DEBUG

        # 移除已有的 handler，避免重复输出
        logger.handlers = []

        # 创建控制台输出 handler 并设置日志级别
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level) 
        console_handler.setFormatter(logging.Formatter(log_format))

        # 将 handler 添加到 logger
        if not no_log_file:
            # 创建文件日志 handler 并设置级别
            file_handler = logging.FileHandler('realtimestt.log')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(
                file_log_format,
                datefmt='%Y-%m-%d %H:%M:%S'
            ))

            logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        self.is_shut_down = False
        self.shutdown_event = mp.Event()
        
        try:
            # 仅在尚未设置多进程启动方式时设置
            if mp.get_start_method(allow_none=True) is None:
                mp.set_start_method("spawn")
        except RuntimeError as e:
            logging.info(f"Start method has already been set. Details: {e}")

        logging.info("Starting RealTimeSTT")

        self.interrupt_stop_event = mp.Event()
        self.was_interrupted = mp.Event()

        # 转写客户端封装：负责与 SenseVoice 子进程通信
        self.transcriber = SenseVoiceTranscriber(
            model_path=self.model_path,
            shutdown_event=self.shutdown_event,
            interrupt_stop_event=self.interrupt_stop_event,
        )

        # 兼容原有字段命名，便于复用现有逻辑
        self.parent_transcription_pipe = self.transcriber.parent_pipe
        self.parent_stdout_pipe = self.transcriber.stdout_pipe

        # 启动音频数据读取进程/线程
        if self.use_microphone.value:
            logging.info("Initializing audio recording"
                         " (creating pyAudio input stream,"
                         f" sample rate: {self.sample_rate}"
                         f" buffer size: {self.buffer_size}"
                         )
            self.reader_process = self._start_thread(
                target=AudioToTextRecorder._audio_data_worker,
                args=(
                    self.audio_queue,
                    self.sample_rate,
                    self.buffer_size,
                    self.input_device_index,
                    self.shutdown_event,
                    self.interrupt_stop_event,
                    self.use_microphone
                )
            )

        # 初始化唤醒词检测
        if wake_words or wakeword_backend in {'oww', 'openwakeword', 'openwakewords'}:
            self.wakeword_backend = wakeword_backend

            self.wake_words_list = [
                word.strip() for word in wake_words.lower().split(',')
            ]
            self.wake_words_sensitivity = wake_words_sensitivity
            self.wake_words_sensitivities = [
                float(wake_words_sensitivity)
                for _ in range(len(self.wake_words_list))
            ]

            if self.wakeword_backend in {'pvp', 'pvporcupine'}:

                try:
                    # 使用面向对象封装的 Porcupine 检测器实现具体逻辑
                    self.wakeword_detector = PorcupineWakeWordDetector(
                        keywords=self.wake_words_list,
                        sensitivities=self.wake_words_sensitivities,
                    )
                    # 与原逻辑保持一致：更新缓冲区大小和采样率
                    self.buffer_size = self.wakeword_detector.frame_length
                    self.sample_rate = self.wakeword_detector.sample_rate

                except Exception as e:
                    logging.exception(
                        "初始化 Porcupine 唤醒词引擎失败: %s", e
                    )
                    raise

                logging.debug(
                    "Porcupine 唤醒词检测引擎初始化成功"
                )

            elif self.wakeword_backend in {'oww', 'openwakeword', 'openwakewords'}:

                try:
                    model_paths = (
                        openwakeword_model_paths.split(',')
                        if openwakeword_model_paths else None
                    )
                    # 使用面向对象封装的 OpenWakeWord 检测器实现具体逻辑
                    self.wakeword_detector = OpenWakeWordDetector(
                        model_paths=model_paths,
                        framework=openwakeword_inference_framework,
                        sensitivity=wake_words_sensitivity,
                    )
                    if model_paths:
                        logging.info(
                            "成功加载唤醒词模型: %s", openwakeword_model_paths
                        )
                    else:
                        logging.info("使用 OpenWakeWord 默认模型集")

                except Exception as e:
                    logging.exception(
                        "初始化 OpenWakeWord 唤醒词引擎失败: %s", e
                    )
                    raise

                logging.debug(
                    "OpenWakeWord 唤醒词检测引擎初始化成功"
                )

            else:
                logging.exception(
                    "Wakeword 引擎 %s 未知或不支持，请使用 pvporcupine 或 openwakeword.",
                    self.wakeword_backend,
                )


        # 初始化 WebRTC 语音活动检测模型
        try:
            logging.info("Initializing WebRTC voice with "
                         f"Sensitivity {webrtc_sensitivity}"
                         )
            self.webrtc_vad_model = webrtcvad.Vad()
            self.webrtc_vad_model.set_mode(webrtc_sensitivity)

        except Exception as e:
            logging.exception("Error initializing WebRTC voice "
                              f"activity detection engine: {e}"
                              )
            raise

        logging.debug("WebRTC VAD voice activity detection "
                      "engine initialized successfully"
                      )

        # 初始化 Silero VAD 语音活动检测模型
        try:
            self.silero_vad_model = load_silero_vad(onnx=True)

        except Exception as e:
            logging.exception(f"Error initializing Silero VAD "
                              f"voice activity detection engine: {e}"
                              )
            raise

        logging.debug("Silero VAD voice activity detection "
                      "engine initialized successfully"
                      )

        self.audio_buffer = collections.deque(
            maxlen=int((self.sample_rate // self.buffer_size) *
                       self.pre_recording_buffer_duration)
        )
        self.last_words_buffer = collections.deque(
            maxlen=int((self.sample_rate // self.buffer_size) *
                       0.3)
        )
        self.frames = []
        self.last_frames = []

        # 录音控制标志位
        self.is_recording = False
        self.is_running = True
        self.start_recording_on_voice_activity = False
        self.stop_recording_on_voice_deactivity = False

        # 启动录音工作线程
        self.recording_thread = threading.Thread(target=self._recording_worker)
        self.recording_thread.daemon = True
        self.recording_thread.start()
                   
        self.stdout_thread = threading.Thread(target=self._read_stdout)
        self.stdout_thread.daemon = True
        self.stdout_thread.start()

        logging.debug('RealtimeSTT initialization completed successfully')
                   
    def _start_thread(self, target=None, args=()):
        """
                在整个库中实现统一的线程/进程启动方式。

                该方法用于启动库内部的所有“工作单元”：
                - 在 Linux 上使用标准的 threading.Thread；
                - 在其他平台上使用 PyTorch 的多进程 Process。

                参数：
                        target (callable): 在线程/进程中实际执行的目标函数；
                        args (tuple): 传递给目标函数的参数元组。
        """
        if (platform.system() == 'Linux'):
            thread = threading.Thread(target=target, args=args)
            thread.deamon = True
            thread.start()
            return thread
        else:
            thread = mp.Process(target=target, args=args, daemon=True)
            thread.start()
            return thread

    def _read_stdout(self):
        while not self.shutdown_event.is_set():
            check_parent_process(self.shutdown_event)

            try:
                if self.parent_stdout_pipe.poll(0.1):
                    logging.debug("Receive from stdout pipe")
                    message = self.parent_stdout_pipe.recv()
                    logging.info(message)
            except (BrokenPipeError, EOFError, OSError):
                # 管道可能已经关闭，这里忽略错误
                pass
            except KeyboardInterrupt:  # 处理手动中断（Ctrl+C）
                logging.info("KeyboardInterrupt in read from stdout detected, exiting...")
                break
            except Exception as e:
                logging.error(f"Unexpected error in read from stdout: {e}", exc_info=True)
                logging.error(traceback.format_exc())  # Log the full traceback here
                break 
            time.sleep(0.1)

    @staticmethod
    def _audio_data_worker(audio_queue,
                        target_sample_rate,
                        buffer_size,
                        input_device_index,
                        shutdown_event,
                        interrupt_stop_event,
                        use_microphone):
        """
        这是一个后台音频采集工作线程（运行在独立线程中），负责从麦克风实时采集音频数据，并进行预处理后放入队列，
        供后续的语音识别模块（如 Silero VAD + SenseVoice）使用。

        该方法是音频录制流程的核心，主要职责包括：

        ✅ 初始化音频输入流（使用 PyAudio），以最高支持采样率采集原始音频；
        ✅ 持续读取音频数据块，按需进行重采样（调整到目标采样率）；
        ✅ 对音频数据进行预处理（如归一化、裁剪）；
        ✅ 将完整音频块放入 audio_queue，供下游模型消费；
        ✅ 捕获并记录录音过程中发生的任何错误；
        ✅ 响应 shutdown_event 或 interrupt_stop_event，优雅退出，避免资源泄漏。
        
        录音流程的工作方法。

        该方法在独立的进程/线程中运行，主要负责：
        - 以尽可能高的采样率建立音频输入流；
        - 持续从输入流中读取音频，必要时重采样并做预处理；
        - 将处理好的完整音频块放入队列供后续模块消费；
        - 处理录音过程中的各种异常；
        - 检测 shutdown_event 被触发后，优雅地退出并释放资源。

        参数：
            audio_queue (queue.Queue): 存放录制音频块的队列；
            target_sample_rate (int): 目标采样率（用于 Silero VAD 等模块）；
            buffer_size (int): Silero VAD 期望的样本数；
            input_device_index (int): 音频输入设备索引；
            shutdown_event (threading.Event): 触发时通知该 worker 终止；
            interrupt_stop_event (threading.Event): 用于响应键盘中断；
            use_microphone (multiprocessing.Value): 是否启用麦克风输入的共享标志。

        异常：
            Exception: 初始化音频录制失败时抛出。
        """
        import pyaudio
        import numpy as np
        from scipy import signal
        
        if __name__ == '__main__':
            system_signal.signal(system_signal.SIGINT, system_signal.SIG_IGN)

        def get_highest_sample_rate(audio_interface, device_index):
            """获取指定设备支持的最高采样率。"""
            try:
                device_info = audio_interface.get_device_info_by_index(device_index)
                max_rate = int(device_info['defaultSampleRate'])
                
                if 'supportedSampleRates' in device_info:
                    supported_rates = [int(rate) for rate in device_info['supportedSampleRates']]
                    if supported_rates:
                        max_rate = max(supported_rates)
                
                return max_rate
            except Exception as e:
                logging.warning(f"Failed to get highest sample rate: {e}")
                return 48000  # 回退到常见的较高采样率 48000

        def initialize_audio_stream(audio_interface, sample_rate, chunk_size):
            nonlocal input_device_index

            def validate_device(device_index):
                """校验设备是否存在且可用于音频输入。"""
                try:
                    device_info = audio_interface.get_device_info_by_index(device_index)
                    if not device_info.get('maxInputChannels', 0) > 0:
                        return False

                    # 实际尝试从该设备读取数据
                    test_stream = audio_interface.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=target_sample_rate,
                        input=True,
                        frames_per_buffer=chunk_size,
                        input_device_index=device_index,
                        start=False  # Don't start the stream yet
                    )

                    # Start the stream and try to read from it
                    test_stream.start_stream()
                    test_data = test_stream.read(chunk_size, exception_on_overflow=False)
                    test_stream.stop_stream()
                    test_stream.close()

                    # 确认是否成功读取到有效数据
                    if len(test_data) == 0:
                        return False

                    return True

                except Exception as e:
                    logging.debug(f"Device validation failed: {e}")
                    return False

            """带错误处理地初始化音频输入流。"""
            while not shutdown_event.is_set():
                check_parent_process(shutdown_event)

                try:
                    # 首先获取所有可用的输入设备列表
                    input_devices = []
                    for i in range(audio_interface.get_device_count()):
                        try:
                            device_info = audio_interface.get_device_info_by_index(i)
                            if device_info.get('maxInputChannels', 0) > 0:
                                input_devices.append(i)
                        except Exception:
                            continue

                    if not input_devices:
                        raise Exception("No input devices found")

                    # 如果当前设备索引为空或不可用，则尝试寻找一个可用设备
                    if input_device_index is None or input_device_index not in input_devices:
                        # First try the default device
                        try:
                            default_device = audio_interface.get_default_input_device_info()
                            if validate_device(default_device['index']):
                                input_device_index = default_device['index']
                        except Exception:
                            # 若默认设备失效，则尝试其他可用输入设备
                            for device_index in input_devices:
                                if validate_device(device_index):
                                    input_device_index = device_index
                                    break
                            else:
                                raise Exception("No working input devices found")

                    # 最终再次校验选择的设备是否可用
                    if not validate_device(input_device_index):
                        raise Exception("Selected device validation failed")

                    # 能进入这里说明已找到并验证通过的设备
                    stream = audio_interface.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=sample_rate,
                        input=True,
                        frames_per_buffer=chunk_size,
                        input_device_index=input_device_index,
                    )

                    logging.info(f"Microphone connected and validated (input_device_index: {input_device_index})")
                    return stream

                except Exception as e:
                    logging.error(f"Microphone connection failed: {e}. Retrying...", exc_info=True)
                    input_device_index = None
                    time.sleep(3)  # Wait before retrying
                    continue

        def preprocess_audio(chunk, original_sample_rate, target_sample_rate):
            """对单个音频块做与 feed_audio 类似的预处理。"""
            if isinstance(chunk, np.ndarray):
                # 如有需要，将双声道转换为单声道
                if chunk.ndim == 2:
                    chunk = np.mean(chunk, axis=1)

                # 如有需要，重采样到目标采样率
                if original_sample_rate != target_sample_rate:
                    num_samples = int(len(chunk) * target_sample_rate / original_sample_rate)
                    chunk = signal.resample(chunk, num_samples)

                # 确保数据类型为 int16
                chunk = chunk.astype(np.int16)
            else:
                # 若输入为 bytes，则先转为 numpy 数组
                chunk = np.frombuffer(chunk, dtype=np.int16)

                # 如有需要进行重采样
                if original_sample_rate != target_sample_rate:
                    num_samples = int(len(chunk) * target_sample_rate / original_sample_rate)
                    chunk = signal.resample(chunk, num_samples)
                    chunk = chunk.astype(np.int16)

            return chunk.tobytes()

        audio_interface = None
        stream = None
        device_sample_rate = None
        chunk_size = 1024  # 增大单次读取帧数以提升性能

        def setup_audio():  
            nonlocal audio_interface, stream, device_sample_rate, input_device_index
            try:
                if audio_interface is None:
                    audio_interface = pyaudio.PyAudio()
                if input_device_index is None:
                    try:
                        default_device = audio_interface.get_default_input_device_info()
                        input_device_index = default_device['index']
                    except OSError as e:
                        input_device_index = None

                sample_rates_to_try = [16000]  # Try 16000 Hz first
                if input_device_index is not None:
                    highest_rate = get_highest_sample_rate(audio_interface, input_device_index)
                    if highest_rate != 16000:
                        sample_rates_to_try.append(highest_rate)
                else:
                    sample_rates_to_try.append(48000)  # Fallback sample rate

                for rate in sample_rates_to_try:
                    try:
                        device_sample_rate = rate
                        stream = initialize_audio_stream(audio_interface, device_sample_rate, chunk_size)
                        if stream is not None:
                            logging.debug(f"Audio recording initialized successfully at {device_sample_rate} Hz, reading {chunk_size} frames at a time")
                            # logging.error(f"Audio recording initialized successfully at {device_sample_rate} Hz, reading {chunk_size} frames at a time")
                            return True
                    except Exception as e:
                        logging.warning(f"Failed to initialize audio23 stream at {device_sample_rate} Hz: {e}")
                        continue

                # If we reach here, none of the sample rates worked
                raise Exception("Failed to initialize audio stream12 with all sample rates.")

            except Exception as e:
                logging.exception(f"Error initializing pyaudio audio recording: {e}")
                if audio_interface:
                    audio_interface.terminate()
                return False

        if not setup_audio():
            raise Exception("Failed to set up audio recording.")

        buffer = bytearray()
        silero_buffer_size = 2 * buffer_size  # 缓冲区过短会导致 Silero 报错

        time_since_last_buffer_message = 0

        try:
            while not shutdown_event.is_set():
                check_parent_process(shutdown_event)

                try:
                    data = stream.read(chunk_size, exception_on_overflow=False)
                    
                    if use_microphone.value:
                        processed_data = preprocess_audio(data, device_sample_rate, target_sample_rate)
                        buffer += processed_data

                        # 检查缓冲区长度是否达到 Silero 期望的大小
                        while len(buffer) >= silero_buffer_size:
                            # 从缓冲区中取出指定长度的数据
                            to_process = buffer[:silero_buffer_size]
                            buffer = buffer[silero_buffer_size:]

                            # 将提取的数据送入 audio_queue
                            if time_since_last_buffer_message:
                                time_passed = time.time() - time_since_last_buffer_message
                                if time_passed > 1:
                                    logging.debug("_audio_data_worker writing audio data into queue.")
                                    time_since_last_buffer_message = time.time()
                            else:
                                time_since_last_buffer_message = time.time()

                            audio_queue.put(to_process)
                            

                except OSError as e:
                    if e.errno == pyaudio.paInputOverflowed:
                        logging.warning("Input overflowed. Frame dropped.")
                    else:
                        logging.error(f"OSError during recording: {e}", exc_info=True)
                        # 尝试重新初始化音频流
                        logging.error("Attempting to reinitialize the audio stream...")

                        try:
                            if stream:
                                stream.stop_stream()
                                stream.close()
                        except Exception as e:
                            pass
                        
                        # Wait a bit before trying to reinitialize
                        time.sleep(1)
                        
                        if not setup_audio():
                            logging.error("Failed to reinitialize audio stream. Exiting.")
                            break
                        else:
                            logging.error("Audio stream reinitialized successfully.")
                    continue

                except Exception as e:
                    logging.error(f"Unknown error during recording: {e}")
                    tb_str = traceback.format_exc()
                    logging.error(f"Traceback: {tb_str}")
                    logging.error(f"Error: {e}")
                    # 尝试重新初始化音频流
                    logging.info("Attempting to reinitialize the audio stream...")
                    try:
                        if stream:
                            stream.stop_stream()
                            stream.close()
                    except Exception as e:
                        pass
                    
                    # Wait a bit before trying to reinitialize
                    time.sleep(1)
                    
                    if not setup_audio():
                        logging.error("Failed to reinitialize audio stream. Exiting.")
                        break
                    else:
                        logging.info("Audio stream reinitialized successfully.")
                    continue

        except KeyboardInterrupt:
            interrupt_stop_event.set()
            logging.debug("Audio data worker process finished due to KeyboardInterrupt")
        finally:
            # 录音结束后，将缓冲区中剩余的音频数据送入队列
            if buffer:
                audio_queue.put(bytes(buffer))
            
            try:
                if stream:
                    stream.stop_stream()
                    stream.close()
            except Exception as e:
                pass
            if audio_interface:
                audio_interface.terminate()

    def wakeup(self):
        """
        如果当前处于唤醒词模式，则将其视为已经说出唤醒词并进入监听状态。
        """
        self.listen_start = time.time()

    def abort(self):
        state = self.state
        self.start_recording_on_voice_activity = False
        self.stop_recording_on_voice_deactivity = False
        self.interrupt_stop_event.set()
        if self.state != RecorderState.INACTIVE.value: # if inactive, was_interrupted will never be set
            self.was_interrupted.wait()
            self._set_state(RecorderState.TRANSCRIBING.value)
        self.was_interrupted.clear()
        if self.is_recording: # if recording, make sure to stop the recorder
            self.stop()

    def wait_audio(self):
        """
        阻塞等待一次录音流程的开始与结束。

        该方法主要负责：
        - 在尚未开始录音时，等待检测到语音活动再启动录音；
        - 在录音进行中时，等待检测到语音结束并停录；
        - 将录制到的帧数据整理为连续音频并写入 self.audio；
        - 在完成后重置与录音相关的内部状态。

        副作用：
        - 更新当前状态（state）；
        - 修改实例的 audio 属性，使其包含当前录音的完整音频数据。
        """

        try:
            logging.info("Setting listen time")
            if self.listen_start == 0:
                self.listen_start = time.time()

            # 若尚未开始录音，则等待检测到语音活动后再启动录音
            if not self.is_recording and not self.frames:
                self._set_state(RecorderState.LISTENING.value)
                self.start_recording_on_voice_activity = True

                # 等待直到录音真正开始
                logging.debug('Waiting for recording start')
                while not self.interrupt_stop_event.is_set():
                    if self.start_recording_event.wait(timeout=0.02):
                        break

            # 如果录音正在进行，则等待语音变为静音后结束录音
            if self.is_recording:
                self.stop_recording_on_voice_deactivity = True

                # 等待直到录音真正停止
                logging.debug('Waiting for recording stop')
                while not self.interrupt_stop_event.is_set():
                    if (self.stop_recording_event.wait(timeout=0.02)):
                        break

            frames = self.frames
            if len(frames) == 0:
                frames = self.last_frames

            # 计算用于“补录”所需保留的采样点数
            samples_to_keep = int(self.sample_rate * self.backdate_resume_seconds)

            # 先将当前所有帧拼接为完整音频数组
            full_audio_array = np.frombuffer(b''.join(frames), dtype=np.int16)
            full_audio = full_audio_array.astype(np.float32) / INT16_MAX_ABS_VALUE

            # 计算需要为“再次监听”预留的尾部样本数
            if samples_to_keep > 0:
                samples_to_keep = min(samples_to_keep, len(full_audio))
                # 保留最后 N 个样本作为再次监听的前置音频
                frames_to_read_audio = full_audio[-samples_to_keep:]

                # 将这部分音频重新转为 int16 的 bytes 切分为帧
                frames_to_read_int16 = (frames_to_read_audio * INT16_MAX_ABS_VALUE).astype(np.int16)
                frame_bytes = frames_to_read_int16.tobytes()

                # 按固定帧长切分（假定标准帧长）
                FRAME_SIZE = 2048  # 常见帧大小
                frames_to_read = []
                for i in range(0, len(frame_bytes), FRAME_SIZE):
                    frame = frame_bytes[i:i + FRAME_SIZE]
                    if frame:  # Only add non-empty frames
                        frames_to_read.append(frame)
            else:
                frames_to_read = []

            # 处理 backdate_stop_seconds：从录音末尾回溯丢弃一部分样本
            samples_to_remove = int(self.sample_rate * self.backdate_stop_seconds)

            if samples_to_remove > 0:
                if samples_to_remove < len(full_audio):
                    self.audio = full_audio[:-samples_to_remove]
                    logging.debug(f"Removed {samples_to_remove} samples "
                        f"({samples_to_remove/self.sample_rate:.3f}s) from end of audio")
                else:
                    self.audio = np.array([], dtype=np.float32)
                    logging.debug("Cleared audio (samples_to_remove >= audio length)")
            else:
                self.audio = full_audio
                logging.debug(f"No samples removed, final audio length: {len(self.audio)}")

            self.frames.clear()
            self.last_frames.clear()
            self.frames.extend(frames_to_read)

            # 重置回溯相关参数
            self.backdate_stop_seconds = 0.0
            self.backdate_resume_seconds = 0.0

            self.listen_start = 0

            self._set_state(RecorderState.INACTIVE.value)

        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt in wait_audio, shutting down")
            self.shutdown()
            raise  # Re-raise the exception after cleanup

    def transcribe(self):
        """
        使用 `sensevoice_small` 模型对当前实例录制到的音频进行转写。

        当未手动调用 start()/stop() 时，将自动：
        - 在检测到语音活动时开始录音；
        - 在检测到语音结束时停止录音；
        最终对整段音频进行一次完整转写。

        返回：
                str: 若成功且未被中断，则返回对应的转写文本；若过程中被中断，则返回空字符串。

        异常：
                Exception: 转写过程中发生错误时抛出。
        """
        self._set_state(RecorderState.TRANSCRIBING.value)
        audio_copy = copy.deepcopy(self.audio)
        start_time = 0
        with self.transcription_lock:
            try:
                if self.transcribe_count == 0:
                    logging.debug("Adding transcription request, no early transcription started")
                    start_time = time.time()  # 开始计时
                    audio_copy = self._add_padding_to_audio(audio_copy)
                    # 通过转写客户端发送转写请求
                    self.transcriber.send(audio_copy, self.language)
                    self.transcribe_count += 1

                while self.transcribe_count > 0:
                    logging.debug(F"Receive from transcriber after sending transcription request, transcribe_count: {self.transcribe_count}")
                    # 通过转写客户端轮询结果是否就绪
                    if not self.transcriber.poll(0.1):  # 检查转写是否完成
                        if self.interrupt_stop_event.is_set():  # 检查是否被中断
                            self.was_interrupted.set()
                            self._set_state("inactive")
                            return "" # return empty string if interrupted
                        continue
                    # 通过转写客户端接收转写结果
                    status, result = self.transcriber.recv()
                    self.transcribe_count -= 1

                self.allowed_to_early_transcribe = True
                self._set_state("inactive")
                if status == 'success':
                    self.last_transcription_bytes = copy.deepcopy(audio_copy)                    
                    self.last_transcription_bytes_b64 = base64.b64encode(self.last_transcription_bytes.tobytes()).decode('utf-8')
                    transcription = self._preprocess_output(result)
                    end_time = time.time()  # 结束计时
                    transcription_time = end_time - start_time

                    if start_time:
                        if self.print_transcription_time:
                            print(f"Model {self.model_path} completed transcription in {transcription_time:.2f} seconds")
                        else:
                            logging.debug(f"Model {self.model_path} completed transcription in {transcription_time:.2f} seconds")
                    # 如已被中断则返回空串，否则返回转写文本
                    return "" if self.interrupt_stop_event.is_set() else transcription
                else:
                    logging.error(f"Transcription error: {result}")
                    raise Exception(result)
            except Exception as e:
                logging.error(f"Error during transcription: {str(e)}", exc_info=True)
                raise e

    def _process_wakeword(self, data):
        """对一段音频数据执行唤醒词检测，返回触发索引。

        具体检测逻辑由 IWakeWordDetector 实现类承担，
        这里仅负责统一的入口与返回值约定。
        """

        if not self.wakeword_detector:
            return -1

        try:
            return self.wakeword_detector.process(data)
        except Exception as e:
            logging.error("唤醒词检测出错: %s", e, exc_info=True)
            return -1

    def text(self,
             on_transcription_finished=None,
             ):
        """
                使用 `sensevoice_small` 模型对当前实例录制到的音频进行一次完整转写。

                - 在未手动调用 start() 的情况下，会在检测到语音活动时自动开始录音；
                - 在未手动调用 stop() 的情况下，会在检测到语音结束后自动停止录音；
                - 将录到的音频送入转写模型并返回文本。

                参数：
                        on_transcription_finished (callable, 可选): 当转写完成时异步回调，
                                若提供此参数，则在单独线程中调用该回调并将转写结果作为参数传入；
                                若不提供，则以同步方式执行并直接返回结果。

                返回：
                        str: 若未指定回调，则直接返回当前录音的转写文本。
        """
        self.interrupt_stop_event.clear()
        self.was_interrupted.clear()
        try:
            self.wait_audio()
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt in text() method")
            self.shutdown()
            raise  # Re-raise the exception after cleanup

        if self.is_shut_down or self.interrupt_stop_event.is_set():
            if self.interrupt_stop_event.is_set():
                self.was_interrupted.set()
            return ""

        if on_transcription_finished:
            threading.Thread(target=on_transcription_finished,
                            args=(self.transcribe(),)).start()
        else:
            return self.transcribe()

    def format_number(self, num):
        # 将数字转为字符串
        num_str = f"{num:.10f}"  # 确保精度足够
        # 将整数部分与小数部分拆开
        integer_part, decimal_part = num_str.split('.')
        # 取整数部分最后两位与小数部分前两位组成结果
        result = f"{integer_part[-2:]}.{decimal_part[:2]}"
        return result

    def start(self, frames = None):
        """
        直接开始录音，而不再等待语音活动触发。
        """

        # 确保在上次停止录音与本次开始录音之间有最小时间间隔
        if (time.time() - self.recording_stop_time
                < self.min_gap_between_recordings):
            logging.info("Attempted to start recording "
                         "too soon after stopping."
                         )
            return self

        logging.info("recording started")
        self._set_state(RecorderState.RECORDING.value)
        self.text_storage = []
        self.wakeword_detected = False
        self.wake_word_detect_time = 0
        self.frames = []
        if frames:
            self.frames = frames
        self.is_recording = True

        self.recording_start_time = time.time()
        self.is_silero_speech_active = False
        self.is_webrtc_speech_active = False
        self.stop_recording_event.clear()
        self.start_recording_event.set()

        if self.on_recording_start:
            self.on_recording_start()

        return self

    def stop(self,
             backdate_stop_seconds: float = 0.0,
             backdate_resume_seconds: float = 0.0,
        ):
        """
        停止录音。

        参数：
        - backdate_stop_seconds (float, 默认 0.0): 从当前时刻向前回溯多少秒作为真实停止时间，
            用于在人工按下“停止”稍有延迟时裁掉末尾多余的静音；
        - backdate_resume_seconds (float, 默认 0.0): 在下一次重新监听时，从当前音频末尾向前
            保留多少秒作为过渡缓冲。
        """

        # 确保本次录音时长不小于最小录音时长
        if (time.time() - self.recording_start_time
                < self.min_length_of_recording):
            logging.info("Attempted to stop recording "
                         "too soon after starting."
                         )
            return self

        logging.info("recording stopped")
        self.last_frames = copy.deepcopy(self.frames)
        self.backdate_stop_seconds = backdate_stop_seconds
        self.backdate_resume_seconds = backdate_resume_seconds
        self.is_recording = False
        self.recording_stop_time = time.time()
        self.is_silero_speech_active = False
        self.is_webrtc_speech_active = False
        self.silero_check_time = 0
        self.start_recording_event.clear()
        self.stop_recording_event.set()

        self.last_recording_start_time = self.recording_start_time
        self.last_recording_stop_time = self.recording_stop_time

        if self.on_recording_stop:
            self.on_recording_stop()

        return self

    def listen(self):
        """
        立即进入“监听”状态。
        典型场景如检测到唤醒词之后：此时不立即开始录音，而是等待真正的语音内容。
        当检测到语音活动时，会自动切换到“录音”状态。
        """
        self.listen_start = time.time()
        self._set_state(RecorderState.LISTENING.value)
        self.start_recording_on_voice_activity = True

    def feed_audio(self, chunk, original_sample_rate=16000):
        """
        手动向处理流水线中喂入一段音频数据。

        传入的多次音频块会先累计到内部缓冲区，当长度满足一定条件后，
        再被切成固定大小的数据块放入 audio_queue 中供后续模块处理。
        """
        # 如果还没有 buffer 属性，则初始化一个
        if not hasattr(self, 'buffer'):
            self.buffer = bytearray()

        # 检查输入是否为 NumPy 数组
        if isinstance(chunk, np.ndarray):
            # 如有需要，将双声道转换为单声道
            if chunk.ndim == 2:
                chunk = np.mean(chunk, axis=1)

            # 如有需要，重采样到 16000 Hz
            if original_sample_rate != 16000:
                num_samples = int(len(chunk) * 16000 / original_sample_rate)
                chunk = resample(chunk, num_samples)

            # 确保数据类型为 int16
            chunk = chunk.astype(np.int16)

            # 将 NumPy 数组转换为字节流
            chunk = chunk.tobytes()

        # 将当前块追加到缓冲区
        self.buffer += chunk
        buf_size = 2 * self.buffer_size  # Silero 要求长度不能太短

        # 当缓冲区长度达到或超过阈值时进行分块发送
        while len(self.buffer) >= buf_size:
            # 从缓冲区取出固定长度的数据
            to_process = self.buffer[:buf_size]
            self.buffer = self.buffer[buf_size:]

            # 将提取的数据送入 audio_queue
            self.audio_queue.put(to_process)
           
    def set_microphone(self, microphone_on=True):
        """
        开启或关闭麦克风输入。
        """
        logging.info("Setting microphone to: " + str(microphone_on))
        self.use_microphone.value = microphone_on

    def shutdown(self):
        """
        安全地关闭录音系统：停止各类工作线程/进程并关闭音频流。
        """

        with self.shutdown_lock:
            if self.is_shut_down:
                return

            print("\033[91mRealtimeSTT shutting down\033[0m")

            # 强制让 wait_audio() 和 text() 等阻塞调用尽快返回
            self.is_shut_down = True
            self.start_recording_event.set()
            self.stop_recording_event.set()

            self.shutdown_event.set()
            self.is_recording = False
            self.is_running = False

            logging.debug('Finishing recording thread')
            if self.recording_thread:
                self.recording_thread.join()

            logging.debug('Terminating reader process')

            # 给读入进程一些时间完成循环与清理
            if self.use_microphone.value:
                self.reader_process.join(timeout=10)

                if self.reader_process.is_alive():
                    logging.warning("Reader process did not terminate "
                                    "in time. Terminating forcefully."
                                    )
                    self.reader_process.terminate()

            logging.debug('Terminating transcription process')
            # 通过转写客户端统一关闭转写子进程与相关资源
            if hasattr(self, "transcriber") and self.transcriber is not None:
                self.transcriber.close(timeout=10)

            gc.collect()

    def _recording_worker(self):
        """
        主录音工作循环：持续监听音频输入并根据语音活动自动开始/停止录音。
        """
        try:
            time_since_last_buffer_message = 0
            was_recording = False
            delay_was_passed = False
            wakeword_detected_time = None
            wakeword_samples_to_remove = None
            self.allowed_to_early_transcribe = True

            # 持续监控音频数据以判断是否存在语音活动
            while self.is_running:
                try:
                    try:
                        data = self.audio_queue.get(timeout=0.01)
                        self.last_words_buffer.append(data)
                    except queue.Empty:
                        if not self.is_running:
                            break
                        continue

                    if self.on_recorded_chunk:
                        self.on_recorded_chunk(data)

                    if self.handle_buffer_overflow:
                        # 处理队列堆积过多的情况
                        if (self.audio_queue.qsize() > self.allowed_latency_limit):
                            logging.warning("Audio queue size exceeds "
                                            "latency limit. Current size: "
                                            f"{self.audio_queue.qsize()}. "
                                            "Discarding old audio chunks."
                                            )

                        while (self.audio_queue.qsize() > self.allowed_latency_limit):
                            data = self.audio_queue.get()

                except BrokenPipeError:
                    logging.error("BrokenPipeError _recording_worker", exc_info=True)
                    self.is_running = False
                    break

                # 更新用于统计日志输出频率的时间戳
                if time_since_last_buffer_message:
                    time_passed = time.time() - time_since_last_buffer_message
                    if time_passed > 1:
                        time_since_last_buffer_message = time.time()
                else:
                    time_since_last_buffer_message = time.time()

                failed_stop_attempt = False

                if not self.is_recording:
                    # 当前处于“未录音”状态的处理逻辑
                    time_since_listen_start = (time.time() - self.listen_start
                                            if self.listen_start else 0)

                    wake_word_activation_delay_passed = (
                        time_since_listen_start >
                        self.wake_word_activation_delay
                    )

                    # 处理唤醒词超时的回调
                    if wake_word_activation_delay_passed \
                            and not delay_was_passed:

                        if self.use_wake_words and self.wake_word_activation_delay:
                            if self.on_wakeword_timeout:
                                self.on_wakeword_timeout()
                    delay_was_passed = wake_word_activation_delay_passed

                    # 根据当前状态更新状态机与终端指示文本
                    if not self.recording_stop_time:
                        if self.use_wake_words \
                                and wake_word_activation_delay_passed \
                                and not self.wakeword_detected:
                            self._set_state("wakeword")
                        else:
                            if self.listen_start:
                                self._set_state("listening")
                            else:
                                self._set_state("inactive")

                    if self.use_wake_words and wake_word_activation_delay_passed:
                        try:
                            wakeword_index = self._process_wakeword(data)

                        except struct.error:
                            logging.error("Error unpacking audio data "
                                        "for wake word processing.", exc_info=True)
                            continue

                        except Exception as e:
                            logging.error(f"Wake word processing error: {e}", exc_info=True)
                            continue

                        # If a wake word is detected                        
                        if wakeword_index >= 0:
                            self.wake_word_detect_time = time.time()
                            wakeword_detected_time = time.time()
                            wakeword_samples_to_remove = int(self.sample_rate * self.wake_word_buffer_duration)
                            self.wakeword_detected = True
                            if self.on_wakeword_detected:
                                self.on_wakeword_detected()

                    # 检查是否有语音活动以决定是否开始录音
                    if ((not self.use_wake_words
                        or not wake_word_activation_delay_passed)
                            and self.start_recording_on_voice_activity) \
                            or self.wakeword_detected:

                        if self._is_voice_active():
                            logging.info("voice activity detected")
                            
                            self.start()
                            self.start_recording_on_voice_activity = False

                            # 将缓冲区中先前保存的音频一并加入当前录音帧
                            self.frames.extend(list(self.audio_buffer))
                            self.audio_buffer.clear()
                            self.silero_vad_model.reset_states()
                        else:
                            data_copy = data[:]
                            self._check_voice_activity(data_copy)

                    self.speech_end_silence_start = 0

                else:
                    # 若当前正在录音
                    if wakeword_samples_to_remove and wakeword_samples_to_remove > 0:
                        # 从录音开头移除属于唤醒词的样本
                        samples_removed = 0
                        while wakeword_samples_to_remove > 0 and self.frames:
                            frame = self.frames[0]
                            frame_samples = len(frame) // 2  # Assuming 16-bit audio
                            if wakeword_samples_to_remove >= frame_samples:
                                self.frames.pop(0)
                                samples_removed += frame_samples
                                wakeword_samples_to_remove -= frame_samples
                            else:
                                self.frames[0] = frame[wakeword_samples_to_remove * 2:]
                                samples_removed += wakeword_samples_to_remove
                                samples_to_remove = 0
                        
                        wakeword_samples_to_remove = 0

                    # 当在语音之后检测到静音时，尝试停止录音
                    if self.stop_recording_on_voice_deactivity:
                        is_speech = (
                            self._is_silero_speech(data) if self.silero_deactivity_detection
                            else self._is_webrtc_speech(data, True)
                        )

                        if not self.speech_end_silence_start:
                            str_speech_end_silence_start = "0"
                        else:
                            str_speech_end_silence_start = datetime.datetime.fromtimestamp(self.speech_end_silence_start).strftime('%H:%M:%S.%f')[:-3]

                        if not is_speech:
                            # 检测到语音结束，开始计时静音持续时间，满足条件才真正停止录音
                            if self.speech_end_silence_start == 0 and \
                                (time.time() - self.recording_start_time > self.min_length_of_recording):

                                self.speech_end_silence_start = time.time()

                            if self.speech_end_silence_start and self.early_transcription_on_silence and len(self.frames) > 0 and \
                                (time.time() - self.speech_end_silence_start > self.early_transcription_on_silence) and \
                                self.allowed_to_early_transcribe:
                                    self.transcribe_count += 1
                                    audio_array = np.frombuffer(b''.join(self.frames), dtype=np.int16)
                                    audio = audio_array.astype(np.float32) / INT16_MAX_ABS_VALUE
                                    audio = self._add_padding_to_audio(audio)
                                    # 使用转写客户端发送一次“早期转写”请求
                                    self.transcriber.send(audio, self.language)
                                    self.allowed_to_early_transcribe = False

                        else:
                            if self.speech_end_silence_start:
                                self.speech_end_silence_start = 0
                                self.allowed_to_early_transcribe = True

                        # 当静音持续足够长时间后，真正停止录音
                        if self.speech_end_silence_start and time.time() - \
                                self.speech_end_silence_start >= \
                                self.post_speech_silence_duration:

                            # 将时间转换为指定格式（HH:MM:SS.nnn）
                            silence_start_time = datetime.datetime.fromtimestamp(self.speech_end_silence_start).strftime('%H:%M:%S.%f')[:-3]

                            # 计算静音持续时长
                            time_diff = time.time() - self.speech_end_silence_start

                            self.frames.append(data)
                            self.stop()
                            if not self.is_recording:
                                self.speech_end_silence_start = 0
                            else:
                                failed_stop_attempt = True

                if not self.is_recording and was_recording:
                    # 录音停止后重置相关标志位，确保状态干净
                    self.stop_recording_on_voice_deactivity = False

                if time.time() - self.silero_check_time > 0.1:
                    self.silero_check_time = 0

                # 处理唤醒词超时：在检测到唤醒词后长时间未开始说话
                if self.wake_word_detect_time and time.time() - \
                        self.wake_word_detect_time > self.wake_word_timeout:

                    self.wake_word_detect_time = 0
                    if self.wakeword_detected and self.on_wakeword_timeout:
                        self.on_wakeword_timeout()
                    self.wakeword_detected = False

                was_recording = self.is_recording

                if self.is_recording and not failed_stop_attempt:
                    self.frames.append(data)

                if not self.is_recording or self.speech_end_silence_start:
                    self.audio_buffer.append(data)

        except Exception as e:
            if not self.interrupt_stop_event.is_set():
                logging.error(f"Unhandled exeption in _recording_worker: {e}", exc_info=True)
                raise

    def _is_silero_speech(self, chunk):
        """
        使用 Silero VAD 判断给定音频数据中是否包含语音。

        参数：
            data (bytes): 原始 16kHz、16bit 单声道音频数据块（通常为 1024 字节）。
        """
        cfg = VadConfig(
            sample_rate=self.sample_rate,
            silero_sensitivity=self.silero_sensitivity,
        )

        self.silero_working = True
        is_silero_speech_active = silero_is_speech(
            self.silero_vad_model,
            chunk,
            cfg,
        )
        self.is_silero_speech_active = is_silero_speech_active
        self.silero_working = False
        return is_silero_speech_active

    def _is_webrtc_speech(self, chunk, all_frames_must_be_true=False):
        """
        使用 WebRTC VAD 判断给定音频数据中是否包含语音。

        参数：
            data (bytes): 原始 16kHz、16bit 单声道音频数据块；
            all_frames_must_be_true (bool): 是否要求所有帧都被判断为语音才认为有语音。
        """
        speech_str = f"{bcolors.OKGREEN}WebRTC VAD detected speech{bcolors.ENDC}"
        silence_str = f"{bcolors.WARNING}WebRTC VAD detected silence{bcolors.ENDC}"
        speech_detected = webrtc_is_speech(
            self.webrtc_vad_model,
            chunk,
            self.sample_rate,
            all_frames_must_be_true=all_frames_must_be_true,
        )
        self.is_webrtc_speech_active = speech_detected
        return speech_detected

    def _check_voice_activity(self, data):
        """
        基于给定的音频数据触发一次语音活动检测。

        参数：
            data: 用于检测是否含有语音的音频数据。
        """
        self._is_webrtc_speech(data)

        # 首先使用 WebRTC 做一次快速语音检测
        if self.is_webrtc_speech_active:

            if not self.silero_working:
                self.silero_working = True

                # 在单独线程中执行计算量更大的 Silero 检测
                threading.Thread(
                    target=self._is_silero_speech,
                    args=(data,)).start()

    def clear_audio_queue(self):
        """
        安全地清空音频队列，避免在唤醒录音等场景下旧的残留音频被继续处理。
        """
        self.audio_buffer.clear()
        try:
            while True:
                self.audio_queue.get_nowait()
        except:
            # PyTorch 的 mp.Queue 没有专门的 Empty 异常，这里直接吃掉所有异常即可
            pass

    def _is_voice_active(self):
        """
        根据 WebRTC 与 Silero 的结果综合判断当前是否有语音活动。

        返回：
            bool: 若检测到语音则为 True，否则为 False。
        """
        return self.is_webrtc_speech_active and self.is_silero_speech_active

    def _set_state(self, new_state):
        """
        更新当前录音器的状态，并触发相应的状态切换回调。

        参数：
            new_state (str): 要切换到的新状态。

        """
        # 将传入状态规范化为 RecorderState 枚举以便统一处理
        try:
            state_enum = RecorderState(new_state)
        except ValueError:
            # 若遇到未知状态则退回到兼容旧逻辑的字符串状态处理
            logging.warning("Unknown state '%s', keeping legacy behaviour", new_state)
            self.state = new_state
            return

        callbacks = StateCallbacks(
            on_vad_detect_start=self.on_vad_detect_start,
            on_vad_detect_stop=self.on_vad_detect_stop,
            on_wakeword_detection_start=self.on_wakeword_detection_start,
            on_wakeword_detection_end=self.on_wakeword_detection_end,
            on_transcription_start=self.on_transcription_start,
        )

        transition_state(
            owner=self,
            new_state=state_enum,
            callbacks=callbacks,
            spinner_enabled=self.spinner,
            wake_words=self.wake_words,
        )

    def _set_spinner(self, text):
        """
        更新或创建终端中的旋转指示器文本。

        参数：
            text (str): 显示在指示器旁边的提示文字。
        """
        if self.spinner:
            # 若尚未创建 Halo 指示器，则新建并启动
            if self.halo is None:
                self.halo = halo.Halo(text=text)
                self.halo.start()
            # 若已存在 Halo 指示器，则仅更新其文本
            else:
                self.halo.text = text

    def _preprocess_output(self, text, preview=False):
        """
        对模型输出文本做简单的后处理：
        - 去掉首尾空白；
        - 将多余空白折叠为单个空格；
        - 可选地将句首字母大写，并在末尾补“.”。

        参数：
            text (str): 待处理的原始文本；
            preview (bool): 是否为预览模式，预览模式下不会强制补句号。

        返回：
            str: 处理后的文本。
        """
        text = re.sub(r'\s+', ' ', text.strip())

        if self.ensure_sentence_starting_uppercase:
            if text:
                text = text[0].upper() + text[1:]

        # 若不是预览模式且结尾为字母或数字，则在末尾补一个句号
        if not preview:
            if self.ensure_sentence_ends_with_period:
                if text and text[-1].isalnum():
                    text += '.'

        return text

    def _find_tail_match_in_text(self, text1, text2, length_of_match=10):
        """
                在 text2 中查找 text1 末尾一段子串的匹配位置。

                具体做法是取 text1 末尾 length_of_match 个字符，
                然后从 text2 末尾向前滑动查找是否存在完全相同的子串。

                参数：
                - text1 (str): 提供末尾子串的文本；
                - text2 (str): 要在其中查找该子串的文本；
                - length_of_match (int): 匹配子串的长度。

                返回：
                int: 若找到，则返回子串在 text2 中的起始下标；若未找到或文本过短，则返回 -1。
        """

        # 若任一输入文本长度不足以切出目标子串，则直接返回 -1
        if len(text1) < length_of_match or len(text2) < length_of_match:
            return -1

        # 取出 text1 的末尾目标子串
        target_substring = text1[-length_of_match:]

        # 从 text2 末尾向前滑动比较
        for i in range(len(text2) - length_of_match + 1):
            # 取出 text2 中当前要比较的子串
            current_substring = text2[len(text2) - i - length_of_match:
                                      len(text2) - i]

            # 比较当前子串与目标子串
            if current_substring == target_substring:
                # 返回在 text2 中的匹配起始位置
                return len(text2) - i

        return -1

    def _add_padding_to_audio(self, audio, padding_duration=1.0):
        """
        在音频首尾补零静音，以提升 ASR 模型的稳定性与效果。

        参数：
            audio (bytes): 需要补零的音频数据；
            padding_duration (float): 需要在首尾各补充的静音时长（秒）。
        """
        padding = np.zeros(int(self.sample_rate * padding_duration), dtype=np.float32)
        audio = np.concatenate([padding, audio, padding])
        return audio

    def __enter__(self):
        """
        配合上下文管理协议使用，使实例可以写在 `with` 语句中。

        进入 `with` 代码块时会自动调用此方法，方便集中管理资源。

        返回：
            self: 当前实例本身。
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
                定义退出上下文管理协议时的行为。

                离开 `with` 代码块时自动调用，用于执行必要的清理和资源释放操作，
                例如安全关闭录音与转写子进程。

                参数：
                        exc_type (Exception or None): 如因异常退出，则为异常类型；
                        exc_value (Exception or None): 异常实例；
                        traceback (Traceback or None): 对应的追踪栈信息。
        """
        self.shutdown()
