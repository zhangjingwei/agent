"""
工具管理器 - 统一管理工具的创建和注册
"""

import importlib
import logging
import asyncio
import time
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

    def _build_mcp_summary(
        self,
        enabled_servers: int,
        success_servers: int,
        failed_servers: int,
        registered_tools: int,
        failed_server_ids: list[str]
    ) -> Dict[str, Any]:
        """构建 MCP 初始化摘要。"""
        return {
            "enabled_servers": enabled_servers,
            "success_servers": success_servers,
            "failed_servers": failed_servers,
            "registered_tools": registered_tools,
            "failed_server_ids": failed_server_ids,
        }

    async def _cleanup_failed_mcp_client(self, server_id: str, client: Optional[MCPClient], stage: str):
        """在 MCP 初始化失败时尽力清理客户端资源。"""
        if client is None:
            return

        try:
            await client.disconnect()
        except Exception:
            logger.debug(f"{stage}后清理 MCP 客户端失败 {server_id}", exc_info=True)
        finally:
            self._mcp_clients.pop(server_id, None)

    async def register_mcp_tools(self, registry: ToolRegistry,
                                mcp_configs: list[MCPConfig],
                                mcp_tool_configs: list[MCPToolConfig]) -> Dict[str, Any]:
        """
        注册MCP工具（优化：并行初始化多个 MCP 服务器）

        Args:
            registry: 工具注册器
            mcp_configs: MCP服务器配置列表
            mcp_tool_configs: MCP工具配置列表
        """
        enabled_configs = [config for config in mcp_configs if config.enabled]
        if not enabled_configs:
            logger.info("没有启用的 MCP 服务器，跳过注册")
            return self._build_mcp_summary(0, 0, 0, 0, [])
        
        enabled_server_count = len(enabled_configs)
        logger.info(f"开始并行初始化 {enabled_server_count} 个 MCP 服务器")
        start_time = time.time()
        
        async def init_mcp_server(config: MCPConfig) -> tuple[str, Optional[int], Optional[str]]:
            """初始化单个 MCP 服务器，返回 (server_id, registered_count, error_message)。"""
            server_timeout_seconds = max(3.0, float(config.timeout) / 1000.0 + 2.0)
            client: Optional[MCPClient] = None

            async def _initialize_server() -> tuple[str, Optional[int], Optional[str]]:
                # 创建并连接MCP客户端
                nonlocal client
                client = MCPClient(config)
                await client.connect()

                # 获取工具列表
                tools = await client.list_tools()
                tool_count = len(tools)
                logger.info(f"MCP服务器 {config.id} 初始化成功，提供 {tool_count} 个工具")

                # 为每个工具创建包装器并注册
                registered_count = 0
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
                        registered_count += 1
                        logger.info(f"成功注册MCP工具: {mcp_tool.name}")

                    except Exception as e:
                        logger.error(f"注册MCP工具失败 {config.id}.{tool_info['name']}: {str(e)}")
                        # 继续注册其他工具

                if registered_count == 0:
                    logger.warning(f"MCP服务器 {config.id} 未注册任何工具，将以降级模式继续运行")

                # 只有完成初始化后才纳入可清理客户端集合
                self._mcp_clients[config.id] = client
                return (config.id, registered_count, None)

            try:
                return await asyncio.wait_for(_initialize_server(), timeout=server_timeout_seconds)
            except asyncio.TimeoutError:
                await self._cleanup_failed_mcp_client(config.id, client, "超时")
                error_msg = (
                    f"初始化超时（>{server_timeout_seconds:.1f}s）"
                )
                logger.error(f"连接MCP服务器失败 {config.id}: {error_msg}")
                logger.warning(f"MCP服务器 {config.id} 的工具将不可用，请检查服务器配置或网络连接")
                return (config.id, None, error_msg)
            except Exception as e:
                await self._cleanup_failed_mcp_client(config.id, client, "异常")
                logger.error(f"连接MCP服务器失败 {config.id}: {str(e)}")
                logger.warning(f"MCP服务器 {config.id} 的工具将不可用，请检查服务器配置或网络连接")
                return (config.id, None, str(e))
        
        # 并行执行所有初始化任务
        try:
            results = await asyncio.gather(
                *[init_mcp_server(config) for config in enabled_configs],
                return_exceptions=True
            )
            
            # 统计结果（过滤掉 CancelledError）
            valid_results = [r for r in results if not isinstance(r, asyncio.CancelledError)]
            success_count = sum(1 for r in valid_results if isinstance(r, tuple) and r[2] is None)
            fail_count = len(valid_results) - success_count
            total_tools = sum(r[1] for r in valid_results if isinstance(r, tuple) and r[1] is not None)
            failed_server_ids = [
                r[0] for r in valid_results if isinstance(r, tuple) and r[2] is not None
            ]
            
            # 检查是否有 CancelledError
            cancelled_count = sum(1 for r in results if isinstance(r, asyncio.CancelledError))
            if cancelled_count > 0:
                logger.warning(f"{cancelled_count} 个 MCP 服务器初始化被取消")
            
            elapsed_time = time.time() - start_time
            logger.info(f"MCP 服务器初始化完成: {success_count} 成功, {fail_count} 失败, 注册 {total_tools} 个工具, 耗时: {elapsed_time:.2f}秒")
            if failed_server_ids:
                logger.warning(
                    "MCP降级运行，以下服务器不可用: %s",
                    ", ".join(failed_server_ids)
                )
            return self._build_mcp_summary(
                enabled_servers=enabled_server_count,
                success_servers=success_count,
                failed_servers=fail_count,
                registered_tools=total_tools,
                failed_server_ids=failed_server_ids,
            )
            
        except asyncio.CancelledError:
            logger.warning("MCP 服务器初始化被取消，继续执行")
            failed_server_ids = [config.id for config in enabled_configs]
            return self._build_mcp_summary(
                enabled_servers=enabled_server_count,
                success_servers=0,
                failed_servers=enabled_server_count,
                registered_tools=0,
                failed_server_ids=failed_server_ids,
            )
        except Exception as e:
            logger.error(f"MCP 服务器并行初始化过程中出错: {str(e)}", exc_info=True)
            failed_server_ids = [config.id for config in enabled_configs]
            return self._build_mcp_summary(
                enabled_servers=enabled_server_count,
                success_servers=0,
                failed_servers=enabled_server_count,
                registered_tools=0,
                failed_server_ids=failed_server_ids,
            )




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
