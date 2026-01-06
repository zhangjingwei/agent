"""
工具执行器
"""

from typing import Dict, Any, Optional
from .registry import ToolRegistry


class ToolExecutor:
    """工具执行器"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具"""
        tool = self.registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        return await tool.execute(**arguments)

    async def execute_batch(self, tool_calls: list) -> Dict[str, Any]:
        """批量执行工具"""
        results = {}
        for tool_call in tool_calls:
            try:
                result = await self.execute(
                    tool_call["name"],
                    tool_call["arguments"]
                )
                results[tool_call["id"]] = {"success": True, "result": result}
            except Exception as e:
                results[tool_call["id"]] = {"success": False, "error": str(e)}

        return results
