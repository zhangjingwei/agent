"""
Skill 渐进式加载器
实现三层加载机制：metadata -> full -> resources
"""
import logging
from typing import Optional
from pathlib import Path
from .base import Skill
from .parser import SkillParser
from config.models import SkillMetadata

logger = logging.getLogger(__name__)


class SkillLoader:
    """Skill 渐进式加载器"""
    
    def __init__(self):
        self.parser = SkillParser()
        self._cache: dict = {}  # 缓存已加载的 Skill
    
    async def load_metadata(self, skill_path: str) -> SkillMetadata:
        """
        Level 1: 仅加载元数据（最低 Token 消耗）
        
        Args:
            skill_path: Skill 目录路径
            
        Returns:
            SkillMetadata 对象
        """
        cache_key = f"{skill_path}:metadata"
        if cache_key in self._cache:
            logger.debug(f"从缓存加载元数据: {skill_path}")
            return self._cache[cache_key]
        
        try:
            metadata = self.parser.parse_metadata_only(skill_path)
            self._cache[cache_key] = metadata
            logger.debug(f"加载 Skill 元数据: {skill_path}")
            return metadata
        except Exception as e:
            logger.error(f"加载 Skill 元数据失败 {skill_path}: {e}")
            raise
    
    async def load_full(self, skill_path: str) -> Skill:
        """
        Level 2: 加载完整内容（YAML + Markdown）
        
        Args:
            skill_path: Skill 目录路径
            
        Returns:
            Skill 对象
        """
        cache_key = f"{skill_path}:full"
        if cache_key in self._cache:
            logger.debug(f"从缓存加载完整内容: {skill_path}")
            return self._cache[cache_key]
        
        try:
            metadata, content, _ = self.parser.parse_skill_file(skill_path)
            skill = Skill(
                metadata=metadata,
                content=content,
                path=skill_path,
                load_level="full"
            )
            self._cache[cache_key] = skill
            logger.debug(f"加载 Skill 完整内容: {skill_path}")
            return skill
        except Exception as e:
            logger.error(f"加载 Skill 完整内容失败 {skill_path}: {e}")
            raise
    
    async def load_with_resources(self, skill_path: str) -> Skill:
        """
        Level 3: 加载所有资源（YAML + Markdown + 资源文件）
        
        Args:
            skill_path: Skill 目录路径
            
        Returns:
            Skill 对象
        """
        cache_key = f"{skill_path}:resources"
        if cache_key in self._cache:
            logger.debug(f"从缓存加载所有资源: {skill_path}")
            return self._cache[cache_key]
        
        try:
            metadata, content, resources = self.parser.parse_skill_file(skill_path)
            skill = Skill(
                metadata=metadata,
                content=content,
                resources=resources,
                path=skill_path,
                load_level="resources"
            )
            self._cache[cache_key] = skill
            logger.debug(f"加载 Skill 所有资源: {skill_path}")
            return skill
        except Exception as e:
            logger.error(f"加载 Skill 所有资源失败 {skill_path}: {e}")
            raise
    
    async def load_by_level(self, skill_path: str, load_level: str) -> Skill:
        """
        根据加载级别加载 Skill
        
        Args:
            skill_path: Skill 目录路径
            load_level: 加载级别 (metadata, full, resources)
            
        Returns:
            Skill 对象（metadata 级别返回仅包含元数据的 Skill）
        """
        if load_level == "metadata":
            metadata = await self.load_metadata(skill_path)
            return Skill(
                metadata=metadata,
                path=skill_path,
                load_level="metadata"
            )
        elif load_level == "full":
            return await self.load_full(skill_path)
        elif load_level == "resources":
            return await self.load_with_resources(skill_path)
        else:
            raise ValueError(f"不支持的加载级别: {load_level}")
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("已清空 Skill 加载缓存")
