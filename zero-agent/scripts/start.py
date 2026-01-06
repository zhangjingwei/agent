#!/usr/bin/env python3
"""
Nexus Agent Core - AI服务启动脚本

此脚本启动Python AI核心服务，提供LangGraph工作流和MCP工具编排。
服务运行在8082端口，通过HTTP/2与Go API网关通信。
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

# 设置Python路径
os.environ['PYTHONPATH'] = str(project_root)

# 配置基础日志（在structlog初始化之前）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def check_environment():
    """检查环境配置"""
    required_vars = []
    optional_vars = ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'SILICONFLOW_API_KEY', 'WEATHER_API_KEY']

    # 检查是否至少有一个LLM API密钥
    has_llm_key = any(os.getenv(var) for var in optional_vars[:3])
    if not has_llm_key:
        logger.error("No LLM API key found. Please set OPENAI_API_KEY, ANTHROPIC_API_KEY, or SILICONFLOW_API_KEY")
        return False

    logger.info("Environment check passed")
    return True

def get_current_llm_info():
    """获取当前使用的LLM信息"""
    llm_provider = os.getenv("LLM_PROVIDER")
    llm_model = os.getenv("LLM_MODEL")
    
    if not llm_provider or not llm_model:
        return None, None
    
    return llm_provider, llm_model


def main():
    """主启动函数"""
    logger.info("Starting Nexus Agent Core (AI Service)...")

    # 检查环境
    if not check_environment():
        sys.exit(1)

    # 显示当前使用的LLM信息
    llm_provider, llm_model = get_current_llm_info()
    logger.info(f"Current LLM: {llm_provider} {llm_model}") 

    # 获取服务器配置
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8082"))  # AI核心服务端口
    log_level = os.getenv("LOG_LEVEL", "INFO")

    # 设置日志级别
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)

    logger.info(f"Starting Nexus Agent Core (AI service) on {host}:{port}")
    logger.info("This service provides AI inference and MCP tool orchestration via HTTP/2")

    try:
        # 启动FastAPI服务器，使用hypercorn支持HTTP/2
        import asyncio
        from hypercorn.asyncio import serve
        from hypercorn.config import Config
        from api import app

        # 配置hypercorn支持HTTP/2 (h2c - HTTP/2 over cleartext)
        config = Config()
        config.bind = [f"{host}:{port}"]
        config.loglevel = log_level.upper()
        config.accesslog = "-"  # 输出到stdout
        config.errorlog = "-"   # 输出到stderr
        config.use_reloader = False
        
        # hypercorn默认支持HTTP/2，会自动协商
        # 如果客户端支持HTTP/2（如Go的http2.Transport），将使用HTTP/2
        # 否则降级到HTTP/1.1
        logger.info("Hypercorn configured with HTTP/2 support (h2c)")

        # 运行hypercorn服务器
        asyncio.run(serve(app, config))

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
