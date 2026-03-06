"""
Skill 注册器
管理 Skill 的注册和查询
"""
import logging
from typing import Dict, List, Optional
from .base import Skill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Skill 注册器"""
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}  # skill_id -> Skill
    
    def register(self, skill_id: str, skill: Skill) -> None:
        """注册 Skill"""
        if skill_id in self._skills:
            logger.warning(f"Skill {skill_id} 已存在，将被覆盖")
        self._skills[skill_id] = skill
        logger.info(f"注册 Skill: {skill_id} ({skill.metadata.name})")
    
    def unregister(self, skill_id: str) -> None:
        """注销 Skill"""
        if skill_id in self._skills:
            del self._skills[skill_id]
            logger.info(f"注销 Skill: {skill_id}")
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取 Skill"""
        return self._skills.get(skill_id)
    
    def get_all_skills(self) -> List[Skill]:
        """获取所有 Skill，按优先级排序"""
        skills = list(self._skills.values())
        # 按优先级排序（数字越小优先级越高）
        skills.sort(key=lambda s: getattr(s, 'priority', 100))
        return skills
    
    def get_active_skills(self) -> List[Skill]:
        """获取所有启用的 Skill"""
        return [s for s in self.get_all_skills() if getattr(s, 'enabled', True)]
    
    def has_skill(self, skill_id: str) -> bool:
        """检查 Skill 是否存在"""
        return skill_id in self._skills
    
    def clear(self) -> None:
        """清空所有 Skill"""
        self._skills.clear()
        logger.info("已清空所有 Skill")
