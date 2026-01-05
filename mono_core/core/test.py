
from pathlib import Path

# 获取当前文件的父目录
current_dir = Path(__file__).resolve().parent

# 获取项目根目录（上上级目录）
project_root = Path(__file__).resolve().parent.parent

# 构建模型路径
MODEL_DIR = project_root / "iic" /"SenseVoiceSmall" # 本地模型路径
# MODEL_DIR = r"D:\code_trip\mono_core\iic\SenseVoiceSmall"  
MODEL_DEFINE = current_dir / "model.py"  # 本地模型定义代码路径

print(f"模型路径: {MODEL_DIR}")
print(f"模型定义代码路径: {MODEL_DEFINE}")

if not MODEL_DIR.exists():
        raise FileNotFoundError(f"模型目录不存在: {MODEL_DIR}")
if not MODEL_DEFINE.exists():
    raise FileNotFoundError(f"模型定义代码不存在: {MODEL_DEFINE}")


# 整文件
from core.asr_service import ASRService
from core.text_service import TextService

asr = ASRService()
text = TextService()
raw = asr.transcribe_file("sample.wav")          # 自动创建 session
refined = text.refine(raw, scene="default", asr_service=asr)  # 补全 llm_phase

# 麦克风
raw_mic = asr.transcribe_microphone_finalize()
refined_mic = text.refine(raw_mic, asr_service=asr)

# 流式（收集后）
final_text = "。".join(collected_sentences)
asr.create_stream_session(final_text, pcm_bytes=collected_pcm)
refined_stream = text.refine(final_text, asr_service=asr)