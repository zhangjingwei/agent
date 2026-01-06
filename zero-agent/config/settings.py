"""
配置设置 - 向后兼容的默认配置加载
"""

import os
from pathlib import Path
from typing import Optional
from .models import AgentConfig
from .loader import ConfigLoader


def get_agent_config() -> AgentConfig:
    """
    获取默认 Agent 配置
    
    优先从配置文件加载，如果配置文件不存在则使用硬编码配置（向后兼容）
    """
    # 尝试从默认配置文件加载
    default_config_path = Path(__file__).parent / "agents" / "default_agent.yaml"
    
    if default_config_path.exists():
        try:
            return ConfigLoader.load_from_file(str(default_config_path))
        except Exception as e:
            # 如果加载失败，记录警告但继续使用硬编码配置
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"加载默认配置文件失败，使用硬编码配置: {str(e)}")
    
    # 降级到硬编码配置（向后兼容）
    return _get_fallback_config()


def _get_fallback_config() -> AgentConfig:
    """
    降级配置：最小化硬编码配置（向后兼容）
    
    注意：此函数仅用于向后兼容，新代码应该使用配置文件。
    如果默认配置文件不存在，此函数提供最基本的配置。
    """
    from .models import ToolConfig, FilterConfig
    
    # 从环境变量获取 LLM 配置（必需）
    llm_provider = os.getenv("LLM_PROVIDER")
    if not llm_provider:
        raise ValueError("LLM_PROVIDER environment variable not set")
    
    llm_api_key = os.getenv(f"{llm_provider.upper()}_API_KEY")
    if not llm_api_key:
        raise ValueError(f"{llm_provider.upper()}_API_KEY environment variable not set")
    
    llm_model = os.getenv("LLM_MODEL")
    if not llm_model:
        raise ValueError("LLM_MODEL environment variable not set")

    # 最小化配置：只包含必需的 LLM 配置和基本过滤器
    return AgentConfig(
        id="zero",
        name="Zero Agent",
        description="系统默认的Agent配置（降级模式）",
        tools=[],  # 工具配置应在配置文件中定义
        mcp_servers=[],  # MCP 配置应在配置文件中定义
        mcp_tools=[],
        function_call={
            "strategy": "auto",
            "max_iterations": 5,
            "timeout": 10000
        },
        llm_config={
            "provider": llm_provider,
            "api_key": llm_api_key,
            "model": llm_model,
            "temperature": 0.7
        },
        filters=[
            FilterConfig(
                enabled=True,
                name="audit",
                type="audit",
                priority=10,
                config={
                    "enable_request_logging": True,
                    "enable_response_logging": True,
                    "log_sensitive_data": False,
                    "log_level": "info"
                }
            )
        ],
        timeouts={
            "llm": 60,  # LLM 调用超时（秒）
            "tool": 30,  # 工具执行超时（秒）
            "workflow": 300  # 工作流总体超时（秒）
        },
        concurrency={
            "max_tools": 5  # 每个工作流最大并发工具数
        }
    )


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """
    从文件加载配置
    
    Args:
        config_path: 配置文件路径，如果为 None 则加载默认配置
        
    Returns:
        AgentConfig: Agent 配置对象
    """
    if config_path:
        return ConfigLoader.load_from_file(config_path)
    else:
        return get_agent_config()
