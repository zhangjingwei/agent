"""
OpenAI LLM提供商
"""

from langchain_openai import ChatOpenAI
from langchain_core.runnables import Runnable
from langchain_core.messages import BaseMessage
from typing import AsyncIterator, Dict, Any
from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI提供商"""

    def create_llm(self) -> Runnable:
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=self.config.get('temperature', 0.7),
            **self.config.get('extra_params', {})
        )

    def get_provider_name(self) -> str:
        return "openai"

    async def stream_chat(self, messages: list[BaseMessage], **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """OpenAI流式对话"""
        llm = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=self.config.get('temperature', 0.7),
            streaming=True,
            **self.config.get('extra_params', {})
        )

        async for chunk in llm.astream(messages):
            if chunk.content:
                yield {
                    "type": "content",
                    "content": chunk.content,
                    "done": False
                }

            if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                for tool_call in chunk.tool_calls:
                    yield {
                        "type": "tool_call_start",
                        "tool_call": {
                            "id": tool_call.get("id", ""),
                            "name": tool_call.get("name", ""),
                            "arguments": tool_call.get("args", {})
                        },
                        "done": False
                    }

    async def stream_chat_with_tools(self, messages: list[BaseMessage], tools: list, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """带工具的流式对话"""
        # 创建支持流式的LLM实例
        llm = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=self.config.get('temperature', 0.7),
            streaming=True,  # 直接设置streaming=True
            **self.config.get('extra_params', {})
        )

        # 绑定工具
        llm_with_tools = llm.bind_tools(tools)

        async for chunk in llm_with_tools.astream(messages):
            if chunk.content:
                yield {
                    "type": "content",
                    "content": chunk.content,
                    "done": False
                }

            if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                for tool_call in chunk.tool_calls:
                    yield {
                        "type": "tool_call_start",
                        "tool_call": tool_call,
                        "done": False
                    }
