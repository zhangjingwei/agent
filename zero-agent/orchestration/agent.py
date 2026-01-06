"""
编排Agent - 协调各个组件
"""

from typing import Dict, Any, AsyncIterator
import asyncio
import time
import logging
from langchain_core.messages import HumanMessage, AIMessage

from .state import AgentState
from .workflow import WorkflowManager
from llm.factory import LLMFactory
from tools.registry import ToolRegistry
from tools.executor import ToolExecutor
from tools.manager import ToolManager
from config.models import AgentConfig, ChatRequest, ChatResponse, StreamChunk

logger = logging.getLogger(__name__)


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
            temperature=llm_config.get("temperature", 0.7)  # 从配置读取，默认0.7
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
        logger.debug(f"开始初始化 Agent: {self.config.id}")
        try:
            # 注册MCP工具
            logger.debug(f"注册 MCP 工具，服务器数量: {len(self.config.mcp_servers)}, 工具数量: {len(self.config.mcp_tools)}")
            await self.tool_manager.register_mcp_tools(
                self.tool_registry,
                self.config.mcp_servers,
                self.config.mcp_tools
            )

            # 重新绑定工具到LLM
            langchain_tools = self.tool_registry.get_langchain_tools()
            logger.debug(f"绑定 {len(langchain_tools)} 个工具到 LLM")
            self.llm_with_tools = self.llm.bind_tools(langchain_tools)
            
            # 从配置读取超时设置并应用到工作流
            timeouts = self.config.timeouts
            llm_timeout = timeouts.get("llm", 60)  # 默认 60 秒
            tool_timeout = timeouts.get("tool", 30)  # 默认 30 秒
            workflow_timeout = timeouts.get("workflow", 300)  # 默认 300 秒
            self.workflow.set_llm(self.llm_with_tools, llm_timeout)
            self.workflow.set_timeouts(
                llm_timeout=llm_timeout,
                tool_timeout=tool_timeout,
                workflow_timeout=workflow_timeout
            )
            
            # 从配置读取并发控制设置
            concurrency = self.config.concurrency
            max_concurrent_tools = concurrency.get("max_tools", 5)  # 默认 5 个并发工具
            self.workflow.set_concurrency_limits(max_concurrent_tools=max_concurrent_tools)
            
            logger.debug(f"超时配置: LLM={llm_timeout}s, 工具={tool_timeout}s, 工作流={workflow_timeout}s")
            logger.debug(f"并发配置: 最大并发工具数={max_concurrent_tools}")

            logger.info(f"Agent {self.config.id} 初始化完成，工具数量: {len(langchain_tools)}")

        except Exception as e:
            logger.error(f"MCP工具注册失败: {str(e)}", exc_info=True)
            # MCP 是必需的，如果注册失败应该抛出异常
            raise RuntimeError(f"MCP工具注册失败，Agent无法正常工作: {str(e)}") from e

    def _register_builtin_tools(self):
        """注册内置工具 - 使用配置驱动的方式"""
        self.tool_manager.register_tools_from_config(self.tool_registry, self.config.tools)

    async def chat_with_history(self, request: ChatRequest) -> ChatResponse:
        """处理带历史上下文的对话"""
        logger.debug(f"收到对话请求，agent_id: {self.config.id}")
        
        # 转换消息历史为LangChain格式
        messages = []
        history_count = 0
        if hasattr(request, 'message_history') and request.message_history:
            history_count = len(request.message_history)
            logger.debug(f"转换消息历史，历史消息数: {history_count}")
            for msg_data in request.message_history:
                role = msg_data.get("role", "").lower()
                content = msg_data.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        # 添加当前用户消息
        messages.append(HumanMessage(content=request.message))
        logger.debug(f"消息总数: {len(messages)} (历史: {history_count}, 当前: 1)")

        # 使用网关传入的 session_id（必需字段）
        if not request.session_id:
            raise ValueError("session_id 是必需字段，必须由网关传入")
        session_id = request.session_id
        logger.debug(f"会话ID: {session_id}")

        # 准备初始状态
        # 从配置中读取 max_iterations，默认值为 5
        max_iterations = self.config.function_call.get("max_iterations", 5)
        initial_state: AgentState = {
            "messages": messages,
            "session_id": session_id,
            "agent_id": self.config.id,
            "tool_calls": [],
            "iteration_count": 0,
            "max_iterations": max_iterations,
            "processing_time": 0.0,
            "errors": [],
            "metadata": request.metadata or {}
        }
        logger.debug(f"初始状态准备完成，max_iterations: {max_iterations}")

        # 执行对话流
        config = {"configurable": {"thread_id": session_id}}
        logger.debug("开始执行工作流")
        final_state = await self.workflow.execute(initial_state, config)
        logger.debug(f"工作流执行完成，迭代次数: {final_state['iteration_count']}")

        # 提取响应
        message = ""
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                message = msg.content
                break

        logger.debug(f"提取到响应消息，长度: {len(message)} 字符")

        # 从state中提取工具调用（workflow已经处理好的格式）
        from config.models import ToolCall
        tool_calls = [
            ToolCall(
                id=tc_dict.get("id", ""),
                name=tc_dict.get("name", ""),
                arguments=tc_dict.get("arguments", {})
            )
            for tc_dict in final_state["tool_calls"]
        ]
        
        if tool_calls:
            logger.info(f"提取到 {len(tool_calls)} 个工具调用: {[tc.name for tc in tool_calls]}")
        else:
            logger.debug("未检测到工具调用")

        response = ChatResponse(
            message=message,
            tool_calls=tool_calls,
            processing_time=final_state["processing_time"]
        )
        logger.info(f"对话响应构建完成，处理时间: {final_state['processing_time']:.3f}s")
        return response

    async def chat_with_history_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """流式对话接口"""
        logger.debug(f"收到流式对话请求，agent_id: {self.config.id}")
        
        # 转换消息历史为LangChain格式
        messages = []
        history_count = 0
        if hasattr(request, 'message_history') and request.message_history:
            history_count = len(request.message_history)
            logger.debug(f"转换消息历史，历史消息数: {history_count}")
            for msg_data in request.message_history:
                role = msg_data.get("role", "").lower()
                content = msg_data.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        # 添加当前用户消息
        messages.append(HumanMessage(content=request.message))
        logger.debug(f"消息总数: {len(messages)} (历史: {history_count}, 当前: 1)")

        # 使用网关传入的 session_id（必需字段）
        if not request.session_id:
            raise ValueError("session_id 是必需字段，必须由网关传入")
        session_id = request.session_id
        logger.debug(f"会话ID: {session_id}")

        # 准备初始状态
        # 从配置中读取 max_iterations，默认值为 5
        max_iterations = self.config.function_call.get("max_iterations", 5)
        initial_state: AgentState = {
            "messages": messages,
            "session_id": session_id,
            "agent_id": self.config.id,
            "tool_calls": [],
            "iteration_count": 0,
            "max_iterations": max_iterations,
            "processing_time": time.time(),
            "errors": [],
            "metadata": request.metadata or {}
        }
        logger.debug(f"初始状态准备完成，max_iterations: {max_iterations}")

        # 流式执行
        config = {"configurable": {"thread_id": session_id}}
        logger.debug("开始流式执行工作流")
        chunk_count = 0
        async for chunk in self.workflow.execute_stream(initial_state, config):
            chunk_count += 1
            logger.debug(f"产生流式数据块 #{chunk_count}, 类型: {chunk.type}")
            yield chunk
        logger.info(f"流式执行完成，共产生 {chunk_count} 个数据块")


    async def cleanup(self):
        """清理资源"""
        await self.tool_manager.cleanup_mcp_clients()
