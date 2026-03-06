"""
编排Agent - 协调各个组件
"""

from typing import Dict, Any, AsyncIterator, List
import asyncio
import time
import logging
import os
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from .state import AgentState
from .workflow import WorkflowManager
from llm.factory import LLMFactory
from tools.registry import ToolRegistry
from tools.executor import ToolExecutor
from tools.manager import ToolManager
from skills.manager import SkillManager
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
        
        # 初始化 Skill 管理器
        self.skill_manager = SkillManager()
        # 设置 Skill 基础路径（项目根目录）
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.skill_manager.set_base_path(base_path)

    async def initialize_async(self):
        """异步初始化 - 并行加载 Skill 和 MCP 工具，然后绑定到LLM"""
        logger.debug(f"开始初始化 Agent: {self.config.id}")
        
        try:
            await self._initialize_skill_and_mcp()
            tool_count = self._bind_tools_to_llm()
            self._configure_workflow()
            logger.info(f"Agent {self.config.id} 初始化完成，工具数量: {tool_count}")

        except Exception as e:
            logger.error(f"Agent 初始化失败: {str(e)}", exc_info=True)
            raise RuntimeError(f"Agent初始化失败: {str(e)}") from e

    async def _initialize_skill_and_mcp(self):
        """并行初始化 Skill 和 MCP，并记录降级信息。"""
        start_time = time.time()
        logger.debug(f"并行初始化 - Skill 数量: {len(self.config.skills)}, MCP 服务器数量: {len(self.config.mcp_servers)}")

        skill_task = self.skill_manager.load_skills_from_config(self.config.skills)
        mcp_task = self.tool_manager.register_mcp_tools(
            self.tool_registry,
            self.config.mcp_servers,
            self.config.mcp_tools
        )

        # 捕获所有异常，初始化阶段尽量不因 MCP/Skill 子任务失败而中断
        try:
            results = await asyncio.gather(skill_task, mcp_task, return_exceptions=True)
            self._handle_parallel_init_results(results)
        except asyncio.CancelledError:
            logger.warning("初始化过程被取消，继续执行")
        except Exception as e:
            logger.error(f"初始化过程中出错: {str(e)}", exc_info=True)

        init_time = time.time() - start_time
        logger.info(f"Skill 和 MCP 初始化完成，耗时: {init_time:.2f}秒")

    def _handle_parallel_init_results(self, results: List[Any]):
        """处理并行初始化结果（Skill + MCP）。"""
        for index, result in enumerate(results):
            if isinstance(result, BaseException):
                task_name = "Skill" if index == 0 else "MCP"
                if isinstance(result, asyncio.CancelledError):
                    logger.warning(f"{task_name} 初始化被取消，继续执行")
                elif isinstance(result, Exception):
                    logger.error(f"{task_name} 初始化失败: {str(result)}", exc_info=result)
                else:
                    logger.error(f"{task_name} 初始化失败: {type(result).__name__}: {str(result)}")
                continue

            if index == 1 and isinstance(result, dict):
                self._log_mcp_degraded_summary(result)

    def _log_mcp_degraded_summary(self, mcp_summary: Dict[str, Any]):
        """记录 MCP 降级摘要。"""
        failed_servers = mcp_summary.get("failed_servers", 0)
        if failed_servers <= 0:
            return

        enabled_servers = mcp_summary.get("enabled_servers", 0)
        failed_server_ids = mcp_summary.get("failed_server_ids", [])
        logger.warning(
            "MCP 以降级模式运行: %s/%s 个服务器不可用 (%s)",
            failed_servers,
            enabled_servers,
            ", ".join(failed_server_ids) if failed_server_ids else "unknown"
        )

    def _bind_tools_to_llm(self) -> int:
        """将当前工具注册表绑定到 LLM，并返回工具数量。"""
        langchain_tools = self.tool_registry.get_langchain_tools()
        logger.debug(f"绑定 {len(langchain_tools)} 个工具到 LLM")
        self.llm_with_tools = self.llm.bind_tools(langchain_tools)
        return len(langchain_tools)

    def _configure_workflow(self):
        """从配置加载超时和并发设置，并应用到工作流。"""
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

        concurrency = self.config.concurrency
        max_concurrent_tools = concurrency.get("max_tools", 5)  # 默认 5 个并发工具
        self.workflow.set_concurrency_limits(max_concurrent_tools=max_concurrent_tools)

        logger.debug(f"超时配置: LLM={llm_timeout}s, 工具={tool_timeout}s, 工作流={workflow_timeout}s")
        logger.debug(f"并发配置: 最大并发工具数={max_concurrent_tools}")

    def _register_builtin_tools(self):
        """注册内置工具 - 使用配置驱动的方式"""
        self.tool_manager.register_tools_from_config(self.tool_registry, self.config.tools)

    def _convert_request_messages(self, request: ChatRequest) -> tuple[List[Any], int]:
        """将请求中的历史消息转换为 LangChain 消息列表，并附加当前用户消息。"""
        messages: List[Any] = []
        history_count = 0

        if hasattr(request, "message_history") and request.message_history:
            history_count = len(request.message_history)
            logger.debug(f"转换消息历史，历史消息数: {history_count}")
            for msg_data in request.message_history:
                role = msg_data.get("role", "").lower()
                content = msg_data.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=request.message))
        return messages, history_count

    def _prepare_messages_with_skill(self, request: ChatRequest) -> tuple[List[Any], int, int]:
        """准备消息并注入 Skill 上下文，返回 (messages, history_count, skill_count)。"""
        messages, history_count = self._convert_request_messages(request)
        skill_messages = self._build_skill_context_messages()
        messages = skill_messages + messages  # 将 Skill 上下文放在最前面
        return messages, history_count, len(skill_messages)

    def _get_required_session_id(self, request: ChatRequest) -> str:
        """获取并校验 session_id（必需字段）。"""
        if not request.session_id:
            raise ValueError("session_id 是必需字段，必须由网关传入")
        return request.session_id

    def _build_initial_state(
        self,
        messages: List[Any],
        session_id: str,
        metadata: Dict[str, Any],
        processing_time: float
    ) -> AgentState:
        """构建工作流初始状态。"""
        max_iterations = self.config.function_call.get("max_iterations", 5)
        initial_state: AgentState = {
            "messages": messages,
            "session_id": session_id,
            "agent_id": self.config.id,
            "tool_calls": [],
            "iteration_count": 0,
            "max_iterations": max_iterations,
            "processing_time": processing_time,
            "errors": [],
            "metadata": metadata
        }
        logger.debug(f"初始状态准备完成，max_iterations: {max_iterations}")
        return initial_state

    def _prepare_request_state(self, request: ChatRequest, processing_time: float) -> tuple[str, AgentState]:
        """准备请求上下文并构建初始状态。"""
        messages, history_count, skill_count = self._prepare_messages_with_skill(request)
        logger.debug(f"消息总数: {len(messages)} (历史: {history_count}, 当前: 1, Skill上下文: {skill_count})")

        session_id = self._get_required_session_id(request)
        logger.debug(f"会话ID: {session_id}")

        initial_state = self._build_initial_state(
            messages=messages,
            session_id=session_id,
            metadata=request.metadata or {},
            processing_time=processing_time
        )
        return session_id, initial_state

    async def chat_with_history(self, request: ChatRequest) -> ChatResponse:
        """处理带历史上下文的对话"""
        logger.debug(f"收到对话请求，agent_id: {self.config.id}")
        session_id, initial_state = self._prepare_request_state(request, processing_time=0.0)

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
        session_id, initial_state = self._prepare_request_state(request, processing_time=time.time())

        # 流式执行
        config = {"configurable": {"thread_id": session_id}}
        logger.debug("开始流式执行工作流")
        chunk_count = 0
        async for chunk in self.workflow.execute_stream(initial_state, config):
            chunk_count += 1
            logger.debug(f"产生流式数据块 #{chunk_count}, 类型: {chunk.type}")
            yield chunk
        logger.info(f"流式执行完成，共产生 {chunk_count} 个数据块")


    def _build_skill_context_messages(self) -> List[SystemMessage]:
        """构建 Skill 上下文消息"""
        skills = self.skill_manager.get_active_skills()
        if not skills:
            return []
        
        context_messages = []
        for skill in skills:
            if skill.load_level == "metadata":
                # Level 1: 仅注入名称和描述
                context = f"可用技能: {skill.metadata.name}\n描述: {skill.metadata.description}"
                if skill.metadata.examples:
                    context += f"\n示例: {', '.join(skill.metadata.examples[:2])}"
            elif skill.load_level == "full":
                # Level 2: 注入完整内容
                context = f"技能指南: {skill.metadata.name}\n\n{skill.content}"
            else:
                # Level 3: 注入所有资源
                context = f"技能指南: {skill.metadata.name}\n\n{skill.content}"
                if skill.resources:
                    context += "\n\n资源文件:\n"
                    for name, content in skill.resources.items():
                        if isinstance(content, str) and len(content) < 1000:
                            context += f"\n{name}:\n{content}\n"
            
            context_messages.append(SystemMessage(content=context))
        
        return context_messages

    async def cleanup(self):
        """清理资源"""
        await self.tool_manager.cleanup_mcp_clients()
        self.skill_manager.clear()