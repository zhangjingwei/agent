"""
配置验证器 - 验证 Agent 配置的有效性
"""

from typing import List, Tuple
import logging

from .models import AgentConfig, ToolConfig, MCPConfig

logger = logging.getLogger(__name__)


class ConfigValidator:
    """配置验证器"""

    @staticmethod
    def validate(config: AgentConfig) -> Tuple[bool, List[str]]:
        """
        验证配置
        
        Args:
            config: Agent 配置
            
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误列表)
        """
        errors = []
        
        # 验证基本字段
        if not config.id or not config.id.strip():
            errors.append("Agent ID 不能为空")
        
        if not config.name or not config.name.strip():
            errors.append("Agent 名称不能为空")
        
        # 验证 LLM 配置
        llm_errors = ConfigValidator._validate_llm_config(config.llm_config)
        errors.extend(llm_errors)
        
        # 验证工具配置
        tool_errors = ConfigValidator._validate_tools(config.tools)
        errors.extend(tool_errors)
        
        # 验证 MCP 配置
        mcp_errors = ConfigValidator._validate_mcp_servers(config.mcp_servers)
        errors.extend(mcp_errors)
        
        # 验证 MCP 工具配置
        mcp_tool_errors = ConfigValidator._validate_mcp_tools(
            config.mcp_tools, 
            config.mcp_servers
        )
        errors.extend(mcp_tool_errors)
        
        return len(errors) == 0, errors

    @staticmethod
    def _validate_llm_config(llm_config: dict) -> List[str]:
        """验证 LLM 配置"""
        errors = []
        
        required_fields = ['provider', 'api_key', 'model']
        for field in required_fields:
            if field not in llm_config or not llm_config[field]:
                errors.append(f"LLM 配置缺少必需字段: {field}")
        
        # 验证 provider
        if 'provider' in llm_config:
            valid_providers = ['openai', 'anthropic', 'siliconflow']
            if llm_config['provider'] not in valid_providers:
                errors.append(
                    f"不支持的 LLM 提供商: {llm_config['provider']}, "
                    f"支持的提供商: {', '.join(valid_providers)}"
                )
        
        return errors

    @staticmethod
    def _validate_tools(tools: List[ToolConfig]) -> List[str]:
        """验证工具配置"""
        errors = []
        tool_names = set()
        
        for i, tool in enumerate(tools):
            if not tool.enabled:
                continue
            
            # 检查工具名称唯一性
            if tool.name in tool_names:
                errors.append(f"工具名称重复: {tool.name}")
            tool_names.add(tool.name)
            
            # 验证工具配置
            if not tool.name or not tool.name.strip():
                errors.append(f"工具 #{i+1} 名称不能为空")
            
            if not tool.description or not tool.description.strip():
                errors.append(f"工具 {tool.name} 缺少描述")
            
            # 验证 handler
            if not tool.handler:
                errors.append(f"工具 {tool.name} 缺少 handler 配置")
            else:
                handler_type = tool.handler.get('type')
                if handler_type == 'function':
                    if not tool.handler.get('module'):
                        errors.append(f"工具 {tool.name} 的 function handler 缺少 module")
                    if not tool.handler.get('function'):
                        errors.append(f"工具 {tool.name} 的 function handler 缺少 function")
                elif handler_type == 'class':
                    if not tool.handler.get('class'):
                        errors.append(f"工具 {tool.name} 的 class handler 缺少 class")
                else:
                    errors.append(f"工具 {tool.name} 的 handler 类型无效: {handler_type}")
        
        return errors

    @staticmethod
    def _validate_mcp_servers(mcp_servers: List[MCPConfig]) -> List[str]:
        """验证 MCP 服务器配置"""
        errors = []
        server_ids = set()
        
        for i, server in enumerate(mcp_servers):
            if not server.enabled:
                continue
            
            # 检查服务器 ID 唯一性
            if server.id in server_ids:
                errors.append(f"MCP 服务器 ID 重复: {server.id}")
            server_ids.add(server.id)
            
            # 验证基本字段
            if not server.id or not server.id.strip():
                errors.append(f"MCP 服务器 #{i+1} ID 不能为空")
            
            if not server.name or not server.name.strip():
                errors.append(f"MCP 服务器 {server.id} 名称不能为空")
            
            if not server.command or not server.command.strip():
                errors.append(f"MCP 服务器 {server.id} 缺少 command")
        
        return errors

    @staticmethod
    def _validate_mcp_tools(
        mcp_tools: List, 
        mcp_servers: List[MCPConfig]
    ) -> List[str]:
        """验证 MCP 工具配置"""
        errors = []
        server_ids = {server.id for server in mcp_servers if server.enabled}
        
        for i, mcp_tool in enumerate(mcp_tools):
            if not mcp_tool.enabled:
                continue
            
            # 验证引用的服务器存在
            if mcp_tool.server_id not in server_ids:
                errors.append(
                    f"MCP 工具配置 #{i+1} 引用的服务器不存在: {mcp_tool.server_id}"
                )
        
        return errors
