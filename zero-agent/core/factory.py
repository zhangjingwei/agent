"""
Agent 工厂 - 创建和管理多个 Agent 实例
"""

import logging
from typing import Dict, Optional
from pathlib import Path

from core.agent import ZeroAgentEngine
from config.models import AgentConfig
from config.loader import ConfigLoader
from config.validator import ConfigValidator

logger = logging.getLogger(__name__)


class AgentFactory:
    """Agent 工厂类"""

    def __init__(self):
        self._agents: Dict[str, ZeroAgentEngine] = {}
        self._configs: Dict[str, AgentConfig] = {}

    async def create_agent(self, config: AgentConfig) -> ZeroAgentEngine:
        """
        创建 Agent 实例
        
        Args:
            config: Agent 配置
            
        Returns:
            ZeroAgentEngine: Agent 实例
            
        Raises:
            ValueError: 配置验证失败或 Agent ID 已存在
        """
        # 验证配置
        is_valid, errors = ConfigValidator.validate(config)
        if not is_valid:
            error_msg = "配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(f"Agent {config.id} 配置验证失败:\n{error_msg}")
            raise ValueError(error_msg)
        
        # 检查是否已存在
        if config.id in self._agents:
            raise ValueError(f"Agent ID '{config.id}' 已存在")
        
        try:
            # 创建 Agent 实例
            agent = ZeroAgentEngine(config)
            await agent.initialize()
            
            # 保存实例和配置
            self._agents[config.id] = agent
            self._configs[config.id] = config
            
            logger.info(f"成功创建 Agent: {config.id} ({config.name})")
            return agent
            
        except Exception as e:
            logger.error(f"创建 Agent 失败 {config.id}: {str(e)}")
            raise

    async def create_agent_from_file(self, config_path: str) -> ZeroAgentEngine:
        """
        从配置文件创建 Agent
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            ZeroAgentEngine: Agent 实例
        """
        config = ConfigLoader.load_from_file(config_path)
        return await self.create_agent(config)

    async def create_agents_from_dir(self, config_dir: str) -> Dict[str, ZeroAgentEngine]:
        """
        从配置目录加载多个 Agent
        
        Args:
            config_dir: 配置目录路径
            
        Returns:
            Dict[str, ZeroAgentEngine]: Agent ID 到实例的映射
        """
        configs = ConfigLoader.load_from_dir(config_dir)
        agents = {}
        
        for agent_id, config in configs.items():
            try:
                agent = await self.create_agent(config)
                agents[agent_id] = agent
            except Exception as e:
                logger.error(f"从配置目录创建 Agent 失败 {agent_id}: {str(e)}")
                continue
        
        return agents

    def get_agent(self, agent_id: str) -> Optional[ZeroAgentEngine]:
        """
        获取 Agent 实例
        
        Args:
            agent_id: Agent ID
            
        Returns:
            ZeroAgentEngine 或 None
        """
        return self._agents.get(agent_id)

    def get_config(self, agent_id: str) -> Optional[AgentConfig]:
        """
        获取 Agent 配置
        
        Args:
            agent_id: Agent ID
            
        Returns:
            AgentConfig 或 None
        """
        return self._configs.get(agent_id)

    def list_agents(self) -> Dict[str, str]:
        """
        列出所有 Agent
        
        Returns:
            Dict[str, str]: Agent ID 到名称的映射
        """
        return {
            agent_id: config.name
            for agent_id, config in self._configs.items()
        }

    async def remove_agent(self, agent_id: str) -> bool:
        """
        移除 Agent 实例
        
        Args:
            agent_id: Agent ID
            
        Returns:
            bool: 是否成功移除
        """
        if agent_id not in self._agents:
            return False
        
        try:
            agent = self._agents[agent_id]
            await agent.cleanup()
            
            del self._agents[agent_id]
            del self._configs[agent_id]
            
            logger.info(f"已移除 Agent: {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除 Agent 失败 {agent_id}: {str(e)}")
            return False

    async def reload_agent(self, agent_id: str, config_path: Optional[str] = None) -> ZeroAgentEngine:
        """
        重新加载 Agent
        
        Args:
            agent_id: Agent ID
            config_path: 配置文件路径（如果提供，从文件重新加载配置）
            
        Returns:
            ZeroAgentEngine: 新的 Agent 实例
            
        Raises:
            ValueError: Agent 不存在且未提供配置文件路径
        """
        # 检查 Agent 是否存在
        agent_exists = agent_id in self._agents
        
        # 移除旧实例（如果存在）
        if agent_exists:
            await self.remove_agent(agent_id)
        
        # 重新加载配置
        if config_path:
            config = ConfigLoader.load_from_file(config_path)
            # 如果提供了配置文件，确保配置的 ID 与 agent_id 匹配
            if config.id != agent_id:
                logger.warning(
                    f"配置文件中的 Agent ID ({config.id}) 与请求的 ID ({agent_id}) 不匹配，"
                    f"将使用配置文件中的 ID"
                )
        else:
            # 如果没有提供配置文件，尝试从已保存的配置中获取
            if not agent_exists:
                raise ValueError(
                    f"Agent '{agent_id}' 不存在且未提供配置文件路径。"
                    f"请提供 config_path 参数来创建新的 Agent。"
                )
            config = self._configs.get(agent_id)
            if not config:
                raise ValueError(f"Agent '{agent_id}' 的配置丢失")
        
        # 创建新实例
        return await self.create_agent(config)

    async def cleanup_all(self):
        """清理所有 Agent 实例"""
        errors = []
        for agent_id in list(self._agents.keys()):
            try:
                await self.remove_agent(agent_id)
            except Exception as e:
                error_msg = f"清理 Agent {agent_id} 时出错: {str(e)}"
                logger.warning(error_msg, exc_info=True)
                errors.append(error_msg)
        
        if errors:
            logger.warning(f"清理完成，但有 {len(errors)} 个错误")
        else:
            logger.info("已清理所有 Agent 实例")
