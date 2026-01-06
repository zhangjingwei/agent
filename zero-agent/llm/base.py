"""
LLM基础接口
"""

from abc import ABC, abstractmethod
from langchain_core.runnables import Runnable


class LLMProvider(ABC):
    """LLM提供商基础接口"""

    def __init__(self, api_key: str, model: str, **kwargs):
        self.api_key = api_key
        self.model = model
        self.config = kwargs

    @abstractmethod
    def create_llm(self) -> Runnable:
        """创建LLM实例"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """获取提供商名称"""
        pass

    def validate_config(self) -> bool:
        """验证配置"""
        return bool(self.api_key and self.model)
