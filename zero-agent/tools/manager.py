"""
工具管理器 - 统一管理工具的创建和注册
"""

import importlib
import logging
from typing import Dict, Any, Optional

from .base import Tool, FunctionTool
from .registry import ToolRegistry
from .mcp.client import MCPClient
from .mcp.tool import MCPTool
from config.models import ToolConfig, MCPConfig, MCPToolConfig

logger = logging.getLogger(__name__)


class ToolManager:
    """工具管理器"""

    def __init__(self):
        self._tool_classes = {}  # 存储工具类映射
        self._mcp_clients: Dict[str, MCPClient] = {}  # MCP 客户端缓存

    def register_tool_class(self, name: str, tool_class: type):
        """注册工具类"""
        self._tool_classes[name] = tool_class
        logger.info(f"已注册工具类: {name}")

    def create_tool_from_config(self, config: ToolConfig) -> Tool:
        """
        根据配置创建工具实例

        Args:
            config: 工具配置

        Returns:
            工具实例

        Raises:
            ValueError: 当配置无效或工具创建失败时
        """
        handler = config.handler
        handler_type = handler.get("type")

        if handler_type == "function":
            return self._create_function_tool(config)
        elif handler_type == "class":
            return self._create_class_tool(config)
        else:
            raise ValueError(f"不支持的工具类型: {handler_type}")

    def _create_function_tool(self, config: ToolConfig) -> FunctionTool:
        """创建函数类型工具"""
        handler = config.handler
        module_path = handler.get("module")
        function_name = handler.get("function")

        if not module_path or not function_name:
            raise ValueError(f"函数工具配置缺少必要字段: module={module_path}, function={function_name}")

        try:
            # 动态导入模块
            module = importlib.import_module(module_path)
            func = getattr(module, function_name)

            logger.info(f"创建函数工具: {config.name} -> {module_path}.{function_name}")
            return FunctionTool(
                name=config.name,
                description=config.description,
                func=func,
                parameters_schema=config.parameters
            )
        except (ImportError, AttributeError) as e:
            raise ValueError(f"无法导入函数工具 {config.name}: {str(e)}")

    def _create_class_tool(self, config: ToolConfig) -> Tool:
        """创建类类型工具"""
        handler = config.handler
        class_name = handler.get("class")
        module_path = handler.get("module", "tools")

        if not class_name:
            raise ValueError(f"类工具配置缺少class字段: {config.name}")

        try:
            # 动态导入模块和类
            module = importlib.import_module(module_path)
            tool_class = getattr(module, class_name)

            logger.info(f"创建类工具: {config.name} -> {module_path}.{class_name}")
            return tool_class()
        except (ImportError, AttributeError) as e:
            raise ValueError(f"无法导入类工具 {config.name}: {str(e)}")

    def register_tools_from_config(self, registry: ToolRegistry, configs: list[ToolConfig]):
        """
        从配置列表注册工具到注册器

        Args:
            registry: 工具注册器
            configs: 工具配置列表
        """
        for config in configs:
            if not config.enabled:
                logger.info(f"跳过禁用的工具: {config.name}")
                continue

            try:
                tool_instance = self.create_tool_from_config(config)
                registry.register(tool_instance)
                logger.info(f"成功注册工具: {config.name}")
            except Exception as e:
                logger.error(f"注册工具失败 {config.name}: {str(e)}")
                # 可以选择继续注册其他工具，或者抛出异常
                # 这里选择继续，以免一个工具失败影响其他工具

    async def register_mcp_tools(self, registry: ToolRegistry,
                                mcp_configs: list[MCPConfig],
                                mcp_tool_configs: list[MCPToolConfig]):
        """
        注册MCP工具

        Args:
            registry: 工具注册器
            mcp_configs: MCP服务器配置列表
            mcp_tool_configs: MCP工具配置列表
        """
        for config in mcp_configs:
            if not config.enabled:
                logger.info(f"跳过禁用的MCP服务器: {config.name}")
                continue

            try:
                # 创建并连接MCP客户端
                client = MCPClient(config)
                await client.connect()
                self._mcp_clients[config.id] = client

                # 获取工具列表
                tools = await client.list_tools()
                logger.info(f"MCP服务器 {config.id} 提供 {len(tools)} 个工具")

                # 为每个工具创建包装器并注册
                for tool_info in tools:
                    tool_config = self._find_mcp_tool_config(
                        mcp_tool_configs, config.id, tool_info['name']
                    )

                    # 检查是否启用
                    if tool_config and not tool_config.enabled:
                        continue

                    try:
                        # 创建MCP工具包装器
                        mcp_tool = MCPTool(config, tool_info)

                        # 如果有描述覆盖，使用覆盖的描述
                        if tool_config and tool_config.description_override:
                            mcp_tool.description = tool_config.description_override

                        # 注册到工具注册器
                        registry.register(mcp_tool)
                        logger.info(f"成功注册MCP工具: {mcp_tool.name}")

                    except Exception as e:
                        logger.error(f"注册MCP工具失败 {config.id}.{tool_info['name']}: {str(e)}")
                        # 继续注册其他工具

            except Exception as e:
                logger.error(f"连接MCP服务器失败 {config.id}: {str(e)}")
                logger.warning(f"MCP服务器 {config.id} 的工具将不可用，请检查服务器配置或网络连接")




    def _find_mcp_tool_config(self, configs: list[MCPToolConfig],
                             server_id: str, tool_name: str) -> Optional[MCPToolConfig]:
        """查找MCP工具配置"""
        for config in configs:
            if config.server_id == server_id and config.tool_name == tool_name:
                return config
        return None

    async def cleanup_mcp_clients(self):
        """清理MCP客户端连接"""
        errors = []
        client_ids = list(self._mcp_clients.keys())
        
        for client_id, client in list(self._mcp_clients.items()):
            try:
                await client.disconnect()
                logger.debug(f"MCP客户端 {client_id} 清理成功")
            except Exception as e:
                error_msg = f"清理MCP客户端 {client_id} 失败: {str(e)}"
                logger.warning(error_msg, exc_info=True)
                errors.append(error_msg)

        self._mcp_clients.clear()
        
        if errors:
            logger.warning(f"MCP客户端清理完成，但有 {len(errors)}/{len(client_ids)} 个错误")
        else:
            logger.info(f"已清理所有MCP客户端连接（共 {len(client_ids)} 个）")
