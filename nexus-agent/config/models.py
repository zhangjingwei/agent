"""
数据模型定义
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """对话消息"""
    id: str
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class ToolCall(BaseModel):
    """工具调用"""
    id: str
    name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    stream: bool = False
    metadata: Optional[Dict[str, Any]] = None
    message_history: Optional[List[Dict[str, Any]]] = None


class ChatResponse(BaseModel):
    """对话响应"""
    message: str
    tool_calls: List[ToolCall] = Field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None


class Session(BaseModel):
    """会话"""
    id: str
    agent_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    messages: List[Message] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class ToolConfig(BaseModel):
    """工具配置"""
    id: str
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Dict[str, Any]
    enabled: bool = True


class MCPConfig(BaseModel):
    """MCP服务器配置"""
    id: str
    name: str
    description: str
    command: str  # 启动命令，如 "uvx" 或 "python"
    args: List[str] = Field(default_factory=list)  # 命令参数
    env: Dict[str, str] = Field(default_factory=dict)  # 环境变量
    enabled: bool = True
    timeout: int = 30000  # 毫秒
    working_dir: Optional[str] = None  # 工作目录


class MCPToolConfig(BaseModel):
    """MCP工具配置"""
    server_id: str
    tool_name: str
    enabled: bool = True
    description_override: Optional[str] = None
    parameter_mapping: Optional[Dict[str, str]] = None


class AgentConfig(BaseModel):
    """Agent配置"""
    id: str
    name: str
    description: str
    tools: List[ToolConfig] = Field(default_factory=list)
    mcp_servers: List[MCPConfig] = Field(default_factory=list)  # MCP 服务器配置
    mcp_tools: List[MCPToolConfig] = Field(default_factory=list)  # MCP 工具配置
    function_call: Dict[str, Any] = Field(default_factory=dict)
    llm_config: Dict[str, Any] = Field(default_factory=dict)
