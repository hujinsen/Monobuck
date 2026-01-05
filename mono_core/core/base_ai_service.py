"""统一的基础抽象层。

本文件汇总所有 AI 服务的抽象接口，便于在具体实现（远程/本地策略）之间保持一致。

设计要点（来自前期讨论汇总）:
1. 语音识别分为整文件与流式两类；流式产出增量结果。
2. 文本服务分为通用生成 generate 与 ASR 结果规范化 refine 两类；规范化是生成的一个特化场景。
3. 后续可在 BaseAIService 中加入统一的日志、指标、重试、熔断、限流等横切能力。
"""

from abc import ABC, abstractmethod
from typing import Iterator, Generator, Dict, Any, List


class BaseAIService(ABC):
    """Root base class for all AI oriented services.

    预留扩展点：
    - metrics/logging hook
    - retry & rate limiting
    - tracing/span context
    """

    pass


class BaseSpeechService(BaseAIService):
    """语音识别统一抽象接口。

    Contract:
    - transcribe_file(path) -> str : 阻塞式整文件识别，返回完整文本（或空字符串）。
    - transcribe_stream(audio_iter) -> Generator[Dict[str, Any]] : 流式识别，逐步返回字典，至少包含 text 与 is_final。

    推荐结果数据结构：
    {"text": str, "is_final": bool, "begin_time": ms|None, "end_time": ms|None}
    """

    @abstractmethod
    def transcribe_file(self, file_path: str) -> str:
        raise NotImplementedError()

    @abstractmethod
    def transcribe_stream(self, audio_stream: Iterator[bytes]) -> Generator[Dict[str, Any], None, None]:
        raise NotImplementedError()
    
    @abstractmethod
    def start(self) -> None:
        """启动识别服务，准备接受音频输入。"""
        raise NotImplementedError()
    
    @abstractmethod
    def stop(self) -> None:
        """停止识别，停止后才能进行文本规范化。"""
        raise NotImplementedError()


class BaseTextService(BaseAIService):
    """文本生成与规范化统一抽象接口。

    Contract:
    - generate(messages, model=..., temperature=..., top_p=...) -> str : 通用对话/生成。
    - refine(raw_text) -> str : 针对 ASR 口语化、无标点文本进行规范化润色，不引入新事实。

    messages 结构与通义千问兼容：[{"role": "system|user|assistant", "content": "..."}, ...]
    """

    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], *, model: str | None = None,
                 temperature: float | None = None,
                 top_p: float | None = None) -> str:
        raise NotImplementedError()

    @abstractmethod
    def refine(self, raw_text: str) -> str:
        raise NotImplementedError()


