"""
api/llm.py - DeepSeek 客户端封装
"""
import json
from typing import Optional, Any, AsyncIterator

from openai import OpenAI, AsyncOpenAI

from api.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    get_logger,
)

log = get_logger("chat")


class LLM:
    """DeepSeek 客户端封装。同时提供同步和异步方法。"""

    def __init__(self):
        if not DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置，请检查 .env")
        self.sync_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
        self.async_client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
        self.model = DEEPSEEK_MODEL
        log.info(f"LLM 客户端初始化 | model={self.model} | base_url={DEEPSEEK_BASE_URL}")

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Any:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            resp = self.sync_client.chat.completions.create(**kwargs)
            return resp.choices[0].message
        except Exception as e:
            log.error(f"LLM 调用失败 | {e}")
            raise

    async def stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[dict]:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        tool_calls_acc: dict[int, dict] = {}

        try:
            stream = await self.async_client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                finish = chunk.choices[0].finish_reason

                if delta.content:
                    yield {"type": "text", "delta": delta.content}

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            tool_calls_acc[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_acc[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_acc[idx]["function"]["arguments"] += tc.function.arguments

                if finish:
                    if tool_calls_acc:
                        tool_calls_list = [tool_calls_acc[i] for i in sorted(tool_calls_acc.keys())]
                        yield {"type": "tool_call", "tool_calls": tool_calls_list}
                    yield {"type": "done", "finish_reason": finish}
                    return
        except Exception as e:
            log.error(f"LLM 流式调用失败 | {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}