"""
Anthropic LLM提供商
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import Runnable
from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic提供商"""

    def create_llm(self) -> Runnable:
        return ChatAnthropic(
            model=self.model,
            api_key=self.api_key,
            temperature=self.config.get('temperature', 0.7),
            **self.config.get('extra_params', {})
        )

    def get_provider_name(self) -> str:
        return "anthropic"
