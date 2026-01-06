"""
SiliconFlow LLM提供商
"""

from langchain_openai import ChatOpenAI
from langchain_core.runnables import Runnable
from .base import LLMProvider


class SiliconFlowProvider(LLMProvider):
    """SiliconFlow提供商"""

    def create_llm(self) -> Runnable:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=self.config.get('temperature', 0.7),
            base_url="https://api.siliconflow.cn/v1",
            **self.config.get('extra_params', {})
        )

        return llm

    def get_provider_name(self) -> str:
        return "siliconflow"
