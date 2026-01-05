
"""语音识别服务实现。

提供两种策略：
1. RemoteASRStrategy 使用阿里云 DashScope Fun-ASR 实时识别。
2. LocalASRStrategy 作为占位，后续可接入本地模型。

流式接口 transcribe_stream 产出增量 dict：
    {
        "text": str,              # 当前句或片段文本
        "is_final": bool,         # 是否句子结束（ASR端判断）
        "begin_time": int|None,   # 片段开始时间（毫秒）
        "end_time": int|None      # 片段结束时间（毫秒）
    }

设计要点（来源于前期讨论）：
 - 使用内部队列与回调分离发送与消费。
 - 记录首结果延迟与总字数，可扩展 metrics。
 - heartbeat 参数支持长时间静默连接。
 - 错误通过 failed 标志与异常抛出。
"""

from __future__ import annotations

import os
import time
import threading
import queue
import contextlib
from typing import Iterator, Generator, Dict, Any, Optional, cast
import multiprocessing
from core.base_ai_service import BaseSpeechService
from core.config import get_config_value
from funasr import AutoModel  
from funasr.register import tables 
from pathlib import Path
from typing import Any
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
        # 直接通过包名导入 RealtimeSTT，便于 PyInstaller 收集依赖
from RealtimeSTT.audio_recorder import AudioToTextRecorder  # type: ignore
class _ASRCallbackState:
    """内部状态与线程安全队列封装。"""

    def __init__(self) -> None:
        self.queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.completed = threading.Event()
        self.failed = threading.Event()
        self.error_message: Optional[str] = None
        self.first_result_time: Optional[float] = None
        self.start_send_time: Optional[float] = None
        self.total_chars: int = 0


class RemoteASRStrategy:
    MODEL = "fun-asr-realtime"

    def __init__(self):
        """构造远程 ASR 策略。直接从配置获取所需参数，无需外部传参。

        可读取键：
            ASR_FORMAT (默认 pcm)
            ASR_SAMPLE_RATE (默认 16000)
            ASR_SEMANTIC_PUNC (默认 False)
            ASR_HEARTBEAT (默认 False)
        """
        self._apply_api_key()
        # 移除实例级状态，改为按需创建，避免会话状态污染

    def start(self) -> None:
        """加载远程模型，适用于实时从识别音频流，这里提前加载好模型"""
        # 远程模式下，每次调用 transcribe_stream 会自动创建连接，无需预加载
        pass

    def stop(self) -> None:
        """停止模型加载。清理资源"""
        # 远程模式下，资源由 transcribe_stream 内部管理
        pass
        

        #主意是否清理self.state？有问题时需要注意


    # 工厂: 统一构造回调, 减少 transcribe_stream / transcribe_microphone 重复代码
    def _make_callback(self,
                state: _ASRCallbackState,
                closing_ref: Dict[str, bool],
                ctx: Dict[str, Any],
                *,
                mic: bool,
                mic_channels: int = 1,
                mic_chunk_ms: int = 120) -> Any:
        
        sample_rate = get_config_value("ASR_SAMPLE_RATE")
        frames_per_buffer = int(sample_rate * (mic_chunk_ms / 1000.0)) #1920个采样点
        ctx["frames_per_buffer"] = frames_per_buffer
        current_sentence_id: Optional[int] = None
        last_text: str = ""

        def _cleanup_mic():
            if not mic:
                return
            # 资源清理
            stream = ctx.get("mic_stream")
            if stream:
                with contextlib.suppress(Exception):
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()
            pa = ctx.get("pa")
            if pa:
                with contextlib.suppress(Exception):
                    pa.terminate()
            ctx["mic_stream"] = None
            ctx["pa"] = None

        class Callback(RecognitionCallback): 
            def on_open(self):
                state.start_send_time = time.time()
                if mic:
                    try:
                        import pyaudio  # type: ignore
                        pa = pyaudio.PyAudio()
                        mic_stream = pa.open(format=pyaudio.paInt16,
                                             channels=mic_channels,
                                             rate=sample_rate,
                                             input=True,
                                             frames_per_buffer=frames_per_buffer)
                        ctx["pa"] = pa
                        ctx["mic_stream"] = mic_stream
                    except Exception as e:  # pragma: no cover
                        state.error_message = f"麦克风打开失败: {e}"
                        state.failed.set()
                        state.completed.set()

            def on_event(self, result):  # result: RecognitionResult
                if closing_ref["closing"] or state.failed.is_set():
                    return
                sentence_raw = result.get_sentence()
                sentence = cast(Dict[str, Any], sentence_raw)
                if not sentence:
                    return
                sid = sentence.get("sentence_id")
                text = cast(str, sentence.get("text", ""))
                if state.first_result_time is None and text:
                    state.first_result_time = time.time()
                nonlocal current_sentence_id, last_text
                if isinstance(sid, int) and current_sentence_id != sid:
                    current_sentence_id = sid
                    last_text = ""
                if not text or text == last_text:
                    return
                last_text = text
                state.total_chars += len(text)
                is_final = bool(sentence.get("sentence_end"))
                assert is_final == RecognitionResult.is_sentence_end(sentence), "is_final 与 sentence_end 不一致"
                state.queue.put({
                    "text": text,
                    "is_final": is_final,
                    "begin_time": sentence.get("begin_time"),
                    "end_time": sentence.get("end_time") if is_final else None,
                    "words": sentence.get("words") or [],
                })

            def on_error(self, message):
                if closing_ref["closing"]:
                    state.completed.set()
                    return
                msg = getattr(message, "message", str(message))
                if isinstance(msg, str) and "has stopped" in msg.lower():
                    state.completed.set()
                    return
                state.error_message = msg
                state.failed.set()
                state.completed.set()

            def on_complete(self):
                state.completed.set()

            def on_close(self):
                state.completed.set()
                _cleanup_mic()

        ctx["_cleanup_mic"] = _cleanup_mic
        return Callback()

    # --- file mode ---
    def transcribe_file(self, file_path: str) -> str:
        """以分片流式方式识别本地文件，复用与 stream/mic 相同的回调与去重逻辑。

        仅在识别端判定句末 (is_final=True) 时累计文本，返回句子用 "。" 拼接的完整串。
        若文件为空或不存在抛出异常；识别失败抛出 RuntimeError。

        2025年11月18日。根据recognition.py里面的API，了解到本地文件识别可以用call（）方法实现。
        调用call（）方法后，会阻塞直到识别完成，返回识别结果。
        
        """
        self._apply_api_key()
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"音频文件不存在: {file_path}")
        if os.path.getsize(file_path) == 0:
            raise RuntimeError("音频文件为空")

        state = _ASRCallbackState()
        closing_ref = {"closing": False}
        ctx: Dict[str, Any] = {}
        callback = self._make_callback(state, closing_ref, ctx, mic=False)
        rec = Recognition(
            model=self.MODEL,
            format="wav" if file_path.lower().endswith(".wav") else self._format,
            sample_rate=get_config_value("ASR_SAMPLE_RATE"),
            callback=callback,
        )
        rec.start()
        sentences: list[str] = []
        bytes_per_100ms = int(get_config_value("ASR_SAMPLE_RATE") * 0.1 * 2)  # 16kHz *0.1s *2字节(int16)
        try:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(bytes_per_100ms)
                    if not chunk:
                        break
                    rec.send_audio_frame(chunk)
                    while not state.queue.empty():
                        part = state.queue.get()
                        if part.get("is_final") and part.get("text"):
                            sentences.append(part["text"].strip())
        except GeneratorExit:
            closing_ref["closing"] = True
        finally:
            with contextlib.suppress(Exception):
                rec.stop()
            while not state.queue.empty():
                part = state.queue.get()
                if part.get("is_final") and part.get("text"):
                    sentences.append(part["text"].strip())
            cleanup = ctx.get("_cleanup_mic")
            if callable(cleanup):
                cleanup()
        if not closing_ref["closing"] and state.failed.is_set():
            raise RuntimeError(f"ASR文件识别失败: {state.error_message}")
        return "。".join(sentences)

    # --- external stream mode ---
    def transcribe_stream(self, audio_stream: Iterator[bytes]) -> Generator[Dict[str, Any], None, None]:
        # 从外部传入音频字节，字节流由调用者提供，这里给出识别结果
        
        # 创建新的会话状态
        state = _ASRCallbackState()
        closing_ref = {"closing": False}
        ctx: Dict[str, Any] = {}
        callback = self._make_callback(state, closing_ref, ctx, mic=False)
        
        # 创建新的识别实例
        rec = Recognition(
            model=self.MODEL,
            format=get_config_value("ASR_FORMAT"),
            sample_rate=get_config_value("ASR_SAMPLE_RATE"),
            callback=callback,
        )
        rec.start()
        
        try:
            if state.failed.is_set():
                raise Exception(f"state.failed设置为True，识别失败: {state.error_message}")
            for audio in audio_stream:
                rec.send_audio_frame(audio)
                while not state.queue.empty():
                    part = state.queue.get()
                    yield part
        except GeneratorExit:
            closing_ref["closing"] = True
        finally:
            """
            contextlib.suppress(Exception) 用于抑制在 finally 块中可能发生的异常，
            确保无论是否发生异常，都能执行清理操作。
            """
            with contextlib.suppress(Exception):
                rec.stop()
            while not state.queue.empty():
                part = state.queue.get()
                yield part
            cleanup = ctx.get("_cleanup_mic")
            if callable(cleanup):
                cleanup()
        if not closing_ref["closing"] and state.failed.is_set():
            raise RuntimeError(f"ASR识别失败: {state.error_message}")  

    # --- microphone integrated mode ---
    def transcribe_microphone(self) -> Generator[Dict[str, Any], None, None]:
        self._apply_api_key()
        state = _ASRCallbackState()
        closing_ref = {"closing": False}
        ctx: Dict[str, Any] = {}
        callback = self._make_callback(state, closing_ref, ctx,
                                       mic=True,
                                       mic_channels=1,
                                       mic_chunk_ms=120)
        rec = Recognition(
            model=self.MODEL,
            format=get_config_value("ASR_FORMAT"),
            sample_rate=get_config_value("ASR_SAMPLE_RATE"),
            callback=callback,
        )
        rec.start()
        try:
            while True:
                if state.failed.is_set():
                    break
                mic_stream = ctx.get("mic_stream")
                if mic_stream is None:
                    if state.completed.is_set():
                        break
                    time.sleep(0.01)
                else:
                    data = mic_stream.read(ctx["frames_per_buffer"], exception_on_overflow=False)
                    rec.send_audio_frame(data)
                while not state.queue.empty():
                    part = state.queue.get()
                    yield part
                if state.completed.is_set():
                    break
        except KeyboardInterrupt:
            closing_ref["closing"] = True
            raise
        except GeneratorExit:
            closing_ref["closing"] = True
        finally:
            with contextlib.suppress(Exception):
                rec.stop()
            while not state.queue.empty():
                part = state.queue.get()
                yield part
            cleanup = ctx.get("_cleanup_mic")
            if callable(cleanup):
                cleanup()
        if not closing_ref["closing"] and state.failed.is_set():
            raise RuntimeError(f"ASR识别失败: {state.error_message}")

    # --- helpers ---
    def _apply_api_key(self) -> None:
        api_key = get_config_value("DASHSCOPE_API_KEY")
        if not api_key:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY，请在 config.json 中配置或使用 set_config_value。")
        dashscope.api_key = api_key


class LocalASRStrategy:
    """本地 ASR 策略：使用 RealtimeSTT(AudioToTextRecorder) 做整段识别。

    说明:
        - 依赖 mono_core/RealtimeSTT 下的 AudioToTextRecorder 与本地模型 iic/SenseVoiceSmall-onnx；
        - 不做真正流式增量，Rust/Tauri 推来的整段 PCM 会在此处一次性累积；
        - 流结束后将整段音频发送给 RealtimeSTT，一次性返回完整文本；
        - 对外仍保持 transcribe_stream 接口，但只产生一条 is_final=True 的结果。
    """

    def __init__(self) -> None:
        # 采样率：与 Rust 端保持一致（默认为 16k）
        self._sample_rate = int(get_config_value("LOCAL_ASR_SAMPLE_RATE") or 16000)



        model_path = get_config_value("LOCAL_ASR_MODEL_PATH") or "iic/SenseVoiceSmall-onnx"

        # 初始化本地 RealtimeSTT 录音/转写器（仅用其离线转写能力，不用内部麦克风）
        self._recorder = AudioToTextRecorder(
            model_path=model_path,
            silero_use_onnx=True,
            silero_deactivity_detection=True,
            use_microphone=False,
        )

    def start(self) -> None:
        """本地模型在构造时已加载，这里无需额外处理。"""
        return

    def stop(self) -> None:
        """预留清理接口，目前不做特殊资源释放。"""
        return

    # --- helpers ---
    @staticmethod
    def _bytes_to_int16_array(pcm_bytes: bytes):
        """将 16-bit PCM bytes 转为 np.int16 数组。"""
        import numpy as np  # type: ignore

        if not pcm_bytes:
            return np.zeros((0,), dtype=np.int16)
        return np.frombuffer(pcm_bytes, dtype=np.int16)

    # --- file mode ---
    def transcribe_file(self, file_path: str) -> str:
        import os
        import soundfile as sf  # type: ignore

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"音频不存在: {file_path}")

        audio_data, samplerate = sf.read(file_path, dtype="int16")
        if samplerate != self._sample_rate:
            raise RuntimeError(f"仅支持 {self._sample_rate}Hz，当前为 {samplerate}Hz")

        # 直接遵循 RealtimeSTT 示例：传入 int16 数组，由内部完成归一化
        self._recorder.audio = audio_data
        text = self._recorder.transcribe() or ""
        return text.strip()

    # --- external stream (bytes iterator) ---
    def transcribe_stream(
        self,
        audio_stream: Iterator[bytes],
    ) -> Generator[Dict[str, Any], None, None]:
        """整段累积：不做流式增量，迭代结束后一次性给出最终结果。"""

        import numpy as np  # type: ignore

        buffer = np.array([], dtype=np.int16)
        start_wall_ms: Optional[int] = None

        try:
            for chunk in audio_stream:
                if not chunk:
                    continue
                # 兼容上层以特殊标记结束会话的情况
                if chunk == b"__STOP__":
                    break
                if start_wall_ms is None:
                    # 记录第一次收到音频数据的墙钟时间（毫秒）
                    start_wall_ms = int(time.time() * 1000)
                arr = np.frombuffer(chunk, dtype=np.int16)
                if arr.size == 0:
                    continue
                buffer = np.concatenate((buffer, arr))
        except GeneratorExit:
            # 上层提前终止会话
            return

        if buffer.size == 0:
            return

        # 计算整段音频的时长（毫秒）
        total_samples = int(buffer.size)
        duration_ms = int(total_samples * 1000 / self._sample_rate)

        # 若未记录开始时间，则以当前时间减去 duration 近似
        if start_wall_ms is None:
            start_wall_ms = int(time.time() * 1000) - duration_ms

        try:
            self._recorder.audio = buffer
            text = self._recorder.transcribe() or ""
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"本地 ASR 识别失败: {e}") from e

        text = text.strip()
        if not text:
            return

        # 只返回一条最终结果，让上层 websocket_server 按 is_final=True 走后续 refine / 持久化逻辑
        yield {
            "text": text,
            "is_final": True,
            "begin_time": start_wall_ms,
            "end_time": start_wall_ms + duration_ms,
        }

    # --- microphone mode ---
    def transcribe_microphone(self) -> Generator[Dict[str, Any], None, None]:
        """当前本地策略不直接提供麦克风模式，需通过 Rust/Tauri 提供音频流。"""
        raise RuntimeError(
            "LocalASRStrategy(RealtimeSTT) 不支持直接麦克风输入，请通过 Rust/Tauri 提供 audio_stream。"
        )
    
    
class ASRService(BaseSpeechService):
    """语音识别服务统一入口。持久化逻辑下沉到本类和 text_service。"""

    def __init__(self) -> None:
        print('初始化ASRService',flush=True)
        use_remote = True
        try:
            flag = get_config_value("USE_REMOTE_ASR")
            if flag is not None:
                use_remote = bool(flag)
        except Exception:
            pass
        print(f'ASRService是否使用远程模型：{use_remote}',flush=True)
        if use_remote:
            self._strategy = RemoteASRStrategy()
            self.strategy_name = getattr(RemoteASRStrategy, "MODEL", "remote-asr")
            self._remote_flag = True
        else:
            self._strategy = LocalASRStrategy()
            self.strategy_name = "SenseVoiceSmall"
            self._remote_flag = False
        self._last_session_id: str | None = None
    
    def start(self) -> None:
        self._strategy.start()

    def stop(self) -> None:
        self._strategy.stop()

    # --- public facade ---
    def transcribe_file(self, file_path: str) -> str:
        text = self._strategy.transcribe_file(file_path)
        return text

    def transcribe_stream(self, audio_stream: Iterator[bytes]) -> Generator[Dict[str, Any], None, None]:
        # 透传底层策略，不做持久化。若需要持久化请使用 transcribe_stream_with_persist / transcribe_stream_finalize。
        return self._strategy.transcribe_stream(audio_stream)

    def transcribe_stream_with_persist(
        self,
        audio_stream: Iterator[bytes],
        persist: bool = True,
    ) -> Generator[Dict[str, Any], None, str]:
        """增量流式识别并在结束后保存会话（不自动 refine）。

        使用示例:
            gen = asr.transcribe_stream_with_persist(audio_iter, persist=True)
            try:
                for part in gen:
                    print(part)
            except StopIteration as e:
                final_text = e.value
        """
        finals: list[str] = []

        for part in self._strategy.transcribe_stream(audio_stream):
            if part.get("is_final") and part.get("text"):
                finals.append(str(part["text"]).strip())
            yield part
        final_text = "。".join(finals)
        return final_text

    def transcribe_stream_finalize(
        self,
        audio_stream: Iterator[bytes],
    ) -> str:
        """
        阻塞式流式语音识别，收集所有音频块并返回最终识别文本。
        Args:
            audio_stream (Iterator[bytes]): 音频数据流迭代器
        Returns:
            str: 合并后的最终识别文本，使用句号连接各段最终结果
        """
        finals: list[str] = []
        
        for part in self._strategy.transcribe_stream(audio_stream):
            if part.get("is_final") and part.get("text"):
                finals.append(str(part["text"]).strip())
        final_text = "。".join(finals)
        return final_text

    def create_stream_session(self, asr_text: str, pcm_bytes: bytes | None = None) -> str | None:
        # Python 侧不再负责持久化，直接返回占位 session id 或 None
        return None

    def transcribe_microphone(self) -> Generator[Dict[str, Any], None, None]:
        return self._strategy.transcribe_microphone()

    def transcribe_microphone_finalize(self) -> str:
        """
    从麦克风输入中转录并最终化语音识别结果，将结果保存到会话管理器中。
    
    该方法会收集麦克风输入的原始音频数据(PCM格式)和语音识别的中间结果，
    当识别到最终结果时，会将文本片段保存。最后将所有最终识别结果拼接成完整文本，
    并将音频数据和识别结果保存到会话管理器中。
    
    Args:
        无显式参数，但使用实例的以下属性：
        - self._strategy: 语音识别策略对象
        - self._remote_flag: 是否远程处理的标志
        - self.strategy_name: 使用的ASR模型名称
    
    Returns:
        str: 拼接后的最终识别文本，以句号("。")连接各片段
    
    Raises:
        无显式抛出异常，但依赖的transcribe_microphone()和session_manager.start_pcm()可能抛出异常
        """
        final_sentences: list[str] = []
        for part in self._strategy.transcribe_microphone():
            if part.get("is_final") and part.get("text"):
                final_sentences.append(str(part["text"]).strip())
        joined = "。".join(final_sentences)
        return joined





if __name__ == "__main__":  # pragma: no cover
    multiprocessing.freeze_support()  # # 为了 Windows 打包兼容

    # 简单自测试: 麦克风实时识别并打印结果 (需要有效 DASHSCOPE_API_KEY)
    # svc = ASRService()
    # for part in svc.transcribe_microphone():
    #     print(part)  # {'text': '...', 'is_final': bool, ...}
    # res = svc.transcribe_file(r"D:\code_trip\alibabacloud-bailian-speech-demo\samples\sample-data\what_color.wav")
    # print(res)
    """
    {'text': '这个语音识别比较慢吗？', 'is_final': False, 'begin_time': 12020, 'end_time': None, 'words': [{'begin_time': 12020, 'end_time': 12340, 'text': '这个', 'punctuation': '', 'fixed': False, 'speaker_id': None}, {'begin_time': 12340, 'end_time': 12660, 'text': '语音', 'punctuation': '', 'fixed': False, 'speaker_id': None}, {'begin_time': 12660, 'end_time': 12980, 'text': '识别', 'punctuation': '', 'fixed': False, 'speaker_id': None}, {'begin_time': 12980, 'end_time': 13300, 'text': '比较', 'punctuation': '', 'fixed': False, 'speaker_id': None}, {'begin_time': 13300, 'end_time': 13500, 'text': '慢', 'punctuation': '', 'fixed': False, 'speaker_id': None}, {'begin_time': 13500, 'end_time': 13820, 'text': '吗', 'punctuation': '？', 'fixed': False, 'speaker_id': None}]}
    """