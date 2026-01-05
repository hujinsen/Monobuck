"""服务编排入口。

将语音识别 (ASRService) 与文本规范化 (TextService) 组合形成完整流水线：
	音频 -> ASR 初始文本 -> refine 规范化文本

提供同步整文件处理与流式增量处理两个接口。
"""

from __future__ import annotations

from typing import Iterator, Generator, Dict, Any
import sys

from core.asr_service import ASRService
from core.text_service import TextService
from core.config import reload_config, get_config_value

class ServiceRuntime:
	"""统一的服务编排类 (语音识别 + 文本规范化)。

	模式说明：
	1. `process_file` 整文件：直接识别全文，再调用 refine。
	2. `process_stream` 流式增量：仅返回 ASR 原始增量，不再实时调用 refine。
	3. `process_stream_finalize` 阻塞式流：收集所有最终句子 (is_final=True)，结束后一次性 refine。

	设计理由：避免对尚未稳定的中间片段频繁调用大模型；提高一致性与降低成本。
	"""

	def __init__(self) -> None:
		self.asr = ASRService()
		self.text = TextService()

	# --- file mode ---
	def process_file(self, audio_path: str, persist: bool = True) -> str:
		"""整文件识别后直接规范化。"""
		raw = self.asr.transcribe_file(audio_path)
		print(f"raw: {raw}")
		# 传入 asr_service 以便触发会话持久化的 LLM 阶段写入
		refined = self.text.refine(raw, asr_service=self.asr)
		return refined

	# --- streaming mode (仅返回最终句子) ---
	def process_stream(self, audio_iter: Iterator[bytes]) -> Generator[Dict[str, Any], None, None]:
		"""流式识别：只产出最终句子，不返回中间增量。

		每次 yield:
		{
		  "sentence": 最终句文本,
		  "begin_time": 句开始(ms),
		  "end_time": 句结束(ms)
		}
		"""
		for part in self.asr.transcribe_stream(audio_iter):
			if part.get("is_final") and part.get("text"):
				yield {
					"sentence": str(part["text"]).strip(),
					"begin_time": part.get("begin_time"),
					"end_time": part.get("end_time"),
				}

	def process_stream_finalize(self, audio_iter: Iterator[bytes]) -> Dict[str, Any]:
		"""
    	阻塞流式执行音频处理流程，生成最终文本结果。
		Args:
			audio_iter (Iterator[bytes]): 音频数据迭代器，可以是文件迭代器或麦克风实时音频流
		Returns:
			Dict[str, Any]: 包含处理结果的字典，包含以下键：
				- raw_joined (str): ASR识别后的原始完整文本
				- refined (str): 经过文本精炼处理后的文本
				- sentences (List[str]): 按句号分割后的句子列表
		"""
		final_text = self.asr.transcribe_stream_finalize(audio_iter)
		refined = self.text.refine(final_text, asr_service=self.asr) if final_text else ""
		sentences = final_text.split("。") if final_text else []
		return {"raw_joined": final_text, "refined": refined, "sentences": sentences}

	def process_microphone_stream_finalize(self) -> Dict[str, Any]:
		"""
			处理麦克风实时识别会话，收集最终句子并规范化结果。
			Returns:
				Dict[str, Any]: 包含以下键的字典:
					- raw_joined: 原始拼接的句子字符串
					- refined: 经过文本精炼处理后的结果
					- sentences: 识别出的最终句子列表
					- interrupted: 是否被键盘中断(Ctrl+C)
			
			Raises:
				KeyboardInterrupt: 当用户按下Ctrl+C时中断处理
		"""
		sentences: list[str] = []
		interrupted = False
		try:
			for part in self.asr.transcribe_microphone():
				
				if part.get("is_final") and part.get("text"):
					sentences.append(str(part["text"]).strip())
					print(f"[final] {part['text']}")
		except KeyboardInterrupt:
			interrupted = True
		raw_joined = "。".join(sentences)
		if raw_joined and get_config_value("PERSIST_ENABLE"):
			# 使用麦克风 finalize 专属方法以便写入 PCM
			self.asr.transcribe_microphone_finalize()  # 已在内部完成会话写入
		refined = self.text.refine(raw_joined, asr_service=self.asr) if raw_joined else ""
		return {"raw_joined": raw_joined, "refined": refined, "sentences": sentences, "interrupted": interrupted}



if __name__ == "__main__":  # pragma: no cover
	rt = ServiceRuntime()
	# for item in rt.process_stream(_demo_audio_iter()):
	# 	print(item)
	# file_path = r"D:\code_trip\alibabacloud-bailian-speech-demo\samples\sample-data\what_color.wav"
	# print(rt.process_file(file_path))
	# reload_config()
	res = rt.process_microphone_stream_finalize()
	print(res)
	# rt.asr.start()
	# print("asr started")
	# import time
	
	
	# result = rt.process_file(r"C:\Users\Hu\Downloads\未命名.wav")
	# print(result)
	


	rt.asr.stop()
	print("asr stopped")

	# result = rt.process_microphone_with_keys()
	# print(result)