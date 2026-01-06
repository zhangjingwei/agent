"""
FastAPI应用
"""

from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import logging
import os
import json

from fastapi import FastAPI, HTTPException, Request, Path as PathParam, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import structlog

from core import ZeroAgentEngine
from core.factory import AgentFactory
from core.resource_manager import get_resource_manager, set_resource_manager, ResourceManager
from config.models import AgentConfig, ChatRequest
from config.loader import ConfigLoader
from filters import FilterManager, FilterMiddleware
from filters.builtin import (
    AuditRequestFilter,
    AuditResponseFilter,
    AuditConfig,
    InputValidationFilter,
    InputValidationConfig,
    OutputProcessingFilter,
    OutputProcessingConfig
)


# 配置标准库日志（在 structlog 之前配置）
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
numeric_level = getattr(logging, log_level, logging.INFO)
logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # 强制重新配置，覆盖之前的配置
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
agent_factory: Optional[AgentFactory] = None
# 提前初始化 filter_manager，以便在应用创建时可以添加中间件
filter_manager: FilterManager = FilterManager(logger)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global agent_factory

    logger.info("Starting Universal Agent MVP")

    # 初始化组件
    try:
        # 初始化全局资源管理器
        max_concurrent_requests = int(os.getenv("MAX_CONCURRENT_REQUESTS", "100"))
        max_concurrent_workflows = int(os.getenv("MAX_CONCURRENT_WORKFLOWS", "50"))
        max_concurrent_tools = int(os.getenv("MAX_CONCURRENT_TOOLS", "20"))
        resource_manager = ResourceManager(
            max_concurrent_requests=max_concurrent_requests,
            max_concurrent_workflows=max_concurrent_workflows,
            max_concurrent_tools=max_concurrent_tools
        )
        set_resource_manager(resource_manager)
        logger.info("Resource manager initialized")
        
        # 初始化 Agent 工厂
        agent_factory = AgentFactory()

        # 加载 Agent 配置
        # 优先从环境变量指定的配置目录加载
        config_dir = os.getenv("AGENT_CONFIG_DIR", "config/agents")
        config_file = os.getenv("AGENT_CONFIG_FILE", None)

        if config_file:
            # 从单个配置文件加载
            logger.info(f"Loading agent from config file: {config_file}")
            config = ConfigLoader.load_from_file(config_file)
            await agent_factory.create_agent(config)
            # 注册过滤器
            register_filters_from_config(filter_manager, config, logger)
        elif os.path.exists(config_dir) and os.path.isdir(config_dir):
            # 从配置目录加载多个 Agent
            logger.info(f"Loading agents from config directory: {config_dir}")
            agents = await agent_factory.create_agents_from_dir(config_dir)
            logger.info(f"Loaded {len(agents)} agents: {list(agents.keys())}")
            # 为每个 Agent 注册过滤器（使用第一个 Agent 的过滤器配置作为默认）
            if agents:
                first_agent_id = list(agents.keys())[0]
                first_config = agent_factory.get_config(first_agent_id)
                if first_config:
                    register_filters_from_config(filter_manager, first_config, logger)
        else:
            # 降级到默认配置（向后兼容）
            logger.warning("Config directory not found, using default config")
            from config import get_agent_config
            config = get_agent_config()
            await agent_factory.create_agent(config)
            register_filters_from_config(filter_manager, config, logger)

        logger.info("Agents and filters initialized successfully")

    except Exception as e:
        logger.error("Failed to initialize agents", error=str(e), exc_info=True)
        raise

    yield

    # 应用关闭时的清理
    if agent_factory:
        await agent_factory.cleanup_all()

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

# 添加过滤器中间件（filter_manager 已提前初始化）
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
    return {"message": "Universal Agent API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """健康检查"""
    if agent_factory is None:
        raise HTTPException(status_code=503, detail="Agent factory not initialized")

    import datetime
    return {
        "service": "zero-agent",
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


@app.get("/agents")
async def list_agents():
    """列出所有可用的 Agent"""
    if agent_factory is None:
        raise HTTPException(status_code=503, detail="Agent factory not initialized")
    
    agents = agent_factory.list_agents()
    return {
        "agents": [
            {
                "id": agent_id,
                "name": name
            }
            for agent_id, name in agents.items()
        ]
    }


@app.post("/agents/{agent_id}/chat")
async def chat_with_agent(
    agent_id: str = PathParam(..., description="Agent ID"),
    chat_request: ChatRequest = ...,
    stream: bool = Query(False, description="是否使用流式输出")
):
    """使用指定 Agent 发送消息（支持流式输出，使用 OpenAI 兼容格式）"""
    if agent_factory is None:
        raise HTTPException(status_code=503, detail="Agent factory not initialized")

    agent = agent_factory.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    # 获取资源管理器并控制并发
    resource_manager = get_resource_manager()
    
    try:
        # 获取请求和工作流资源
        async with resource_manager.acquire_request():
            async with resource_manager.acquire_workflow():
                if stream:
                    # 流式输出（目前使用自定义格式，后续可以添加OpenAI流式格式支持）
                    async def generate():
                        try:
                            async for chunk in agent.chat_with_history_stream(chat_request):
                                data = f"data: {chunk.model_dump_json()}\n\n"
                                yield data.encode('utf-8')
                        except Exception as e:
                            logger.error("Stream generation error", error=str(e), exc_info=True)
                            error_chunk = {"type": "error", "error": str(e), "done": True}
                            yield f"data: {json.dumps(error_chunk)}\n\n".encode('utf-8')

                    return StreamingResponse(
                        generate(),
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "Access-Control-Allow-Origin": "*",
                        }
                    )
                else:
                    # 普通输出，使用OpenAI格式
                    response = await agent.chat_with_history(chat_request)
                    return response.to_dict(format="openai")

    except ValueError as e:
        logger.warning("Invalid chat request", error=str(e), agent_id=agent_id)
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
    except Exception as e:
        logger.error("Chat processing failed", error=str(e), agent_id=agent_id)
        raise HTTPException(status_code=500, detail="Internal server error")


def _serialize_tool(tool) -> Dict[str, Any]:
    """
    序列化工具对象为字典
    
    Args:
        tool: 工具实例
        
    Returns:
        包含工具信息的字典，包括：
        - id: 工具ID
        - name: 工具名称
        - description: 工具描述
        - type: 工具类型（builtin 或 mcp）
        - parameters: 参数schema
        - server_id: MCP工具所属服务器ID（仅MCP工具）
        - server_name: MCP工具所属服务器名称（仅MCP工具）
    """
    tool_type = getattr(tool, 'tool_type', 'builtin')
    tool_dict = {
        "id": tool.name,
        "name": tool.name,
        "description": tool.description,
        "type": tool_type,
        "parameters": tool.get_parameters_schema()
    }
    
    # 如果是 MCP 工具，添加服务器信息
    if tool_type == "mcp" and hasattr(tool, 'server_config'):
        tool_dict["server_id"] = tool.server_config.id
        tool_dict["server_name"] = tool.server_config.name or tool.server_config.id
    
    return tool_dict


@app.get("/agents/{agent_id}/tools")
async def list_agent_tools(agent_id: str = PathParam(..., description="Agent ID")):
    """列出指定 Agent 的可用工具"""
    if agent_factory is None:
        raise HTTPException(status_code=503, detail="Agent factory not initialized")

    agent = agent_factory.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    try:
        tools = agent.orchestrator.tool_registry.get_all_tools()
        
        return {
            "agent_id": agent_id,
            "tools": [_serialize_tool(tool) for tool in tools]
        }
    except Exception as e:
        logger.error("Failed to list tools", error=str(e), agent_id=agent_id)
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
                logger.warning(f"Unknown filter type: {filter_config.type}")

        except Exception as e:
            logger.error(f"Failed to register filter {filter_config.name}: {str(e)}")
            continue

    logger.info("Filters registered from configuration successfully")


def _start_server():
    """启动服务器（提取为独立函数以便复用）"""
    import asyncio
    from pathlib import Path
    
    # 添加项目根目录到 Python 路径
    project_root = Path(__file__).parent.parent
    import sys
    sys.path.insert(0, str(project_root))
    
    # 加载环境变量（如果存在 .env 文件）
    try:
        from dotenv import load_dotenv
        env_file = project_root / '.env'
        if env_file.exists():
            load_dotenv(env_file)
    except ImportError:
        pass  # dotenv 不是必需的
    
    # 获取服务器配置
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8082"))
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # 使用 hypercorn（支持 HTTP/2）
    try:
        from hypercorn.asyncio import serve
        from hypercorn.config import Config
    except ImportError:
        logger.error("hypercorn is not installed. Please install it:")
        logger.error("  pip install hypercorn")
        sys.exit(1)
    
    config = Config()
    config.bind = [f"{host}:{port}"]
    config.loglevel = log_level.upper()
    config.accesslog = "-"
    config.errorlog = "-"
    config.use_reloader = False
    
    logger.info(f"Starting server with Hypercorn (HTTP/2 support) on {host}:{port}")
    asyncio.run(serve(app, config))


# 启动入口：支持 `python -m api.app` 直接启动
if __name__ == "__main__":
    _start_server()
