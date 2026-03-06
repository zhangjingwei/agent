"""
Skill 管理器
统一管理 Skill 的加载、注册和生命周期
"""
import logging
import os
from pathlib import Path
from typing import List
from .registry import SkillRegistry
from .loader import SkillLoader
from .base import Skill
from config.models import SkillConfig

logger = logging.getLogger(__name__)


class SkillManager:
    """Skill 管理器"""
    
    def __init__(self):
        self.registry = SkillRegistry()
        self.loader = SkillLoader()
        self._base_path: Path = None  # Skill 基础路径
    
    def set_base_path(self, base_path: str):
        """设置 Skill 基础路径（通常是项目根目录）"""
        self._base_path = Path(base_path)
        logger.info(f"设置 Skill 基础路径: {base_path}")
    
    async def load_skills_from_config(self, skill_configs: List[SkillConfig]) -> None:
        """
        从配置加载 Skill
        
        Args:
            skill_configs: Skill 配置列表
        """
        logger.debug(f"收到 Skill 配置: {len(skill_configs) if skill_configs else 0} 个")
        
        if not skill_configs:
            logger.info("没有配置 Skill，跳过加载")
            return
        
        # 详细日志
        for config in skill_configs:
            logger.debug(f"Skill 配置: id={config.id}, enabled={config.enabled}, path={config.path}, load_level={config.load_level}")
        
        logger.info(f"开始加载 {len(skill_configs)} 个 Skill 配置")
        
        for config in skill_configs:
            if not config.enabled:
                logger.info(f"跳过禁用的 Skill: {config.id}")
                continue
            
            try:
                # 构建完整路径
                if self._base_path:
                    skill_path = self._base_path / config.path
                else:
                    skill_path = Path(config.path)
                
                skill_path = skill_path.resolve()
                
                if not skill_path.exists():
                    logger.warning(f"Skill 路径不存在: {skill_path}")
                    continue
                
                # 根据配置的加载级别加载 Skill
                skill = await self.loader.load_by_level(str(skill_path), config.load_level)
                
                # 设置配置属性
                skill.enabled = config.enabled
                skill.priority = config.priority
                
                # 注册到注册器
                self.registry.register(config.id, skill)
                logger.info(f"成功加载 Skill: {config.id} ({skill.metadata.name})")
                
            except Exception as e:
                logger.error(f"加载 Skill 失败 {config.id}: {e}", exc_info=True)
                # 继续加载其他 Skill，不因一个失败而中断
    
    def get_active_skills(self) -> List[Skill]:
        """获取所有启用的 Skill"""
        return self.registry.get_active_skills()
    
    def get_skill(self, skill_id: str) -> Skill:
        """获取指定 Skill"""
        return self.registry.get_skill(skill_id)
    
    def clear(self):
        """清空所有 Skill"""
        self.registry.clear()
        self.loader.clear_cache()
