"""
工作流管理器
"""

import time
import logging
import asyncio
import random
from typing import Dict, Any, AsyncIterator, Optional, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .state import AgentState
from tools.executor import ToolExecutor
from config.models import StreamChunk
from langchain_core.runnables import Runnable, RunnableLambda
from core.resource_manager import get_resource_manager
from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

class WorkflowManager:
    """工作流管理器"""

    def __init__(self, tool_executor: ToolExecutor):
        self.tool_executor = tool_executor
        # MVP版本暂时不使用checkpointer，避免复杂性
        self.checkpointer = None
        self.graph = self._create_graph()
        # 超时配置（默认值，可通过 set_timeouts 方法更新）
        self._llm_timeout = 60  # LLM 调用超时（秒）
        self._tool_timeout = 30  # 工具执行超时（秒）
        self._workflow_timeout = 300  # 工作流总体超时（秒）
        # 并发控制配置
        self._max_concurrent_tools = 5  # 最大并发工具数
        # 速率限制和熔断配置
        self._max_retry_attempts = 3  # 最大重试次数（针对429错误）
        self._base_retry_delay = 1.0  # 基础重试延迟（秒）
        self._max_retry_delay = 60.0  # 最大重试延迟（秒）
        # 创建LLM熔断器
        self._llm_circuit_breaker = CircuitBreaker(
            failure_threshold=5,  # 连续5次失败后熔断
            success_threshold=2,  # 半开状态下2次成功恢复
            timeout=60.0,  # 熔断60秒后尝试恢复
            name="llm_provider"
        )

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

    def _is_rate_limit_error(self, error: Exception) -> Tuple[bool, Optional[float]]:
        """检查是否为速率限制错误，并提取重试等待时间
        
        Returns:
            (is_rate_limit, retry_after): 是否为速率限制错误，以及建议的重试等待时间（秒）
        """
        error_str = str(error)
        
        # 检查错误消息中是否包含速率限制相关信息
        rate_limit_indicators = [
            '429',
            'rate limit',
            'rate limiting',
            'RPM limit',
            'TPM limit',
            'quota',
            'too many requests'
        ]
        
        is_rate_limit = any(indicator.lower() in error_str.lower() for indicator in rate_limit_indicators)
        
        # 尝试从错误对象中提取 retry_after 信息
        retry_after = None
        if hasattr(error, 'response'):
            # OpenAI SDK 的错误对象可能有 response 属性
            response = getattr(error, 'response', None)
            if response:
                # 检查响应头中的 retry-after
                if hasattr(response, 'headers'):
                    retry_after_header = response.headers.get('retry-after')
                    if retry_after_header:
                        try:
                            retry_after = float(retry_after_header)
                        except (ValueError, TypeError):
                            pass
                # 检查响应体中的 retry_after
                if retry_after is None and hasattr(response, 'json'):
                    try:
                        error_body = response.json()
                        if isinstance(error_body, dict):
                            retry_after = error_body.get('retry_after') or error_body.get('retryAfter')
                            if retry_after:
                                retry_after = float(retry_after)
                    except Exception:
                        pass
        
        return is_rate_limit, retry_after

    async def _call_llm(self, state: AgentState) -> AgentState:
        """调用LLM节点（异步，支持速率限制重试和熔断保护）"""
        try:
            # 这里需要注入LLM实例，稍后在OrchestratorAgent中设置
            llm_with_tools = getattr(self, '_llm_with_tools', None)
            if not llm_with_tools:
                raise ValueError("LLM not initialized")

            iteration = state['iteration_count']
            message_count = len(state["messages"])
            logger.info(f"LLM调用 - 迭代 {iteration + 1}/{state['max_iterations']}, 消息数: {message_count}")
            logger.debug(f"发送给LLM的消息: {[msg.__class__.__name__ for msg in state['messages']]}")
            
            # 检查熔断器状态
            circuit_state = self._llm_circuit_breaker.get_state()
            if circuit_state.value == "open":
                error_msg = "LLM服务已熔断，请求被拒绝"
                logger.error(error_msg)
                state["errors"].append(error_msg)
                raise CircuitBreakerOpenError(error_msg)
            
            # 获取配置
            llm_timeout = getattr(self, '_llm_timeout', 60)
            max_retry_attempts = getattr(self, '_max_retry_attempts', 3)
            base_retry_delay = getattr(self, '_base_retry_delay', 1.0)
            max_retry_delay = getattr(self, '_max_retry_delay', 60.0)
            
            # 定义实际的LLM调用函数
            async def _invoke_llm():
                return await asyncio.wait_for(
                    llm_with_tools.ainvoke(state["messages"]),
                    timeout=llm_timeout
                )
            
            # 重试循环（针对429错误）
            # 注意：熔断器会在每次调用时自动记录成功/失败
            last_error = None
            response = None
            
            for attempt in range(max_retry_attempts + 1):
                try:
                    # 通过熔断器调用（会自动记录成功/失败）
                    response = await self._llm_circuit_breaker.call_async(_invoke_llm)
                    # 成功获取响应，跳出重试循环
                    break
                    
                except CircuitBreakerOpenError:
                    # 熔断器已打开，直接抛出
                    error_msg = "LLM服务已熔断，请求被拒绝"
                    logger.error(error_msg)
                    state["errors"].append(error_msg)
                    raise
                    
                except asyncio.TimeoutError:
                    # 超时错误，熔断器已自动记录失败
                    error_msg = f"LLM调用超时（超过 {llm_timeout} 秒）"
                    logger.error(error_msg)
                    state["errors"].append(error_msg)
                    raise TimeoutError(error_msg)
                    
                except Exception as e:
                    last_error = e
                    is_rate_limit, retry_after = self._is_rate_limit_error(e)
                    
                    # 如果是速率限制错误且还有重试机会，则重试
                    if is_rate_limit and attempt < max_retry_attempts:
                        # 计算重试延迟（指数退避 + 抖动）
                        if retry_after:
                            # 使用 API 建议的重试时间
                            delay = min(float(retry_after), max_retry_delay)
                        else:
                            # 指数退避：base_delay * (2 ^ attempt) + 随机抖动
                            delay = min(
                                base_retry_delay * (2 ** attempt) + random.uniform(0, 1),
                                max_retry_delay
                            )
                        
                        logger.warning(
                            f"LLM调用遇到速率限制（429），第 {attempt + 1}/{max_retry_attempts} 次重试，"
                            f"等待 {delay:.2f} 秒后重试。错误: {str(e)}"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # 不是速率限制错误，或者已达到最大重试次数
                        # 熔断器已自动记录失败（通过call_async）
                        if is_rate_limit:
                            logger.error(
                                f"LLM速率限制重试失败，已达到最大重试次数 {max_retry_attempts}，"
                                f"熔断器状态: {self._llm_circuit_breaker.get_state().value}"
                            )
                        raise
            
            # 如果所有重试都失败，抛出最后一个错误
            if last_error and response is None:
                raise last_error
            
            logger.debug(f"LLM响应类型: {type(response).__name__}, 内容长度: {len(response.content) if hasattr(response, 'content') else 0}")

            # 检查是否有工具调用
            # LangChain的AIMessage.tool_calls返回的是字典列表，格式：{"id": "...", "name": "...", "args": {...}}
            tool_calls = []
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.debug(f"LLM返回了 {len(response.tool_calls)} 个工具调用")
                for tc in response.tool_calls:
                    tool_call = {
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "arguments": tc.get("args", {})  # LangChain使用"args"字段
                    }
                    tool_calls.append(tool_call)
                    logger.debug(f"工具调用: {tool_call['name']} (id: {tool_call['id']}), 参数: {tool_call['arguments']}")

                logger.info(f"检测到 {len(tool_calls)} 个工具调用: {[tc.get('name', 'unknown') for tc in tool_calls]}")
            else:
                logger.debug("LLM响应完成，无工具调用")
                logger.info("LLM响应完成，无工具调用")

            state["messages"] = state["messages"] + [response]
            state["tool_calls"] = tool_calls
            state["iteration_count"] += 1
            logger.debug(f"状态更新完成，迭代次数: {state['iteration_count']}, 工具调用数: {len(tool_calls)}")

        except asyncio.TimeoutError:
            error_msg = f"LLM调用超时（超过 {self._llm_timeout} 秒）"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            raise TimeoutError(error_msg)
        except Exception as e:
            error_msg = f"LLM调用失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            state["errors"].append(error_msg)
            # 不直接抛出异常，而是记录错误并返回状态，让工作流决定如何处理
            raise

        return state

    async def _execute_tools(self, state: AgentState) -> AgentState:
        """执行工具节点（支持并发执行）"""
        if not state["tool_calls"]:
            logger.debug("无工具调用需要执行")
            return state

        try:
            tool_count = len(state['tool_calls'])
            logger.info(f"执行 {tool_count} 个工具（并发模式）")
            
            # 获取并发控制配置
            max_concurrent_tools = getattr(self, '_max_concurrent_tools', 5)
            tool_timeout = getattr(self, '_tool_timeout', 30)
            
            # 创建信号量控制并发数
            semaphore = asyncio.Semaphore(max_concurrent_tools)
            
            async def execute_single_tool(tool_call: Dict[str, Any], idx: int) -> tuple[str, ToolMessage, Optional[str]]:
                """执行单个工具，返回 (tool_call_id, tool_message, error)"""
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                tool_call_id = tool_call["id"]
                
                # 获取全局资源管理器
                resource_manager = get_resource_manager()
                
                # 同时使用本地信号量和全局信号量控制并发
                async with semaphore:  # 本地并发控制
                    async with resource_manager.acquire_tool():  # 全局并发控制
                        logger.debug(f"执行工具 [{idx}/{tool_count}]: {tool_name} (id: {tool_call_id})")
                        logger.debug(f"工具参数: {tool_args}")
                        
                        # 创建Runnable包装器
                        tool_runnable = self._create_tool_runnable(tool_name, tool_args, tool_call_id)
                        
                        start_time = time.time()
                        try:
                            # 执行工具，带超时控制
                            tool_result = await asyncio.wait_for(
                                tool_runnable.ainvoke({}),
                                timeout=tool_timeout
                            )
                            execution_time = time.time() - start_time
                            
                            logger.debug(f"工具 {tool_name} 执行完成，耗时: {execution_time:.3f}s")
                            
                            tool_message = ToolMessage(
                                content=str(tool_result["result"]),
                                tool_call_id=tool_call_id
                            )
                            return (tool_call_id, tool_message, None)
                            
                        except asyncio.TimeoutError:
                            execution_time = time.time() - start_time
                            error_msg = f"工具 {tool_name} 执行超时（超过 {tool_timeout} 秒）"
                            logger.error(error_msg)
                            return (tool_call_id, None, error_msg)
                        except Exception as e:
                            execution_time = time.time() - start_time
                            error_msg = f"工具 {tool_name} 执行失败: {str(e)}"
                            logger.error(error_msg, exc_info=True)
                            return (tool_call_id, None, error_msg)
            
            # 并发执行所有工具
            tasks = [
                execute_single_tool(tool_call, idx + 1)
                for idx, tool_call in enumerate(state["tool_calls"])
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理执行结果
            executed_results = []
            errors = []
            for result in results:
                if isinstance(result, Exception):
                    # 任务本身抛出异常（不应该发生，因为我们在函数内捕获了）
                    error_msg = f"工具执行任务异常: {str(result)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
                else:
                    tool_call_id, tool_message, error = result
                    if error:
                        errors.append(error)
                        # 即使失败也创建错误消息，让LLM知道工具调用失败
                        tool_message = ToolMessage(
                            content=f"工具执行失败: {error}",
                            tool_call_id=tool_call_id
                        )
                        executed_results.append(tool_message)
                    elif tool_message:
                        executed_results.append(tool_message)

            # 更新状态
            state["messages"] = state["messages"] + executed_results
            if errors:
                state["errors"].extend(errors)
                logger.warning(f"部分工具执行失败: {len(errors)}/{tool_count}")
            
            logger.info(f"所有工具执行完成，共 {tool_count} 个工具，成功: {len(executed_results)}, 失败: {len(errors)}")

        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            state["errors"].append(error_msg)
            # 如果所有工具都失败，抛出异常中止执行
            # 否则继续执行，让LLM知道部分工具失败
            if len(state["errors"]) >= tool_count:
                raise RuntimeError(f"所有工具执行失败: {error_msg}") from e
            # 部分失败时，创建错误消息让LLM知道
            for tool_call in state["tool_calls"]:
                if not any(r.tool_call_id == tool_call["id"] for r in executed_results if hasattr(r, 'tool_call_id')):
                    error_message = ToolMessage(
                        content=f"工具 {tool_call['name']} 执行失败",
                        tool_call_id=tool_call["id"]
                    )
                    executed_results.append(error_message)
            state["messages"] = state["messages"] + executed_results

        return state

    def _respond(self, state: AgentState) -> AgentState:
        """响应节点"""
        state["processing_time"] = time.time() - state["processing_time"]
        return state

    def _create_tool_runnable(self, tool_name: str, tool_args: dict, tool_call_id: str) -> Runnable:
        """创建工具执行的Runnable包装器
        
        使用RunnableLambda从异步函数创建Runnable，简化实现
        """
        executor = self.tool_executor
        
        async def execute_tool(input_data: dict):
            """异步执行工具的函数"""
            result = await executor.execute(tool_name, tool_args)
            return {
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "result": result
            }
        
        # 使用RunnableLambda从异步函数创建Runnable
        # RunnableLambda会自动处理invoke和ainvoke方法
        runnable = RunnableLambda(execute_tool)
        # 设置名称以便在事件中识别
        runnable.name = f"execute_tool_{tool_name}"
        return runnable

    def _should_continue(self, state: AgentState) -> str:
        """判断是否继续"""
        if state["iteration_count"] >= state["max_iterations"]:
            return "respond"

        if state["tool_calls"]:
            return "execute_tools"

        return "respond"


    def set_llm(self, llm_with_tools, llm_timeout: int = 60):
        """设置LLM实例和超时配置"""
        self._llm_with_tools = llm_with_tools
        self._llm_timeout = llm_timeout

    def set_timeouts(self, llm_timeout: int = None, tool_timeout: int = None, workflow_timeout: int = None):
        """设置超时配置"""
        if llm_timeout is not None:
            self._llm_timeout = llm_timeout
        if tool_timeout is not None:
            self._tool_timeout = tool_timeout
        if workflow_timeout is not None:
            self._workflow_timeout = workflow_timeout

    def set_concurrency_limits(self, max_concurrent_tools: int = None):
        """设置并发控制配置"""
        if max_concurrent_tools is not None:
            self._max_concurrent_tools = max_concurrent_tools

    def set_retry_config(
        self,
        max_retry_attempts: int = None,
        base_retry_delay: float = None,
        max_retry_delay: float = None
    ):
        """设置速率限制重试配置
        
        Args:
            max_retry_attempts: 最大重试次数（默认 3）
            base_retry_delay: 基础重试延迟，秒（默认 1.0）
            max_retry_delay: 最大重试延迟，秒（默认 60.0）
        """
        if max_retry_attempts is not None:
            self._max_retry_attempts = max_retry_attempts
        if base_retry_delay is not None:
            self._base_retry_delay = base_retry_delay
        if max_retry_delay is not None:
            self._max_retry_delay = max_retry_delay

    def set_circuit_breaker_config(
        self,
        failure_threshold: int = None,
        success_threshold: int = None,
        timeout: float = None
    ):
        """设置熔断器配置
        
        Args:
            failure_threshold: 触发熔断的连续失败次数（默认 5）
            success_threshold: 半开状态下需要连续成功的次数（默认 2）
            timeout: 熔断持续时间，秒（默认 60.0）
        """
        if failure_threshold is not None:
            self._llm_circuit_breaker.failure_threshold = failure_threshold
        if success_threshold is not None:
            self._llm_circuit_breaker.success_threshold = success_threshold
        if timeout is not None:
            self._llm_circuit_breaker.timeout = timeout

    def get_circuit_breaker_stats(self) -> dict:
        """获取熔断器统计信息"""
        return self._llm_circuit_breaker.get_stats()

    def reset_circuit_breaker(self):
        """手动重置熔断器"""
        self._llm_circuit_breaker.reset()

    async def execute(self, initial_state: AgentState, config: Dict[str, Any]) -> AgentState:
        """执行工作流（带总体超时控制）"""
        try:
            if self.checkpointer:
                return await asyncio.wait_for(
                    self.graph.ainvoke(initial_state, config),
                    timeout=self._workflow_timeout
                )
            else:
                # 不使用checkpointer的简单执行
                return await asyncio.wait_for(
                    self.graph.ainvoke(initial_state),
                    timeout=self._workflow_timeout
                )
        except asyncio.TimeoutError:
            error_msg = f"工作流执行超时（超过 {self._workflow_timeout} 秒）"
            logger.error(error_msg)
            initial_state["errors"].append(error_msg)
            raise TimeoutError(error_msg)

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
            processed_tool_calls = set()
            processing_start_time = initial_state.get("processing_time", time.time())
            workflow_start_time = time.time()

            # 流式执行，在循环中检查超时
            async for event in self.graph.astream_events(initial_state, config, version="v2"):
                # 检查总体超时
                elapsed = time.time() - workflow_start_time
                if elapsed > self._workflow_timeout:
                    error_msg = f"工作流执行超时（超过 {self._workflow_timeout} 秒）"
                    logger.error(error_msg)
                    yield StreamChunk(
                        type="error",
                        error=error_msg,
                        done=True
                    )
                    return
                event_name = event.get("name", "")
                event_type = event.get("event", "")
                
                # 监听LLM模型完成事件 - 提取LLM响应和工具调用
                # 注意：不检查 event_name，因为不同提供商的名称不同（ChatOpenAI, ChatAnthropic, 等）
                if event_type == "on_chat_model_end":
                    output = event.get("data", {}).get("output")
                    if not output:
                        continue
                    
                    # 提取LLM响应内容
                    if output.content:
                        yield StreamChunk(
                            type="content",
                            content=output.content,
                            done=False
                        )
                    
                    # 提取工具调用
                    if output.tool_calls:
                        for tc in output.tool_calls:
                            tool_call_id = tc.get("id", "")
                            if tool_call_id not in processed_tool_calls:
                                processed_tool_calls.add(tool_call_id)
                                yield StreamChunk(
                                    type="tool_call_start",
                                    tool_call={
                                        "id": tool_call_id,
                                        "name": tc.get("name", ""),
                                        "arguments": tc.get("args", {})
                                    },
                                    done=False
                                )
                
                # 监听工具执行完成事件
                elif event_type == "on_chain_end" and event_name.startswith("execute_tool_"):
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict) and output.get("tool_call_id"):
                        yield StreamChunk(
                            type="tool_call_end",
                            tool_call_id=output["tool_call_id"],
                            result=output.get("result", ""),
                            done=False
                        )
                
                # 监听工作流完成事件
                elif event_type == "on_chain_end" and event_name == "respond":
                    output = event.get("data", {}).get("output", {})
                    processing_time = output.get("processing_time", 0.0) if isinstance(output, dict) else time.time() - processing_start_time
                    
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

        except asyncio.TimeoutError:
            error_msg = f"工作流执行超时（超过 {self._workflow_timeout} 秒）"
            logger.error(error_msg)
            yield StreamChunk(
                type="error",
                error=error_msg,
                done=True
            )
            return
        except Exception as e:
            error_msg = f"流式执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            yield StreamChunk(
                type="error",
                error=error_msg,
                done=True
            )
            return
