# Universal Agent MVP Dockerfile

# 使用Python 3.11 slim镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY pyproject.toml .
COPY llm/ ./llm/
COPY tools/ ./tools/
COPY api/ ./api/
COPY core/ ./core/
COPY config/ ./config/
COPY orchestration/ ./orchestration/
COPY scripts/ ./scripts/

# 复制其他必要文件
COPY README.md .

# 安装Python依赖
RUN pip install --no-cache-dir -e .

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 启动命令
CMD ["python", "-m", "scripts.start"]
