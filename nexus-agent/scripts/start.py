#!/usr/bin/env python3
"""
Universal Agent MVP 启动脚本
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
    logger.info("Starting Universal Agent MVP...")

    # 检查环境
    if not check_environment():
        sys.exit(1)

    # 显示当前使用的LLM信息
    llm_provider, llm_model = get_current_llm_info()
    logger.info(f"Current LLM: {llm_provider} {llm_model}") 

    # 获取服务器配置
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8080"))
    log_level = os.getenv("LOG_LEVEL", "INFO")

    # 设置日志级别
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)

    logger.info(f"Starting server on {host}:{port}")

    try:
        # 启动FastAPI服务器
        import uvicorn
        from api import app

        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=log_level.lower(),
            access_log=True,
            server_header=False,
            date_header=False
        )

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
