"""交互式麦克风语音识别示例：

双击 Ctrl 开始录音 + 语音识别，单击 Ctrl 停止后一次性进行文本规范化输出。

特性:
    - 仅在识别结果句末 (is_final=True) 追加，减少重复中间片段。
    - 结束后将所有句子拼接送入文本服务 refine。
    - 可多次重复会话，互不影响。

依赖安装 (使用 uv):
    uv add dashscope pyaudio pynput
Windows 若 pyaudio 安装失败，可尝试:
    pip install pipwin
    pipwin install pyaudio

环境变量:
    $env:DASHSCOPE_API_KEY="sk-xxxx"  # 不要硬编码在代码里

运行:
    python -m examples.run_mic_stream

交互:
    双击 Ctrl 开始，一次 Ctrl 停止并输出结果，Ctrl+C 退出程序。
"""
from __future__ import annotations

import time
import threading
from typing import List

try:
    from pynput import keyboard  # type: ignore
except ImportError:  # pragma: no cover
    keyboard = None  # 延迟报错

from core.asr_service import ASRService, create_microphone_stream
from core.text_service import TextService

DOUBLE_CTRL_INTERVAL_MS = 400  # 双击判定阈值
CHUNK_MS = 100
SAMPLE_RATE = 16000

_last_ctrl_time_ms: float = 0.0
_running_lock = threading.Lock()
_running = False
_stop_event = threading.Event()
_sentences: List[str] = []
_thread: threading.Thread | None = None

asr = ASRService()
text = TextService()


def _collect_loop():
    """后台线程：持续消费音频迭代并获取最终句子。"""
    global _running
    audio_iter = create_microphone_stream(sample_rate=SAMPLE_RATE, chunk_ms=CHUNK_MS)
    try:
        for part in asr.transcribe_stream(audio_iter):
            if _stop_event.is_set():
                break
            if not part.get("text"):
                continue
            # 仅在句末追加，避免中间重复
            if part.get("is_final"):
                _sentences.append(part["text"].strip())
    except Exception as e:  # pragma: no cover - 运行时错误展示
        print(f"[collect] 异常: {e}")
    finally:
        with _running_lock:
            _running = False


def start_session():
    global _thread, _running
    with _running_lock:
        if _running:
            return
        _running = True
    _stop_event.clear()
    _sentences.clear()
    _thread = threading.Thread(target=_collect_loop, daemon=True)
    _thread.start()
    print("[session] 开始录音/识别...")


def stop_session():
    global _thread
    _stop_event.set()
    if _thread:
        _thread.join()
    raw_text = "。".join(_sentences)
    print(f'[RAW] {raw_text}')
    refined = text.refine(raw_text) if raw_text else ""
    print("\n[RAW]", raw_text)
    print("[REFINED]", refined, "\n")
    print("[session] 已结束，可再次双击 Ctrl 开始新的会话。")


def on_press(key):
    global _last_ctrl_time_ms
    if key not in (getattr(keyboard, "Key").ctrl, getattr(keyboard, "Key").ctrl_l, getattr(keyboard, "Key").ctrl_r):  # type: ignore[attr-defined]
        return
    now = time.time() * 1000
    with _running_lock:
        active = _running

    if not active:
        # 判定双击
        if now - _last_ctrl_time_ms <= DOUBLE_CTRL_INTERVAL_MS:
            start_session()
            _last_ctrl_time_ms = 0.0
        else:
            _last_ctrl_time_ms = now
    else:
        # 单击结束
        stop_session()


def main():
    if keyboard is None:
        raise RuntimeError("缺少 pynput，请先安装: uv add pynput 或 pip install pynput")
    print("双击 Ctrl 开始录音，录制期间单击 Ctrl 结束并规范化输出。Ctrl+C 退出。")
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    try:
        listener.join()
    except KeyboardInterrupt:  # pragma: no cover
        with _running_lock:
            active = _running
        if active:
            stop_session()
        print("退出。")


if __name__ == "__main__":
    main()
