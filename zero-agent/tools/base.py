"""
工具基础接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
import importlib
import asyncio
from langchain_core.tools import tool


class Tool(ABC):
    """工具基础类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        pass

    def to_langchain_tool(self):
        """转换为LangChain工具"""
        from pydantic import create_model, Field

        # 获取参数schema
        schema = self.get_parameters_schema()

        # 创建Pydantic模型作为参数schema
        field_definitions = {}
        required_fields = schema.get('required', [])

        for prop_name, prop_info in schema.get('properties', {}).items():
            field_type = str  # 默认字符串类型
            field_default = ... if prop_name in required_fields else None

            # 根据schema类型映射Python类型
            prop_type = prop_info.get('type', 'string')
            if prop_type == 'integer':
                field_type = int
            elif prop_type == 'number':
                field_type = float
            elif prop_type == 'boolean':
                field_type = bool
            # string类型保持str

            field_definitions[prop_name] = (
                field_type,
                Field(default=field_default, description=prop_info.get('description', ''))
            )

        # 创建动态Pydantic模型
        ArgsModel = create_model(f'{self.name}Args', **field_definitions)

        async def tool_func(**kwargs):
            return await self.execute(**kwargs)

        tool_func.__name__ = self.name
        tool_func.__doc__ = self.description

        # 使用正确的参数schema创建工具
        return tool(tool_func, args_schema=ArgsModel)

    def get_parameters_schema(self):
        """获取参数schema，子类可以重写"""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    @property
    def langchain_tool(self):
        """获取LangChain工具实例"""
        return self.to_langchain_tool()


class FunctionTool(Tool):
    """函数类型工具包装类"""

    def __init__(self, name: str, description: str, func: Callable, parameters_schema: Dict[str, Any]):
        super().__init__(name, description)
        self.func = func
        self._parameters_schema = parameters_schema

    def get_parameters_schema(self):
        """获取参数schema"""
        return self._parameters_schema

    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        # 检查函数是否是异步的
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        else:
            # 对于同步函数，在线程池中运行
            import concurrent.futures
            import functools

            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # 使用functools.partial来处理关键字参数
                func_with_args = functools.partial(self.func, **kwargs)
                return await loop.run_in_executor(executor, func_with_args)