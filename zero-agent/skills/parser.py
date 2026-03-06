"""
Skill 文件解析器
解析 SKILL.md 文件（YAML 前置 + Markdown 正文）
"""
import os
import re
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from config.models import SkillMetadata

logger = logging.getLogger(__name__)


class SkillParser:
    """Skill 文件解析器"""
    
    def __init__(self):
        self.skill_file_name = "SKILL.md"
    
    def parse_skill_file(self, skill_path: str) -> Tuple[SkillMetadata, str, Dict[str, Any]]:
        """
        解析 SKILL.md 文件
        
        Args:
            skill_path: Skill 目录路径
            
        Returns:
            (metadata, content, resources): 元数据、Markdown 内容、资源文件
        """
        skill_dir = Path(skill_path)
        skill_file = skill_dir / self.skill_file_name
        
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill 文件不存在: {skill_file}")
        
        # 读取文件内容
        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 分离 YAML 前置和 Markdown 正文
        metadata_dict, markdown_content = self._split_yaml_frontmatter(content)
        
        # 解析元数据
        metadata = SkillMetadata(**metadata_dict)
        
        # 扫描资源文件
        resources = self._scan_resources(skill_dir)
        
        return metadata, markdown_content, resources
    
    def _split_yaml_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """
        分离 YAML 前置元数据和 Markdown 正文
        
        Returns:
            (yaml_dict, markdown_content)
        """
        # 匹配 YAML 前置（--- 包围）
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)
        
        if not match:
            # 没有 YAML 前置，整个文件作为 Markdown
            return {"name": "Unknown", "description": ""}, content
        
        yaml_str = match.group(1)
        markdown_content = match.group(2)
        
        try:
            yaml_dict = yaml.safe_load(yaml_str) or {}
            return yaml_dict, markdown_content
        except yaml.YAMLError as e:
            logger.error(f"YAML 解析失败: {e}")
            return {"name": "Unknown", "description": ""}, markdown_content
    
    def _scan_resources(self, skill_dir: Path) -> Dict[str, Any]:
        """
        扫描 Skill 目录中的资源文件
        
        Returns:
            资源文件字典，key 为文件名，value 为文件内容或路径
        """
        resources = {}
        
        # 扫描目录中的文件（排除 SKILL.md）
        for file_path in skill_dir.iterdir():
            if file_path.is_file() and file_path.name != self.skill_file_name:
                try:
                    # 读取文本文件内容
                    if file_path.suffix in ['.md', '.txt', '.py', '.json', '.yaml', '.yml']:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            resources[file_path.name] = f.read()
                    else:
                        # 其他文件只记录路径
                        resources[file_path.name] = str(file_path)
                except Exception as e:
                    logger.warning(f"无法读取资源文件 {file_path}: {e}")
        
        # 扫描子目录（scripts/, references/, assets/）
        for subdir_name in ['scripts', 'references', 'assets']:
            subdir = skill_dir / subdir_name
            if subdir.exists() and subdir.is_dir():
                for file_path in subdir.rglob('*'):
                    if file_path.is_file():
                        try:
                            rel_path = file_path.relative_to(skill_dir)
                            if file_path.suffix in ['.md', '.txt', '.py', '.json', '.yaml', '.yml']:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    resources[str(rel_path)] = f.read()
                            else:
                                resources[str(rel_path)] = str(file_path)
                        except Exception as e:
                            logger.warning(f"无法读取资源文件 {file_path}: {e}")
        
        return resources
    
    def parse_metadata_only(self, skill_path: str) -> SkillMetadata:
        """
        仅解析元数据（Level 1 加载）
        
        Args:
            skill_path: Skill 目录路径
            
        Returns:
            SkillMetadata 对象
        """
        skill_dir = Path(skill_path)
        skill_file = skill_dir / self.skill_file_name
        
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill 文件不存在: {skill_file}")
        
        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata_dict, _ = self._split_yaml_frontmatter(content)
        return SkillMetadata(**metadata_dict)
