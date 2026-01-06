"""
FastAPI应用
"""

from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import structlog

from core import UniversalAgent
from config.models import AgentConfig, ChatRequest
from nexus_agent.filters import FilterManager, FilterMiddleware
from nexus_agent.filters.builtin import (
    AuditRequestFilter,
    AuditResponseFilter,
    AuditConfig,
    InputValidationFilter,
    InputValidationConfig,
    OutputProcessingFilter,
    OutputProcessingConfig
)


# 配置结构化日志
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# 全局变量
agent: Optional[UniversalAgent] = None
filter_manager: Optional[FilterManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global agent

    logger.info("Starting Universal Agent MVP")

    # 初始化组件
    try:
        # 加载配置（简化版本，实际应该从配置文件加载）
        from config import get_agent_config
        config = get_agent_config()

        # 初始化Agent
        agent = UniversalAgent(config)

        # 初始化过滤器管理器
        global filter_manager
        filter_manager = FilterManager(logger)

        # 从配置注册过滤器
        register_filters_from_config(filter_manager, config, logger)

        # 异步初始化（包括MCP服务启动）
        await agent.initialize()

        logger.info("Agent and filters initialized successfully", agent_id=config.id)

    except Exception as e:
        logger.error("Failed to initialize agent", error=str(e))
        raise

    yield

    # 应用关闭时的清理
    if agent:
        await agent.cleanup()

    logger.info("Shutting down Universal Agent MVP")


# 创建FastAPI应用
app = FastAPI(
    title="Universal Agent API",
    description="通用Agent框架MVP版本API",
    version="0.1.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP版本允许所有源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加过滤器中间件
if filter_manager:
    app.add_middleware(FilterMiddleware, filter_manager=filter_manager)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志中间件"""
    import time
    start_time = time.time()

    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host
    )

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        process_time=f"{process_time:.3f}s"
    )

    return response


@app.get("/")
async def root():
    """根路径"""
    return {"message": "Universal Agent MVP", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """健康检查"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    import datetime
    return {
        "status": "healthy",
        "agent_id": agent.orchestrator.config.id,
        "tools_count": len(agent.orchestrator.tool_registry._tools),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


# Session 由Go网关统一管理
# 推理引擎无状态
@app.post("/chat")
async def chat_with_history(chat_request: ChatRequest):
    """发送消息（带完整历史上下文）"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not available")

    try:
        # 传递消息历史作为上下文
        response = await agent.chat_with_history(chat_request)

        return {
            "message": response.message,
            "tool_calls": [
                {
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                    "result": call.result,
                    "error": call.error,
                    "execution_time": call.execution_time
                }
                for call in response.tool_calls
            ] if response.tool_calls else [],
            "usage": response.usage,
            "processing_time": response.processing_time
        }

    except ValueError as e:
        logger.warning("Invalid chat request", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
    except Exception as e:
        logger.error("Chat processing failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/chat/stream")
async def chat_stream(chat_request: ChatRequest):
    """流式对话接口"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not available")

    try:
        async def generate():
            async for chunk in agent.chat_with_history_stream(chat_request):
                # SSE格式
                data = f"data: {chunk.model_dump_json()}\n\n"
                yield data.encode('utf-8')

        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )

    except ValueError as e:
        logger.warning("Invalid chat stream request", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
    except Exception as e:
        logger.error("Streaming chat processing failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/tools")
async def list_tools():
    """列出可用工具"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        tools = agent.orchestrator.tool_registry.get_all_tools()
        return {
            "tools": [
                {
                    "id": tool.name,
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {}  # 简化处理
                }
                for tool in tools
            ]
        }

    except Exception as e:
        logger.error("Failed to list tools", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/filters/metrics")
async def get_filter_metrics():
    """获取过滤器性能指标"""
    if filter_manager is None:
        raise HTTPException(status_code=503, detail="Filter manager not initialized")

    try:
        metrics = filter_manager.get_metrics()
        return {
            "status": "ok",
            "enabled": filter_manager.is_enabled(),
            "metrics": metrics
        }
    except Exception as e:
        logger.error("Failed to get filter metrics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# 错误处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        url=str(request.url)
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        error=str(exc),
        url=str(request.url),
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


def register_filters_from_config(manager: FilterManager, agent_config, logger):
    """从配置注册过滤器"""
    for filter_config in agent_config.filters:
        if not filter_config.enabled:
            logger.debug(f"Filter {filter_config.name} is disabled, skipping")
            continue

        try:
            if filter_config.type == "audit":
                audit_config = AuditConfig(**filter_config.config)
                # 注册请求审计过滤器
                audit_request_filter = AuditRequestFilter(logger, audit_config)
                manager.register_request_filter(audit_request_filter)
                # 注册响应审计过滤器
                audit_response_filter = AuditResponseFilter(logger, audit_config)
                manager.register_response_filter(audit_response_filter)
                logger.info(f"Registered audit filters: {filter_config.name}")

            elif filter_config.type == "input_validation":
                input_config = InputValidationConfig(**filter_config.config)
                input_filter = InputValidationFilter(logger, input_config)
                manager.register_request_filter(input_filter)
                logger.info(f"Registered input validation filter: {filter_config.name}")

            elif filter_config.type == "output_processing":
                output_config = OutputProcessingConfig(**filter_config.config)
                output_filter = OutputProcessingFilter(logger, output_config)
                manager.register_response_filter(output_filter)
                logger.info(f"Registered output processing filter: {filter_config.name}")

            else:
                logger.warn(f"Unknown filter type: {filter_config.type}")

        except Exception as e:
            logger.error(f"Failed to register filter {filter_config.name}: {str(e)}")
            continue

    logger.info("Filters registered from configuration successfully")
