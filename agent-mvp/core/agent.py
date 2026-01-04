"""
统一Agent接口 - 整合所有层
"""

from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime

from orchestration.agent import OrchestratorAgent
from config.models import AgentConfig, ChatRequest, ChatResponse, Session, Message, MessageRole


class UniversalAgent:
    """通用Agent接口"""

    def __init__(self, config: AgentConfig):
        self.orchestrator = OrchestratorAgent(config)
        # MVP版本使用内存存储会话
        self._sessions: Dict[str, Session] = {}
        self._initialized = False

    async def initialize(self):
        """异步初始化agent"""
        if not self._initialized:
            await self.orchestrator.initialize_async()
            self._initialized = True

    async def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> Session:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = Session(
            id=session_id,
            agent_id=self.orchestrator.config.id,
            metadata=metadata or {}
        )
        self._sessions[session_id] = session
        return session

    async def get_history(self, session_id: str, limit: Optional[int] = None) -> List[Message]:
        """获取会话历史"""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        messages = self._sessions[session_id].messages
        if limit:
            messages = messages[-limit:]
        return messages

    async def clear_session(self, session_id: str) -> bool:
        """清除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    async def chat(self, session_id: str, request: ChatRequest) -> ChatResponse:
        """对话接口"""
        # 确保会话存在
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        # 执行对话
        response = await self.orchestrator.chat(session_id, request)

        # 更新会话历史
        session = self._sessions[session_id]

        # 添加用户消息
        user_message = Message(
            id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content=request.message,
            metadata=request.metadata
        )
        session.messages.append(user_message)

        # 添加助手消息
        assistant_message = Message(
            id=str(uuid.uuid4()),
            role=MessageRole.ASSISTANT,
            content=response.message,
            metadata={
                "tool_calls": len(response.tool_calls) if response.tool_calls else 0,
                "processing_time": response.processing_time
            }
        )
        session.messages.append(assistant_message)

        # 更新会话时间戳
        session.updated_at = datetime.now()

        return response

    async def cleanup(self):
        """清理资源"""
        await self.orchestrator.cleanup()
