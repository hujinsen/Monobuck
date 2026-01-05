"""示例：麦克风实时识别 + finalize + refine

执行：
    python examples/demo_microphone_direct.py

操作：
  - 直接运行，内部获取麦克风音频，结束条件为 Ctrl+C 或策略完成。
  - 然后调用 transcribe_microphone_finalize() 再次收集最终文本并持久化。
"""
from __future__ import annotations
import datetime, json
from pathlib import Path

from core.asr_service import ASRService
from core.text_service import TextService
from core.config import set_config_value, get_config_value


def main():
    # 使用远程 ASR 或本地 ASR
    set_config_value("USE_REMOTE_ASR", False)
    set_config_value("PERSIST_ENABLE", True)

    asr = ASRService()
    text = TextService()

    print("开始麦克风识别，按 Ctrl+C 中断 ...")
    try:
        final_text = asr.transcribe_microphone_finalize()
    except KeyboardInterrupt:
        print("用户中断，未完整结束。")
        final_text = ""

    print("[ASR Final]", final_text)
    refined = text.refine(final_text, asr_service=asr) if final_text else ""
    print("[Refined]", refined)

    # if final_text:
    #     persist_dir = Path(get_config_value("PERSIST_DIR")) / datetime.date.today().isoformat()
    #     latest = max(persist_dir.glob("*.json"), default=None)
    #     if latest:
    #         data = json.loads(latest.read_text(encoding="utf-8"))
    #         print("[Session]", latest.name)
    #         print("  asr_phase.text:", data.get("asr_phase", {}).get("text"))
    #         print("  llm_phase.text:", data.get("llm_phase", {}).get("text"))


if __name__ == "__main__":
    main()
