"""
配置文件加载器 - 支持 YAML 和 JSON 格式
"""

import json
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from .models import AgentConfig, ToolConfig, MCPConfig, MCPToolConfig, FilterConfig, SkillConfig

logger = logging.getLogger(__name__)


def _ensure_env_loaded():
    """确保环境变量已加载（如果存在 .env 文件）"""
    try:
        from dotenv import load_dotenv
        project_root = Path(__file__).parent.parent.parent
        env_file = project_root / '.env'
        if env_file.exists():
            load_dotenv(env_file, override=False)  # 不覆盖已存在的环境变量
    except ImportError:
        pass  # dotenv 不是必需的


class ConfigLoader:
    """配置加载器"""

    @staticmethod
    def load_from_file(config_path: str) -> AgentConfig:
        """
        从文件加载配置
        
        Args:
            config_path: 配置文件路径（支持 .yaml, .yml, .json）
            
        Returns:
            AgentConfig: Agent 配置对象
            
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 配置文件格式错误
        """
        # 确保环境变量已加载
        _ensure_env_loaded()
        
        path = Path(config_path)
        
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        # 根据扩展名选择解析器
        suffix = path.suffix.lower()
        
        if suffix in ['.yaml', '.yml']:
            return ConfigLoader._load_yaml(path)
        elif suffix == '.json':
            return ConfigLoader._load_json(path)
        else:
            raise ValueError(f"不支持的配置文件格式: {suffix}，支持 .yaml, .yml, .json")

    @staticmethod
    def _load_yaml(path: Path) -> AgentConfig:
        """加载 YAML 配置文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return ConfigLoader._parse_config(data, path.parent)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"加载配置文件失败: {str(e)}")

    @staticmethod
    def _load_json(path: Path) -> AgentConfig:
        """加载 JSON 配置文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return ConfigLoader._parse_config(data, path.parent)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"加载配置文件失败: {str(e)}")

    @staticmethod
    def _parse_config(data: Dict[str, Any], config_dir: Path) -> AgentConfig:
        """解析配置数据"""
        # 解析工具配置
        tools = [
            ToolConfig(**tool_data) 
            for tool_data in data.get('tools', [])
        ]
        
        # 解析 MCP 服务器配置
        mcp_servers = [
            MCPConfig(**mcp_data)
            for mcp_data in data.get('mcp_servers', [])
        ]
        
        # 解析 MCP 工具配置
        mcp_tools = [
            MCPToolConfig(**mcp_tool_data)
            for mcp_tool_data in data.get('mcp_tools', [])
        ]
        
        # 解析 Skill 配置
        skills = [
            SkillConfig(**skill_data)
            for skill_data in data.get('skills', [])
        ]
        
        # 解析过滤器配置
        filters = [
            FilterConfig(**filter_data)
            for filter_data in data.get('filters', [])
        ]
        
        # 处理环境变量替换（先解析基本配置）
        llm_config = ConfigLoader._resolve_env_vars(data.get('llm_config', {}))
        
        # 智能解析 LLM API Key：根据 provider 动态选择对应的 API key
        llm_config = ConfigLoader._resolve_llm_api_key(llm_config)
        
        # 处理 MCP 服务器配置中的环境变量
        resolved_mcp_servers = []
        for mcp_data in data.get('mcp_servers', []):
            resolved_mcp = ConfigLoader._resolve_env_vars(mcp_data)
            resolved_mcp_servers.append(resolved_mcp)
        
        # 重新构建 MCP 配置对象
        mcp_servers = [
            MCPConfig(**mcp_data)
            for mcp_data in resolved_mcp_servers
        ]
        
        # 构建 AgentConfig
        agent_config = AgentConfig(
            id=data.get('id', 'zero'),
            name=data.get('name', 'Default Agent'),
            description=data.get('description', ''),
            tools=tools,
            mcp_servers=mcp_servers,
            mcp_tools=mcp_tools,
            skills=skills,  # 添加 Skill 配置
            function_call=data.get('function_call', {}),
            llm_config=llm_config,
            filters=filters,
            timeouts=data.get('timeouts', {}),  # 添加超时配置
            concurrency=data.get('concurrency', {})  # 添加并发配置
        )
        
        # 添加调试日志
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"解析配置完成 - Agent ID: {agent_config.id}, Skills: {len(agent_config.skills)}, MCP Servers: {len(agent_config.mcp_servers)}")
        
        return agent_config

    @staticmethod
    def _resolve_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析环境变量
        
        支持格式：
        - ${VAR_NAME} 或 $VAR_NAME
        - ${VAR_NAME:default_value} 默认值
        """
        resolved = {}
        for key, value in config.items():
            if isinstance(value, str):
                # 替换 ${VAR} 或 $VAR
                import re
                pattern = r'\$\{?([^}:]+)(?::([^}]+))?\}?'
                
                def replace_env(match):
                    var_name = match.group(1)
                    default = match.group(2) if match.group(2) else None
                    return os.getenv(var_name, default or '')
                
                resolved[key] = re.sub(pattern, replace_env, value)
            elif isinstance(value, dict):
                resolved[key] = ConfigLoader._resolve_env_vars(value)
            elif isinstance(value, list):
                # 处理列表中的环境变量
                resolved[key] = [
                    ConfigLoader._resolve_env_vars(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                resolved[key] = value
        
        return resolved

    @staticmethod
    def _resolve_llm_api_key(llm_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        智能解析 LLM API Key
        
        根据 provider 动态选择对应的 API key 环境变量：
        - openai -> OPENAI_API_KEY
        - anthropic -> ANTHROPIC_API_KEY
        - siliconflow -> SILICONFLOW_API_KEY
        
        如果 api_key 字段为空或包含 ${...}，则根据 provider 自动填充
        """
        provider = llm_config.get('provider', '').lower()
        api_key = llm_config.get('api_key', '')
        
        # 如果 api_key 为空或仍然是环境变量占位符，则根据 provider 自动获取
        if not api_key or api_key.startswith('${') or api_key.startswith('$'):
            # 根据 provider 映射到对应的环境变量
            provider_key_map = {
                'openai': 'OPENAI_API_KEY',
                'anthropic': 'ANTHROPIC_API_KEY',
                'siliconflow': 'SILICONFLOW_API_KEY',
            }
            
            env_var_name = provider_key_map.get(provider)
            if env_var_name:
                api_key = os.getenv(env_var_name, '')
                if api_key:
                    llm_config['api_key'] = api_key
                    logger.info(f"自动从环境变量 {env_var_name} 获取 API key")
        
        return llm_config

    @staticmethod
    def load_from_dir(config_dir: str) -> Dict[str, AgentConfig]:
        """
        从目录加载多个配置文件
        
        Args:
            config_dir: 配置目录路径
            
        Returns:
            Dict[str, AgentConfig]: Agent ID 到配置的映射
        """
        configs = {}
        dir_path = Path(config_dir)
        
        if not dir_path.exists() or not dir_path.is_dir():
            raise ValueError(f"配置目录不存在或不是目录: {config_dir}")
        
        # 查找所有配置文件（支持 .yaml, .yml, .json）
        config_patterns = ['*.yaml', '*.yml', '*.json']
        for pattern in config_patterns:
            for config_file in dir_path.glob(pattern):
                try:
                    config = ConfigLoader.load_from_file(str(config_file))
                    # 如果 ID 已存在，记录警告但继续加载（后面的会覆盖前面的）
                    if config.id in configs:
                        logger.warning(
                            f"配置文件 {config_file.name} 的 Agent ID '{config.id}' 已存在，将被覆盖"
                        )
                    configs[config.id] = config
                    logger.info(f"加载配置文件: {config_file.name} -> Agent ID: {config.id}")
                except Exception as e:
                    logger.error(f"加载配置文件失败 {config_file.name}: {str(e)}")
                    continue
        
        return configs
