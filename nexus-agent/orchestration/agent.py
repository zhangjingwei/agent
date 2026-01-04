"""
编排Agent - 协调各个组件
"""

from typing import Dict, Any, AsyncIterator
import asyncio
import time
from langchain_core.messages import HumanMessage, AIMessage

from .state import AgentState
from .workflow import WorkflowManager
from llm.factory import LLMFactory
from tools.registry import ToolRegistry
from tools.executor import ToolExecutor
from tools.manager import ToolManager
from config.models import AgentConfig, ChatRequest, ChatResponse, StreamChunk


class OrchestratorAgent:
    """编排Agent"""

    def __init__(self, config: AgentConfig):
        self.config = config

        # 初始化LLM
        llm_config = config.llm_config
        self.llm = LLMFactory.create_llm(
            provider=llm_config.get("provider"),
            api_key=llm_config.get("api_key"),
            model=llm_config.get("model"),
            temperature=0.7
        )

        # 初始化流式LLM
        self.streaming_llm = LLMFactory.create_streaming_llm(
            provider=llm_config.get("provider"),
            api_key=llm_config.get("api_key"),
            model=llm_config.get("model"),
            temperature=0.7
        )

        # 初始化工具层
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.tool_manager = ToolManager()

        # 注册内置工具
        self._register_builtin_tools()

        # 初始化工作流（暂时不绑定工具，会在异步初始化中完成）
        self.workflow = WorkflowManager(self.tool_executor)
        self.llm_with_tools = None  # 会在异步初始化中设置

    async def initialize_async(self):
        """异步初始化 - 注册MCP工具并绑定到LLM"""
        try:
            # 注册MCP工具
            await self.tool_manager.register_mcp_tools(
                self.tool_registry,
                self.config.mcp_servers,
                self.config.mcp_tools
            )

            # 重新绑定工具到LLM
            langchain_tools = self.tool_registry.get_langchain_tools()
            self.llm_with_tools = self.llm.bind_tools(langchain_tools)
            self.workflow.set_llm(self.llm_with_tools)

            # 设置流式LLM
            self.workflow.set_streaming_llm(self.streaming_llm, langchain_tools)

            print("DEBUG: LLM with MCP tools set to workflow")

        except Exception as e:
            print(f"ERROR: MCP工具注册失败: {str(e)}")
            # 即使MCP失败，也要确保基本的LLM功能可用
            if self.llm_with_tools is None:
                langchain_tools = self.tool_registry.get_langchain_tools()
                self.llm_with_tools = self.llm.bind_tools(langchain_tools)
                self.workflow.set_llm(self.llm_with_tools)
                self.workflow.set_streaming_llm(self.streaming_llm, langchain_tools)

    def _register_builtin_tools(self):
        """注册内置工具 - 使用配置驱动的方式"""
        self.tool_manager.register_tools_from_config(self.tool_registry, self.config.tools)

    async def chat_with_history(self, request: ChatRequest) -> ChatResponse:
        """处理带历史上下文的对话"""
        # 转换消息历史为LangChain格式
        messages = []
        if hasattr(request, 'message_history') and request.message_history:
            for msg_data in request.message_history:
                role = msg_data.get("role", "").lower()
                content = msg_data.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        # 添加当前用户消息
        messages.append(HumanMessage(content=request.message))

        # 生成session_id（如果没有的话）
        session_id = getattr(request, 'session_id', None) or f"temp-{hash(request.message)}"

        # 准备初始状态
        initial_state: AgentState = {
            "messages": messages,
            "session_id": session_id,
            "agent_id": self.config.id,
            "tool_calls": [],
            "iteration_count": 0,
            "max_iterations": 5,
            "processing_time": 0.0,
            "errors": [],
            "metadata": request.metadata or {}
        }

        # 执行对话流
        config = {"configurable": {"thread_id": session_id}}
        final_state = await self.workflow.execute(initial_state, config)

        # 提取响应
        message = ""
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                message = msg.content
                break

        return ChatResponse(
            message=message,
            tool_calls=final_state["tool_calls"],
            processing_time=final_state["processing_time"]
        )

    async def chat_with_history_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """流式对话接口"""
        # 转换消息历史为LangChain格式
        messages = []
        if hasattr(request, 'message_history') and request.message_history:
            for msg_data in request.message_history:
                role = msg_data.get("role", "").lower()
                content = msg_data.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        # 添加当前用户消息
        messages.append(HumanMessage(content=request.message))

        # 生成session_id
        session_id = getattr(request, 'session_id', None) or f"temp-{hash(request.message)}"

        # 准备初始状态
        initial_state: AgentState = {
            "messages": messages,
            "session_id": session_id,
            "agent_id": self.config.id,
            "tool_calls": [],
            "iteration_count": 0,
            "max_iterations": 5,
            "processing_time": time.time(),
            "errors": [],
            "metadata": request.metadata or {}
        }

        # 流式执行
        config = {"configurable": {"thread_id": session_id}}

        async for chunk in self.workflow.execute_stream(initial_state, config):
            yield chunk


    async def cleanup(self):
        """清理资源"""
        await self.tool_manager.cleanup_mcp_clients()
