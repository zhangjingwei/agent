"""
配置设置
"""

import os
from typing import Optional
from .models import AgentConfig, ToolConfig, MCPConfig, MCPToolConfig


def get_agent_config() -> AgentConfig:
    """
    生产环境从YAML/JSON文件加载
    """
    # 取LLM配置
    llm_provider = os.getenv("LLM_PROVIDER")
    llm_api_key = os.getenv(f"{llm_provider.upper()}_API_KEY") if llm_provider else None
    llm_model = os.getenv("LLM_MODEL")  # 设置默认模型为deepseek-chat

    if not llm_provider:
        raise ValueError("LLM_PROVIDER environment variable not set")

    if not llm_api_key:
        raise ValueError(f"{llm_provider.upper()}_API_KEY environment variable not set")

    if not llm_model:
        raise ValueError("LLM_MODEL environment variable not set")

    if not llm_provider:
        raise ValueError("LLM_PROVIDER environment variable not set")

    # LLM配置
    llm_config = {
        "provider": llm_provider,
        "api_key": llm_api_key,
        "model": llm_model
    }

    # 工具配置
    tools = [
        ToolConfig(
            id="calculator",
            name="calculator",
            description="高级数学计算器，支持丰富的数学运算和函数",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，支持：基本运算(+-*/), 幂运算(**), 函数(sqrt, sin, cos, tan, log, ln, exp, abs, factorial), 常量(pi, e)"
                    }
                },
                "required": ["expression"]
            },
            handler={
                "type": "function",
                "module": "tools.builtin.calculator",
                "function": "calculate",
                "timeout": 5000
            }
        )
    ]


    # MCP服务器配置
    mcp_servers = [
        # MCP 文件系统工具 (已验证可用)
        MCPConfig(
            id="filesystem",
            name="文件系统工具",
            description="提供文件系统操作工具",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            env={},
            enabled=True
        ),

        # 彩云天气工具 (需要调试，可使用 MCP inspector)
        # 如需启用，请先运行:
        # npx @modelcontextprotocol/inspector uvx mcp-caiyun-weather
        MCPConfig(
            id="caiyun-weather",
            name="彩云天气",
            description="提供中国天气预报服务",
            command="uvx",
            args=["mcp-caiyun-weather"],
            env={
                "CAIYUN_WEATHER_API_TOKEN": "huE0COxlM2CCc2ES"
            },
            enabled=True
        ),
        # 可以添加更多MCP服务器
        # MCPConfig(
        #     id="filesystem",
        #     name="文件系统工具",
        #     description="提供文件系统操作工具",
        #     command="npx",
        #     args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        #     enabled=True
        # )
    ]

    # MCP工具配置（可选，用于自定义配置）
    mcp_tools: list[MCPToolConfig] = [
        # 可以在这里自定义特定工具的配置
        # MCPToolConfig(
        #     server_id="caiyun-weather",
        #     tool_name="get_realtime_weather",
        #     enabled=True,
        #     description_override="获取指定位置的实时天气信息"
        # )
    ]

    # Function Call配置
    function_call = {
        "strategy": "auto",
        "max_iterations": 3,
        "timeout": 10000
    }

    return AgentConfig(
        id="demo-agent",
        name="演示Agent",
        description="用于演示的简单Agent",
        tools=tools,
        mcp_servers=mcp_servers,
        mcp_tools=mcp_tools,
        function_call=function_call,
        llm_config=llm_config
    )


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """
    从文件加载配置

    MVP版本暂时返回硬编码配置，生产环境应该实现YAML/JSON配置加载
    """
    return get_agent_config()
