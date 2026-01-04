"""
统一Agent接口 - 整合所有层
"""

from typing import Optional, Any

from orchestration.agent import OrchestratorAgent
from config.models import AgentConfig, ChatRequest, ChatResponse


class UniversalAgent:
    """通用Agent接口（无状态推理引擎）"""

    def __init__(self, config: AgentConfig):
        self.orchestrator = OrchestratorAgent(config)
        self._initialized = False

    async def initialize(self):
        """异步初始化agent"""
        if not self._initialized:
            await self.orchestrator.initialize_async()
            self._initialized = True

    async def chat_with_history(self, request: ChatRequest) -> ChatResponse:
        """带完整历史上下文的对话接口"""
        # 执行对话（传递消息历史）
        response = await self.orchestrator.chat_with_history(request)
        return response

    async def cleanup(self):
        """清理资源"""
        await self.orchestrator.cleanup()
