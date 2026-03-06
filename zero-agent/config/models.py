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
    session_id: str  # 会话ID，由网关传入，必需字段
    metadata: Optional[Dict[str, Any]] = None
    message_history: Optional[List[Dict[str, Any]]] = None


class StreamChunk(BaseModel):
    """流式响应数据块"""
    type: str  # "content", "tool_call_start", "tool_call_end", "error", "done"
    content: Optional[str] = None
    tool_call: Optional[Dict[str, Any]] = None
    tool_call_id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None
    done: bool = False
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class StreamingChatResponse(BaseModel):
    """流式对话响应"""
    chunks: List[StreamChunk] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """对话响应"""
    message: str
    tool_calls: List[ToolCall] = Field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None

    def to_dict(self, format: str = "openai") -> Dict[str, Any]:
        """转换为字典，用于API响应
        
        Args:
            format: 响应格式，默认使用 "openai"
        
        确保所有字段都有默认值，避免返回null
        """
        return self.to_openai_format()
    
    def to_openai_format(self) -> Dict[str, Any]:
        """OpenAI 兼容格式
        
        注意：OpenAI的function_call格式是单个对象，不是数组
        如果有多个工具调用，需要返回多个choices，每个choice包含一个function_call
        """
        import uuid
        import json
        from datetime import datetime
        
        choices = []
        
        # 如果有工具调用，使用 function_call 格式
        if self.tool_calls:
            # OpenAI格式：每个工具调用作为一个独立的choice
            # 但通常只返回第一个工具调用作为function_call
            # 或者返回所有工具调用作为tool_calls数组（新格式）
            if len(self.tool_calls) == 1:
                # 单个工具调用，使用function_call格式（OpenAI旧格式）
                call = self.tool_calls[0]
                choices.append({
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": self.message,
                        "function_call": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False)
                        }
                    },
                    "finish_reason": "function_call"
                })
            else:
                # 多个工具调用，使用tool_calls格式（OpenAI新格式，支持并行调用）
                choices.append({
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": self.message,
                        "tool_calls": [
                            {
                                "id": call.id,
                                "type": "function",
                                "function": {
                                    "name": call.name,
                                    "arguments": json.dumps(call.arguments, ensure_ascii=False)
                                }
                            }
                            for call in self.tool_calls
                        ]
                    },
                    "finish_reason": "tool_calls"
                })
        else:
            # 没有工具调用，普通文本响应
            choices.append({
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": self.message
                },
                "finish_reason": "stop"
            })
        
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": "gpt-4",  # 可以从配置中获取
            "choices": choices,
            "usage": self.usage if self.usage else {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }


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
    command: str  # 启动命令，如 "uvx" 或 "node"
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


class FilterConfig(BaseModel):
    """过滤器配置"""
    enabled: bool = True
    name: str
    type: str  # "audit", "input_validation", "output_processing", "custom"
    priority: int = 100
    config: Dict[str, Any] = Field(default_factory=dict)


class SkillConfig(BaseModel):
    """Skill 配置"""
    id: str
    name: str
    path: str  # Skill 目录路径（相对于项目根目录）
    enabled: bool = True
    load_level: str = "metadata"  # metadata, full, resources
    priority: int = 100  # 加载优先级，数字越小优先级越高


class SkillMetadata(BaseModel):
    """Skill 元数据（从 SKILL.md 的 YAML 前置提取）"""
    name: str
    description: str
    version: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)  # 依赖的工具列表
    examples: List[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    """Agent配置"""
    id: str
    name: str
    description: str
    tools: List[ToolConfig] = Field(default_factory=list)
    mcp_servers: List[MCPConfig] = Field(default_factory=list)  # MCP 服务器配置
    mcp_tools: List[MCPToolConfig] = Field(default_factory=list)  # MCP 工具配置
    skills: List[SkillConfig] = Field(default_factory=list)  # Skill 配置
    function_call: Dict[str, Any] = Field(default_factory=dict)
    llm_config: Dict[str, Any] = Field(default_factory=dict)
    filters: List[FilterConfig] = Field(default_factory=list)  # 过滤器配置
    timeouts: Dict[str, int] = Field(default_factory=dict)  # 超时配置（秒）
    concurrency: Dict[str, int] = Field(default_factory=dict)  # 并发控制配置