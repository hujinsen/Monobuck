"""示例：流式阻塞模式（分片迭代 + 最终保存 + refine）

将大音频文件分片送入识别，结束后一次性返回最终文本并持久化。
执行：
    python examples/demo_stream_finalize.py
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterator
import wave
import datetime, json
import sys
sys.path.append(".")
from core.asr_service import ASRService
from core.text_service import TextService
from core.config import set_config_value, get_config_value
import pyaudio

AUDIO_PATH = r"C:\Users\Hu\Downloads\未命名.wav"  
CHUNK_MS = 120  # 每次发送的时间长度
SAMPLE_RATE = 16000  # 期望的采样率


def wav_chunk_iter(path: str, chunk_ms: int, sample_rate: int) -> Iterator[bytes]:
    with wave.open(path, "rb") as wf:
        if wf.getnchannels() != 1:
            raise RuntimeError("示例假设单声道，当前文件声道数 !=1")
        if wf.getsampwidth() != 2:
            raise RuntimeError("示例假设 16-bit PCM，当前文件采样宽度不为2")
        if wf.getframerate() != sample_rate:
            raise RuntimeError(f"采样率不匹配: {wf.getframerate()} != {sample_rate}")
        bytes_per_ms = sample_rate * 2 // 1000  # 16-bit 单声道
        bytes_per_chunk = bytes_per_ms * chunk_ms
        frames_per_chunk = bytes_per_chunk // 2
        while True:
            data = wf.readframes(frames_per_chunk)
            if not data:
                break
            yield data

#从麦克风读取音频流
def wav_mic_chunk_iter() -> Iterator[bytes]:
    """从麦克风读取音频流"""
    sample_rate = get_config_value("ASR_SAMPLE_RATE")
    chunk_ms = get_config_value("CHUNK_MS")
    print(f'sample_rate: {sample_rate}, chunk_ms: {chunk_ms}')
    chunk_size = int(sample_rate * chunk_ms / 1000)  # 每帧采样数
    print(f'chunk_size: {chunk_size}')
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=sample_rate,
                        input=True,
                        frames_per_buffer=chunk_size)
    try:
        while True:
            data = stream.read(chunk_size, exception_on_overflow=False)
            # print(f"read {len(data)} bytes")
            yield data
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()



def main():
    set_config_value("USE_REMOTE_ASR", True)#远程模型OK
    # set_config_value("USE_REMOTE_ASR", False) #本地模型OK
    set_config_value("PERSIST_ENABLE", True) #

    asr = ASRService()
    
    
    text = TextService()

    # 经过大量测试，下面的方法可以进行本地和远程识别，给出最终的识别结果
    result = {}
    try:
        for text_dict in asr.transcribe_stream(wav_mic_chunk_iter()):
            # print(text_dict['text'], text_dict['is_final'])
            if text_dict['is_final']:
                result['text'] = text_dict['text']
                result['is_final'] = text_dict['is_final']
                
    except KeyboardInterrupt:
        print("用户中断")
        if result:
            print(result)

        # if text_dict['is_final']:
        #     print(text_dict['text'])
    # print("[ASR Final]", final_text)
    # refined = text.refine(final_text, asr_service=asr)
    # print("[Refined]", refined)

    # persist_dir = Path(get_config_value("PERSIST_DIR")) / datetime.date.today().isoformat()
    # if persist_dir.exists():
    #     latest = max(persist_dir.glob("*.json"), default=None)
    #     if latest:
    #         data = json.loads(latest.read_text(encoding="utf-8"))
    #         print("[Session]", latest.name)
    #         print("  asr_phase.text:", data.get("asr_phase", {}).get("text"))
    #         print("  llm_phase.text:", data.get("llm_phase", {}).get("text"))
    #     else:
    #         print("未找到会话 JSON 文件")
    # else:
    #     print("持久化目录不存在:", persist_dir)


if __name__ == "__main__":
    main()
