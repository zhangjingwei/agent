"""
Skill 基础类
"""
from typing import Dict, Any, Optional
from config.models import SkillMetadata


class Skill:
    """Skill 类，表示一个技能"""
    
    def __init__(
        self,
        metadata: SkillMetadata,
        content: str = "",
        resources: Dict[str, Any] = None,
        path: str = "",
        load_level: str = "metadata"
    ):
        self.metadata = metadata
        self.content = content  # Markdown 正文内容
        self.resources = resources or {}  # 资源文件（脚本、文档等）
        self.path = path  # Skill 目录路径
        self.load_level = load_level  # 当前加载级别
        self.enabled: bool = True  # 是否启用
        self.priority: int = 100  # 优先级
    
    def __repr__(self):
        return f"Skill(name={self.metadata.name}, load_level={self.load_level})"
