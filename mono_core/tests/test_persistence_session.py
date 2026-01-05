"""持久化最小测试：验证 ServiceRuntime.process_file 生成 JSON 会话文件。

运行方式（无需 pytest）：
    python tests/test_persistence_session.py

测试逻辑：
1. 动态设置配置：开启 PERSIST_ENABLE，使用本地 LLM（避免远程调用），保留远程 ASR 但会 monkeypatch 其文件识别以避免真实推理。
2. 生成一个临时静音 wav 文件作为输入。
3. 调用 ServiceRuntime.process_file(persist=True)。
4. 在 PERSIST_DIR/当天目录下查找新增的 JSON 文件，解析并断言关键字段存在。

注意：
- 若已有历史文件，会根据调用前后文件数量差异判断是否新增。
- 不依赖真实模型或 API Key；通过 monkeypatch 避免网络调用。
"""
from __future__ import annotations

import os
import sys
import wave
import tempfile
import json
from pathlib import Path
from typing import List
import datetime

# 保证可以 import core 包
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from core.service_runtime import ServiceRuntime  # type: ignore
from core.config import set_config_value, get_config_value  # type: ignore


def _make_silent_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> str:
    frames = int(duration_s * sample_rate)
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        silence = b"\x00\x00" * frames
        wf.writeframes(silence)
    return path


def _list_json_files(persist_dir: str) -> List[str]:
    today = datetime.date.today().isoformat()
    day_dir = Path(persist_dir) / today
    if not day_dir.exists():
        return []
    return [str(p) for p in day_dir.glob("*.json")]


def main() -> None:
    # 配置：启用持久化；禁用远程 LLM；保留远程 ASR 但将其 transcribe_file 打桩
    set_config_value("PERSIST_ENABLE", True)
    persist_dir = get_config_value("PERSIST_DIR") or str(Path(PROJECT_ROOT) / "persist")
    set_config_value("PERSIST_DIR", persist_dir)
    set_config_value("USE_REMOTE_LLM", False)  # 使用本地 LLM，避免远程调用

    # 构造运行时
    rt = ServiceRuntime()

    # 打桩 ASR 文件识别，避免真实推理或网络调用
    original_transcribe_file = rt.asr.transcribe_file

    def _fake_transcribe(file_path: str, persist: bool = True) -> str:  # type: ignore[override]
        # 保留持久化分支逻辑，手动调用真正策略以演示可选
        return "测试静音文本"  # 简单返回固定文本

    rt.asr.transcribe_file = _fake_transcribe  # type: ignore

    before_files = _list_json_files(persist_dir)
    silent_wav = _make_silent_wav()

    try:
        refined = rt.process_file(silent_wav, persist=True)
        print(f"refined: {refined}")
    finally:
        try:
            os.remove(silent_wav)
        except OSError:
            pass

    after_files = _list_json_files(persist_dir)
    new_files = [f for f in after_files if f not in before_files]

    if not new_files:
        raise AssertionError("未发现新增 JSON 会话文件，持久化可能未执行。")

    latest = max(new_files, key=os.path.getmtime)
    print(f"新增会话文件: {latest}")

    with open(latest, "r", encoding="utf-8") as fr:
        data = json.load(fr)

    # 基础字段断言
    required_keys = ["session_id", "created_at", "mode", "audio", "asr_phase", "llm_phase"]
    for k in required_keys:
        if k not in data:
            raise AssertionError(f"JSON 缺少必要字段: {k}")

    if data.get("mode") != "file":
        raise AssertionError(f"mode 应为 file 实际为: {data.get('mode')}")

    if not isinstance(data.get("created_at"), str):
        raise AssertionError("created_at 不是字符串")

    llm_phase = data.get("llm_phase") or {}
    if "enabled" not in llm_phase:
        raise AssertionError("llm_phase 缺少 enabled")

    print("[OK] 持久化测试通过")


if __name__ == "__main__":  # pragma: no cover
    main()
