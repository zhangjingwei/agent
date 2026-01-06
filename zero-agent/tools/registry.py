"""
工具注册器
"""

from typing import Dict, Any, List, Optional
from .base import Tool


class ToolRegistry:
    """工具注册器"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """注销工具"""
        self._tools.pop(name, None)

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def get_all_tools(self) -> List[Tool]:
        """获取所有工具"""
        return list(self._tools.values())

    def get_langchain_tools(self) -> List[Any]:
        """获取所有LangChain工具"""
        tools = []
        for tool in self._tools.values():
            if hasattr(tool, 'langchain_tool'):
                tools.append(tool.langchain_tool)
            elif hasattr(tool, 'to_langchain_tool'):
                tools.append(tool.to_langchain_tool())
        return tools

    def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools

    def clear(self) -> None:
        """清空所有工具"""
        self._tools.clear()