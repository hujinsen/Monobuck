"""文件语音识别 + 文本规范化最简示例。

用法:
    python -m examples.run_pipeline <audio_file>

准备:
    - 16kHz 单声道 wav/pcm/mp3 等（若非 16kHz：ffmpeg 转换 ）
    - 已设置环境变量 DASHSCOPE_API_KEY 或通过 set_config_value 注入。

转换示例 (PowerShell 下装有 ffmpeg):
    ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav
"""
from __future__ import annotations

import sys
from core.asr_service import ASRService
from core.text_service import TextService


def main():
    if len(sys.argv) < 2:
        print("用法: python -m examples.run_pipeline <audio_file>")
        return
    audio_file = sys.argv[1]

    asr = ASRService()
    text = TextService()
    try:
        raw = asr.transcribe_file(audio_file)
    except Exception as e:
        print(f"识别失败: {e}")
        return
    refined = text.refine(raw)

    print("=== 结果 ===")
    print("原始识别：")
    print(raw)
    print("\n规范化：")
    print(refined)


if __name__ == "__main__":
    main()
