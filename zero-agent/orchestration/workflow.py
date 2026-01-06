"""
工作流管理器
"""

import time
import logging
import asyncio
from typing import Dict, Any, AsyncIterator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .state import AgentState
from tools.executor import ToolExecutor
from config.models import StreamChunk
from langchain_core.runnables import Runnable

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
        """执行工具节点（使用LangChain Runnable包装）"""
        if not state["tool_calls"]:
            return state

        try:
            logger.info(f"执行 {len(state['tool_calls'])} 个工具")
            executed_results = []

            for tool_call in state["tool_calls"]:
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                tool_call_id = tool_call["id"]
                
                # 创建Runnable包装器，使工具执行可以被LangGraph事件系统捕获
                tool_runnable = self._create_tool_runnable(tool_name, tool_args, tool_call_id)
                
                # 执行工具（作为Runnable，可以被astream_events捕获）
                tool_result = await tool_runnable.ainvoke({})
                
                tool_message = ToolMessage(
                    content=str(tool_result["result"]),
                    tool_call_id=tool_call_id
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

    def _create_tool_runnable(self, tool_name: str, tool_args: dict, tool_call_id: str) -> Runnable:
        """创建工具执行的Runnable包装器"""
        executor = self.tool_executor
        
        class ToolRunnable(Runnable):
            """工具执行的Runnable包装器"""
            
            def __init__(self, executor: ToolExecutor, name: str, args: dict, call_id: str):
                super().__init__()
                self.executor = executor
                self.tool_name = name
                self.tool_args = args
                self.tool_call_id = call_id
            
            async def ainvoke(self, input_data: dict, config=None):
                """异步执行工具"""
                result = await self.executor.execute(self.tool_name, self.tool_args)
                return {
                    "tool_call_id": self.tool_call_id,
                    "tool_name": self.tool_name,
                    "result": result
                }
            
            @property
            def name(self):
                return f"execute_tool_{self.tool_name}"
        
        return ToolRunnable(executor, tool_name, tool_args, tool_call_id)

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
        """流式执行工作流（使用LangGraph的astream_events统一执行逻辑）
        
        使用LangGraph的流式事件API，与非流式执行使用同一套逻辑，
        确保行为一致，减少代码重复。
        """
        llm_with_tools = getattr(self, '_llm_with_tools', None)
        if not llm_with_tools:
            error_msg = "LLM with tools not configured"
            logger.error(error_msg)
            yield StreamChunk(
                type="error",
                error=error_msg,
                done=True
            )
            return

        try:
            # 记录已处理的工具调用，避免重复输出
            processed_tool_calls = set()
            tool_call_results = {}  # 存储工具执行结果 {tool_call_id: result}
            processing_start_time = initial_state.get("processing_time", time.time())
            last_state = initial_state.copy()
            last_message_count = len(initial_state.get("messages", []))

            # 使用LangGraph的astream_events获取流式事件
            async for event in self.graph.astream_events(initial_state, config, version="v2"):
                event_name = event.get("name", "")
                event_type = event.get("event", "")
                
                # 监听call_llm节点完成事件
                if event_type == "on_chain_end" and event_name == "call_llm":
                    data = event.get("data", {})
                    output = data.get("output")
                    
                    if output:
                        # 提取LLM响应内容
                        if hasattr(output, 'content') and output.content:
                            yield StreamChunk(
                                type="content",
                                content=output.content,
                                done=False
                            )
                        
                        # 提取工具调用
                        if hasattr(output, 'tool_calls') and output.tool_calls:
                            logger.info(f"检测到 {len(output.tool_calls)} 个工具调用")
                            for tc in output.tool_calls:
                                tool_call_id = tc.get("id", "")
                                if tool_call_id not in processed_tool_calls:
                                    processed_tool_calls.add(tool_call_id)
                                    tool_call = {
                                        "id": tool_call_id,
                                        "name": tc.get("name", ""),
                                        "arguments": tc.get("args", {})
                                    }
                                    yield StreamChunk(
                                        type="tool_call_start",
                                        tool_call=tool_call,
                                        done=False
                                    )
                
                # 监听execute_tools节点中的工具执行事件（Runnable执行）
                elif event_type == "on_chain_end" and event_name.startswith("execute_tool_"):
                    # 工具执行完成，提取结果
                    data = event.get("data", {})
                    output = data.get("output", {})
                    
                    if isinstance(output, dict):
                        tool_call_id = output.get("tool_call_id", "")
                        tool_name = output.get("tool_name", "")
                        tool_result = output.get("result", "")
                        
                        if tool_call_id:
                            tool_call_results[tool_call_id] = tool_result
                            logger.info(f"工具 {tool_name} 执行完成")
                            
                            # 流式输出工具执行结果
                            yield StreamChunk(
                                type="tool_call_end",
                                tool_call_id=tool_call_id,
                                result=tool_result,
                                done=False
                            )
                
                # 监听execute_tools节点完成事件
                elif event_type == "on_chain_end" and event_name == "execute_tools":
                    logger.info("所有工具执行完成")
                    
                    # 从状态中提取工具执行结果
                    # 由于工具执行在节点内部，我们需要从状态变化中提取
                    data = event.get("data", {})
                    output = data.get("output", {})
                    if isinstance(output, dict) and "messages" in output:
                        # 检查是否有新的ToolMessage（工具执行结果）
                        messages = output["messages"]
                        current_message_count = len(messages)
                        
                        # 如果消息数量增加了，说明有新的ToolMessage
                        if current_message_count > last_message_count:
                            # 获取新增的消息（应该是ToolMessage）
                            new_messages = messages[last_message_count:]
                            for msg in new_messages:
                                if isinstance(msg, ToolMessage):
                                    tool_call_id = msg.tool_call_id
                                    if tool_call_id not in tool_call_results:
                                        tool_call_results[tool_call_id] = msg.content
                                        yield StreamChunk(
                                            type="tool_call_end",
                                            tool_call_id=tool_call_id,
                                            result=msg.content,
                                            done=False
                                        )
                            
                            last_message_count = current_message_count
                
                # 监听状态更新事件，获取最新状态
                elif event_type == "on_chain_stream":
                    # 获取更新后的状态
                    data = event.get("data", {})
                    if "chunk" in data:
                        chunk = data["chunk"]
                        if isinstance(chunk, dict):
                            last_state.update(chunk)
                
                # 监听respond节点完成事件（工作流完成）
                elif event_type == "on_chain_end" and event_name == "respond":
                    # 从最终状态获取处理时间
                    data = event.get("data", {})
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        processing_time = output.get("processing_time", 0.0)
                    else:
                        processing_time = time.time() - processing_start_time
                    
                    yield StreamChunk(
                        type="done",
                        done=True,
                        processing_time=processing_time
                    )
                    break
                
                # 监听错误事件
                elif event_type == "on_chain_error" or event_type == "on_tool_error":
                    error_data = event.get("data", {})
                    error_msg = str(error_data.get("error", "Unknown error"))
                    logger.error(f"工作流执行错误: {error_msg}")
                    yield StreamChunk(
                        type="error",
                        error=error_msg,
                        done=True
                    )
                    return

        except Exception as e:
            logger.error(f"流式执行失败: {e}", exc_info=True)
            yield StreamChunk(
                type="error",
                error=str(e),
                done=True
            )
            return
