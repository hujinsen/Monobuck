"""示例：整文件识别 + 持久化 + refine

运行前：
1. 将待识别的 wav 文件路径替换 AUDIO_PATH。
2. 确认 config.json 中 PERSIST_ENABLE: true，并设置 USE_REMOTE_ASR 为需要的模式。
3. 若使用本地模型，首次运行会下载模型，需联网，后续走本地缓存。

执行：
    python examples/demo_file_mode.py
"""
from pathlib import Path
import datetime
import json
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from core.asr_service import ASRService
from core.text_service import TextService
from core.config import set_config_value, get_config_value

# 你自己的音频文件(16k 单声道 wav 优先)。
AUDIO_PATH = r"C:\Users\Hu\Downloads\未命名.wav"  # TODO: 修改为真实文件


def main():
    # 根据需求切换远程/本地
    # True 使用 DashScope 远程, False 使用 SenseVoiceSmall 本地
    set_config_value("USE_REMOTE_ASR", False)
    set_config_value("PERSIST_ENABLE", True)

    asr = ASRService()
    text = TextService()

    raw = asr.transcribe_file(AUDIO_PATH)
    print("[ASR]", raw)

    refined = text.refine(raw, asr_service=asr)
    print("[Refined]", refined)

    # 找到最新的 session json
    persist_dir = Path(get_config_value("PERSIST_DIR")) / datetime.date.today().isoformat()
    if not persist_dir.exists():
        print("未找到持久化目录:", persist_dir)
        return
    candidates = sorted(persist_dir.glob("*.json"))
    if not candidates:
        print("未生成 session json")
        return
    latest = candidates[-1]
    data = json.loads(latest.read_text(encoding="utf-8"))
    print("[Session JSON]", latest)
    print("  asr_phase.text:", data.get("asr_phase", {}).get("text"))
    print("  llm_phase.text:", data.get("llm_phase", {}).get("text"))


if __name__ == "__main__":
    main()
