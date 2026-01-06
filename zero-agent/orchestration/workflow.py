"""
工作流管理器
"""

import time
import logging
from typing import Dict, Any, AsyncIterator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .state import AgentState
from tools.executor import ToolExecutor
from config.models import StreamChunk

logger = logging.getLogger(__name__)

class WorkflowManager:
    """工作流管理器"""

    def __init__(self, tool_executor: ToolExecutor):
        self.tool_executor = tool_executor
        # MVP版本暂时不使用checkpointer，避免复杂性
        self.checkpointer = None
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        """创建LangGraph状态图"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("receive_message", self._receive_message)
        workflow.add_node("call_llm", self._call_llm)
        workflow.add_node("execute_tools", self._execute_tools)
        workflow.add_node("respond", self._respond)

        # 设置入口点
        workflow.set_entry_point("receive_message")

        # 添加边
        workflow.add_edge("receive_message", "call_llm")
        workflow.add_edge("execute_tools", "call_llm")
        workflow.add_edge("respond", END)

        # 添加条件边
        workflow.add_conditional_edges(
            "call_llm",
            self._should_continue,
            {
                "execute_tools": "execute_tools",
                "respond": "respond"
            }
        )

        # 编译图
        return workflow.compile(checkpointer=self.checkpointer)

    def _receive_message(self, state: AgentState) -> AgentState:
        """接收消息节点"""
        state["processing_time"] = time.time()
        return state

    def _call_llm(self, state: AgentState) -> AgentState:
        """调用LLM节点"""
        try:
            # 这里需要注入LLM实例，稍后在OrchestratorAgent中设置
            llm_with_tools = getattr(self, '_llm_with_tools', None)
            if not llm_with_tools:
                raise ValueError("LLM not initialized")

            logger.info(f"LLM调用 - 迭代 {state['iteration_count']}")
            response = llm_with_tools.invoke(state["messages"])

            # 检查是否有工具调用
            tool_calls = []
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tc in response.tool_calls:
                    tool_call = {
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "arguments": tc.get("args", {})
                    }
                    tool_calls.append(tool_call)

                logger.info(f"检测到 {len(tool_calls)} 个工具调用")
            else:
                logger.info("LLM响应完成，无工具调用")

            state["messages"] = state["messages"] + [response]
            state["tool_calls"] = tool_calls
            state["iteration_count"] += 1

        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise

        return state

    async def _execute_tools(self, state: AgentState) -> AgentState:
        """执行工具节点"""
        if not state["tool_calls"]:
            return state

        try:
            logger.info(f"执行 {len(state['tool_calls'])} 个工具")
            executed_results = []

            for tool_call in state["tool_calls"]:
                result = await self.tool_executor.execute(
                    tool_call["name"],
                    tool_call["arguments"]
                )

                tool_message = ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                )
                executed_results.append(tool_message)

            state["messages"] = state["messages"] + executed_results
            logger.info("工具执行完成")

        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            # 工具调用失败时抛出异常，中止执行
            raise RuntimeError(f"工具执行失败: {str(e)}") from e

        return state

    def _respond(self, state: AgentState) -> AgentState:
        """响应节点"""
        state["processing_time"] = time.time() - state["processing_time"]
        return state

    def _should_continue(self, state: AgentState) -> str:
        """判断是否继续"""
        if state["iteration_count"] >= state["max_iterations"]:
            return "respond"

        if state["tool_calls"]:
            return "execute_tools"

        return "respond"


    def set_llm(self, llm_with_tools):
        """设置LLM实例"""
        self._llm_with_tools = llm_with_tools

    def set_streaming_llm(self, streaming_llm, langchain_tools=None):
        """设置流式LLM实例"""
        self._streaming_llm = streaming_llm
        self._langchain_tools = langchain_tools or []

    async def execute(self, initial_state: AgentState, config: Dict[str, Any]) -> AgentState:
        """执行工作流"""
        if self.checkpointer:
            return await self.graph.ainvoke(initial_state, config)
        else:
            # 不使用checkpointer的简单执行
            return await self.graph.ainvoke(initial_state)

    async def execute_stream(self, initial_state: AgentState, config: Dict[str, Any]) -> AsyncIterator[StreamChunk]:
        """流式执行工作流"""
        streaming_llm = getattr(self, '_streaming_llm', None)
        if not streaming_llm:
            error_msg = "Streaming LLM not configured"
            logger.error(error_msg)
            yield StreamChunk(
                type="error",
                error=error_msg,
                done=True
            )
            return

        # 简化版本：直接流式调用LLM，不支持复杂的工具调用循环
        messages = initial_state["messages"]
        tools = getattr(self, '_langchain_tools', [])

        try:
            async for chunk_data in streaming_llm.stream_chat_with_tools(messages, tools):
                yield StreamChunk(**chunk_data)

            # 发送完成信号
            processing_time = time.time() - initial_state.get("processing_time", time.time())

            yield StreamChunk(
                type="done",
                done=True,
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"流式执行失败: {e}")
            yield StreamChunk(
                type="error",
                error=str(e),
                done=True
            )
            return
