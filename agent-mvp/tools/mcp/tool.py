"""
MCP工具包装器
"""

from typing import Dict, Any, Optional
import logging

from tools.base import Tool
from .client import MCPClient
from config.models import MCPConfig

logger = logging.getLogger(__name__)


class MCPTool(Tool):
    """MCP工具包装器"""

    def __init__(self, server_config: MCPConfig, tool_info: Dict[str, Any]):
        self.server_config = server_config
        self.tool_info = tool_info
        self._client: Optional[MCPClient] = None

        # 使用服务器ID和工具名作为唯一标识
        tool_name = f"{server_config.id}_{tool_info['name']}"
        description = tool_info.get('description', '')

        super().__init__(tool_name, description)

    async def _get_client(self) -> MCPClient:
        """获取或创建客户端"""
        if self._client is None:
            self._client = MCPClient(self.server_config)
            await self._client.connect()
        return self._client

    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数schema"""
        schema = self.tool_info.get('inputSchema', {})
        # 确保返回有效的JSON Schema格式
        if not schema:
            schema = {
                "type": "object",
                "properties": {},
                "required": []
            }
        return schema

    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        client = await self._get_client()
        # 提取实际工具名（去掉服务器前缀）
        actual_tool_name = self.tool_info['name']
        result = await client.call_tool(actual_tool_name, kwargs)
        return result
