"""文本生成与规范化服务实现。

提供两种策略：
1. RemoteLLMStrategy 调用阿里云 DashScope 通义千问系列模型进行生成与润色。
2. LocalLLMStrategy 占位，实现最简单的拼接或清洗，方便离线环境。

核心公开方法：
    generate(messages, model=..., temperature=..., top_p=...) -> str
    refine(raw_text) -> str  # 针对 ASR 结果做标点、格式规范化（不添加新事实）

messages 兼容 DashScope:
    [{"role": "system|user|assistant", "content": "..."}, ...]

注意：本模块不会缓存结果；可在上层引入缓存（LRU/Redis）避免重复生成。
"""

from __future__ import annotations

import os
from typing import List, Dict, Any

from core.base_ai_service import BaseTextService
from core.config import get_config_value, reload_config


class RemoteLLMStrategy:
    DEFAULT_MODEL = "qwen-plus"

    def __init__(self) -> None:
        import dashscope
        from dashscope import Generation
        self._dashscope = dashscope
        self._Generation = Generation

    # --- core generation ---
    def generate(self, messages: List[Dict[str, str]], *, model: str | None = None,
                 temperature: float | None = None,
                 top_p: float | None = None) -> str:
        api_key = get_config_value("DASHSCOPE_API_KEY")
        if not api_key:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY，请在 config.json 中配置或使用 set_config_value，无法调用远程 LLM。")
        self._dashscope.api_key = api_key

        payload_model = model or self.DEFAULT_MODEL
        kwargs: Dict[str, Any] = {"result_format": "message"}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if top_p is not None:
            kwargs["top_p"] = top_p
        resp = self._Generation.call(  # type: ignore[assignment]
            model=payload_model,
            messages=messages,
            **kwargs,
        )
        status_code = getattr(resp, "status_code", 200)
        if status_code != 200:
            raise RuntimeError(
                f"LLM错误 http={status_code} code={getattr(resp,'code',None)} msg={getattr(resp,'message',None)}"
            )
        output = getattr(resp, "output", None)
        if output and getattr(output, "choices", None):
            first = output.choices[0]
            msg = getattr(first, "message", None)
            content = getattr(msg, "content", None)
            if isinstance(content, str):
                return content
        raise RuntimeError("LLM响应结构异常，缺少有效 choices/message.content")

    def refine(self, raw_text: str) -> str:
        
        messages = [{"role": "system", "content": get_config_value("prompts").get("system","")},
           
            {"role": "user", "content": raw_text},
        ]
        # print(f"原始消息: {messages}")
        return self.generate(messages, temperature=0.3)


class LocalLLMStrategy:
    """本地 LLM 占位策略：快速返回，不调用远程。"""

    def generate(self, messages: List[Dict[str, str]], *, model: str | None = None,
                 temperature: float | None = None,
                 top_p: float | None = None) -> str:  # noqa: D401
        # 模拟返回：取最后一个 user 内容加前缀
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"(local llm mock) {last_user}".strip()

    def refine(self, raw_text: str) -> str:
        # 最简单的去首尾空白；可进一步添加基本标点处理
        return raw_text.strip()


class TextService(BaseTextService):
    """文本服务统一入口。

    通过配置 USE_REMOTE_LLM 控制使用远程或本地策略：
        set_config_value("USE_REMOTE_LLM", False) -> 切换至 LocalLLMStrategy
    """

    def __init__(self) -> None:
        use_remote = True
        try:
            flag = get_config_value("USE_REMOTE_LLM")
            if flag is not None:
                use_remote = bool(flag)
        except Exception:
            pass
        self._strategy = RemoteLLMStrategy() if use_remote else LocalLLMStrategy()

    # --- facade methods ---TODO:后续研究下facade methods--
    def generate(self, messages: List[Dict[str, str]], *, model: str | None = None,
                 temperature: float | None = None,
                 top_p: float | None = None) -> str:
        # 基础校验：所有 message 必须含有 role 与 content
        for m in messages:
            if "role" not in m or "content" not in m:
                raise ValueError(f"message 缺少 role 或 content: {m}")
        return self._strategy.generate(messages, model=model, temperature=temperature, top_p=top_p)

    def refine(self, raw_text: str, scene: str = "default", asr_service: Any = None) -> str:
        if not isinstance(raw_text, str):
            raise TypeError("raw_text 必须是字符串")
        refined = self._strategy.refine(raw_text)
        return refined


# 使用示例（同步生成）:
# svc = TextService()
# print(svc.generate([
#     {"role": "system", "content": "You are a helpful assistant."},
#     {"role": "user", "content": "请用一句话解释量子计算。"}
# ]))
