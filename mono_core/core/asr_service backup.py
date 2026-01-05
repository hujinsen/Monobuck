
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

from core.base_ai_service import BaseSpeechService
from core.config import get_config_value
from funasr import AutoModel  
from funasr.register import tables 
from pathlib import Path
from typing import Any
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

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
    """本地 ASR 策略：使用项目内置 SenseVoiceSmall 模型进行“伪流式”与整文件识别。

    说明:
        - 依赖本地目录 iic/SenseVoiceSmall 与 core/model.py 中的模型定义 (FunASR AutoModel)。
        - 流式/麦克风模式采用“累积整段 + 重解码 + 增量差异”方式，不是真正深度流式，性能与延迟取决于窗口大小。
        - 仅在停止或 Generator 结束时输出最终 is_final=True 的结果，过程中增量 is_final=False。

    可配置项 (通过 config.json 或外部 set_config_value)：
        - LOCAL_ASR_SAMPLE_RATE (默认 16000)
        - LOCAL_ASR_BLOCK_MS (默认 50)  麦克风单次采集块大小
        - LOCAL_ASR_INFER_WINDOW_S (默认 1.5) 推理刷新间隔
        - LOCAL_ASR_MIN_FIRST_INFER_S (默认 1.0) 首次最少音频秒数
        - LOCAL_ASR_USE_ITN (默认 True) 是否启用 ITN
        - LOCAL_ASR_LANGUAGE (默认 auto)
        - LOCAL_ASR_ENABLE_VAD (默认 True) 是否使用内置 VAD (fsmn-vad)
    """

    def __init__(self) -> None:
        
        self._loaded = False
        self._model: Any | None = None  # 延迟加载 AutoModel
        self._device = "cpu"  # 可后续暴露配置
        self._cache: Dict[str, Any] = {}
        # 路径解析
        core_dir = Path(__file__).resolve().parent
        project_root = core_dir.parent
        self._model_dir = (project_root / "iic" / "SenseVoiceSmall" ).as_posix()
        self._model_define = (core_dir / "model.py").as_posix()
        # 参数（若取不到配置则用默认）
        self._sample_rate = int(get_config_value("LOCAL_ASR_SAMPLE_RATE") or 16000)
        self._block_ms = int(get_config_value("LOCAL_ASR_BLOCK_MS") or 120)
        self._infer_window_s = float(get_config_value("LOCAL_ASR_INFER_WINDOW_S") or 1.5)
        self._min_first_infer_s = float(get_config_value("LOCAL_ASR_MIN_FIRST_INFER_S") or 1.0)
        self._use_itn = bool(get_config_value("LOCAL_ASR_USE_ITN") if get_config_value("LOCAL_ASR_USE_ITN") is not None else True)
        self._language = str(get_config_value("LOCAL_ASR_LANGUAGE") or "auto")
        self._enable_vad = bool(get_config_value("LOCAL_ASR_ENABLE_VAD") if get_config_value("LOCAL_ASR_ENABLE_VAD") is not None else True)

        self.start() #初始化时候就加载模型

    def start(self) -> None:
        """启动模型加载。"""
        self._lazy_load()

    # --- internal helpers ---
    def _lazy_load(self) -> None:
        if self._loaded:
            return

        vad_model = "fsmn-vad" if self._enable_vad else None
        self._model = AutoModel(
            model="iic/SenseVoiceSmall",#魔搭上的模型ID，不要更改,首次运行自动下载模型到缓存目录
            vad_model=vad_model,     #把所有模型移动到本地模型目录，下次不会再下载。
            device=self._device,
            disable_update=True, # 禁用自动更新
            trust_remote_code=True, # 读取本地模型代码
            remote_code = self._model_define, #本地模型代码
            local_dir = self._model_dir #本地模型目录，下载后放入此目录
    
            
        )
        self._loaded = True

    def stop(self) -> None:
        """停止模型加载。做一些清理的工作"""
        self._loaded = False
        self._model = None

    @staticmethod
    def _incremental_diff(prev: str, cur: str) -> str:
        """计算两个字符串之间的增量差异，返回 cur 相对于 prev 的新增部分。"""
        common_len = 0
        for i in range(min(len(prev), len(cur))):
            if prev[i] != cur[i]:
                break
            common_len = i + 1
        return cur[common_len:]

    def _run_inference_on_bytes(self, pcm_bytes: bytes) -> str:
        """将累积的 16-bit PCM bytes 转存临时 wav，调用模型并返回文本。"""
        import tempfile, wave, os
        if self._model is None:
            raise RuntimeError("模型尚未加载")
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        # 写 wav
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sample_rate)
            wf.writeframes(pcm_bytes)
        try:
            res = self._model.generate(
                input=path,
                cache=self._cache,  # 可复用减少重复计算（伪流式）
                language=self._language,
                use_itn=self._use_itn,
                batch_size_s=60,
                merge_vad=True,
                merge_length_s=15,
            )
        finally:
            with contextlib.suppress(Exception):
                os.remove(path)
        if not res or not isinstance(res, list):
            return ""
        return str(res[0].get("text", ""))

    # --- file mode ---
    def transcribe_file(self, file_path: str) -> str:
        self._lazy_load()
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"音频不存在: {file_path}")
        if self._model is None:
            raise RuntimeError("模型未成功初始化")
        # 直接用模型文件推理
        res = self._model.generate(
            input=file_path,
            cache={},  # 文件识别不复用缓存
            language=self._language,
            use_itn=self._use_itn,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
        if not res or not isinstance(res, list):
            return ""
        return str(res[0].get("text", ""))

    # --- external stream (bytes iterator) ---
    def transcribe_stream(self, audio_stream: Iterator[bytes]) -> Generator[Dict[str, Any], None, None]:
        """伪流式：累积 PCM 字节到窗口阈值后重解码，产生增量文本。"""
        
        window_bytes_target = int(self._sample_rate * (self._infer_window_s) * 2)  # int16 2字节
        min_first_bytes = int(self._sample_rate * self._min_first_infer_s * 2)
        buffer = bytearray()
        last_infer_time = 0.0
        partial_text = ""
        try:
            for chunk in audio_stream:
                if not chunk:
                    continue
                buffer.extend(chunk)
                total_bytes = len(buffer)
                elapsed = time.time() - last_infer_time
                do_infer = False
                if partial_text == "" and total_bytes >= min_first_bytes:
                    do_infer = True
                elif elapsed >= self._infer_window_s and total_bytes >= min_first_bytes:
                    do_infer = True
                if do_infer:
                    last_infer_time = time.time()
                    current_text = self._run_inference_on_bytes(bytes(buffer))
                    new_part = self._incremental_diff(partial_text, current_text)
                    if new_part.strip():
                        partial_text = current_text
                        yield {
                            "text": new_part.strip(),
                            "is_final": False,
                            "begin_time": None,
                            "end_time": None,
                        }
        except GeneratorExit:
            # 生成器提前关闭，准备输出最终结果
            pass
        finally:
            # 直接使用已有的识别结果作为最终结果，不再重复识别
            # 这避免了在流结束时的额外处理时间
            if partial_text:
                # 标记为最终结果
                yield {
                    "text": partial_text.strip(),
                    "is_final": True,
                    "begin_time": None,
                    "end_time": None,
                }

    # --- microphone mode ---
    def transcribe_microphone(self) -> Generator[Dict[str, Any], None, None]:
        """麦克风伪流式：与 asr_sencevoice.py 类似逻辑，增量输出。"""
        self._lazy_load()
        # 尝试 sounddevice 优先
        try:
            import sounddevice as sd  # type: ignore
            use_sd = True
        except Exception:
            use_sd = False
            try:
                import pyaudio  # type: ignore
            except Exception as e:  # pragma: no cover
                raise RuntimeError("缺少 sounddevice 或 pyaudio，无法使用麦克风本地 ASR。") from e
        try:
            import numpy as np  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("本地 ASR 需要 numpy，请先安装: pip install numpy") from e
        block_size = int(self._sample_rate * self._block_ms / 1000)
        buffer_pcm = bytearray()
        partial_text = ""
        last_infer_time = 0.0
        min_first_bytes = int(self._sample_rate * self._min_first_infer_s * 2)

        if use_sd:
            q: "queue.Queue[np.ndarray]" = queue.Queue()
            def _cb(indata, frames, time_info, status):  # noqa: D401
                if status:  # pragma: no cover - 状态仅日志
                    pass
                q.put(indata.copy())
            stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype=np.int16,
                blocksize=block_size,
                callback=_cb,
            )
            stream.start()
            get_chunk = lambda: q.get(timeout=0.5)
        else:
            pa = pyaudio.PyAudio()  # type: ignore
            stream = pa.open(
                format=pyaudio.paInt16,  # type: ignore
                channels=1,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=block_size,
            )
            get_chunk = lambda: np.frombuffer(stream.read(block_size, exception_on_overflow=False), dtype=np.int16)

        try:
            while True:
                try:
                    chunk_arr = get_chunk()
                except queue.Empty:
                    continue
                if chunk_arr is None:
                    continue
                if hasattr(chunk_arr, "ndim") and chunk_arr.ndim > 1:
                    chunk_arr = chunk_arr.reshape(-1)
                buffer_pcm.extend(chunk_arr.tobytes())
                total_bytes = len(buffer_pcm)
                elapsed = time.time() - last_infer_time
                do_infer = False
                if partial_text == "" and total_bytes >= min_first_bytes:
                    do_infer = True
                elif elapsed >= self._infer_window_s and total_bytes >= min_first_bytes:
                    do_infer = True
                if do_infer:
                    last_infer_time = time.time()
                    current_text = self._run_inference_on_bytes(bytes(buffer_pcm))
                    new_part = self._incremental_diff(partial_text, current_text)
                    if new_part.strip():
                        partial_text = current_text
                        yield {
                            "text": new_part.strip(),
                            "is_final": False,
                            "begin_time": None,
                            "end_time": None,
                        }
        except KeyboardInterrupt:
            # 用户中断，输出最终
            pass
        finally:
            with contextlib.suppress(Exception):
                # pyaudio stream: stop_stream(); sounddevice InputStream: stop()
                if hasattr(stream, "stop_stream"):
                    stream.stop_stream()  # type: ignore[attr-defined]
                if hasattr(stream, "stop"):
                    stream.stop()  # type: ignore[call-arg]
                if hasattr(stream, "close"):
                    stream.close()
            if not use_sd:
                with contextlib.suppress(Exception):
                    pa.terminate()
            # 直接使用已有的识别结果作为最终结果，不再重复识别
            # 这避免了在流结束时的额外处理时间
            if partial_text:
                # 标记为最终结果
                yield {
                    "text": partial_text.strip(),
                    "is_final": True,
                    "begin_time": None,
                    "end_time": None,
                }
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
    # 简单自测试: 麦克风实时识别并打印结果 (需要有效 DASHSCOPE_API_KEY)
    svc = ASRService()
    for part in svc.transcribe_microphone():
        print(part)  # {'text': '...', 'is_final': bool, ...}
    # res = svc.transcribe_file(r"D:\code_trip\alibabacloud-bailian-speech-demo\samples\sample-data\what_color.wav")
    # print(res)
    """
    {'text': '这个语音识别比较慢吗？', 'is_final': False, 'begin_time': 12020, 'end_time': None, 'words': [{'begin_time': 12020, 'end_time': 12340, 'text': '这个', 'punctuation': '', 'fixed': False, 'speaker_id': None}, {'begin_time': 12340, 'end_time': 12660, 'text': '语音', 'punctuation': '', 'fixed': False, 'speaker_id': None}, {'begin_time': 12660, 'end_time': 12980, 'text': '识别', 'punctuation': '', 'fixed': False, 'speaker_id': None}, {'begin_time': 12980, 'end_time': 13300, 'text': '比较', 'punctuation': '', 'fixed': False, 'speaker_id': None}, {'begin_time': 13300, 'end_time': 13500, 'text': '慢', 'punctuation': '', 'fixed': False, 'speaker_id': None}, {'begin_time': 13500, 'end_time': 13820, 'text': '吗', 'punctuation': '？', 'fixed': False, 'speaker_id': None}]}
    """