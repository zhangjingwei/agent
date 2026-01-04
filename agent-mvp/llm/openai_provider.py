"""
OpenAI LLM提供商
"""

from langchain_openai import ChatOpenAI
from langchain_core.runnables import Runnable
from llm.base import LLMProvider


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
