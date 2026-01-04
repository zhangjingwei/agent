"""
LLM工厂 - 创建不同提供商的LLM实例
"""

from typing import Dict, Any, Optional
from langchain_core.runnables import Runnable
from .base import LLMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .siliconflow_provider import SiliconFlowProvider


class LLMFactory:
    """LLM工厂类"""

    _providers = {
        'openai': OpenAIProvider,
        'anthropic': AnthropicProvider,
        'siliconflow': SiliconFlowProvider
    }

    @classmethod
    def create_llm(cls, provider: str, api_key: str, model: str, **config) -> Runnable:
        """创建LLM实例"""
        if provider not in cls._providers:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        provider_class = cls._providers[provider]
        llm_provider = provider_class(api_key=api_key, model=model, **config)

        if not llm_provider.validate_config():
            raise ValueError(f"Invalid configuration for provider: {provider}")

        return llm_provider.create_llm()

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """获取支持的提供商列表"""
        return list(cls._providers.keys())

    @classmethod
    def register_provider(cls, name: str, provider_class):
        """注册新的提供商"""
        cls._providers[name] = provider_class
