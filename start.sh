#!/bin/bash
# Nexus Agent 系统启动脚本
# 同时启动 Go API网关 和 Python AI核心服务

set -e

echo "启动 Nexus Agent 系统..."

# 加载环境变量配置
if [ -f "zero-agent/.env" ]; then
    echo "加载环境配置..."
    # 移除BOM并正确解析环境变量
    while IFS='=' read -r key value; do
        # 跳过注释行和空行
        [[ $key =~ ^[[:space:]]*# ]] && continue
        [[ -z $key ]] && continue
        export "$key=$value"
    done < <(tail -c +4 zero-agent/.env 2>/dev/null || cat zero-agent/.env)
else
    echo "警告: 未找到 zero-agent/.env 文件"
fi

# 检查环境变量
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$SILICONFLOW_API_KEY" ]; then
    echo "错误: 请设置至少一个LLM API密钥"
    echo "   请在 zero-agent/.env 文件中配置:"
    echo "   OPENAI_API_KEY 或 ANTHROPIC_API_KEY 或 SILICONFLOW_API_KEY"
    echo ""
    echo "   当前配置状态:"
    echo "   OPENAI_API_KEY: ${OPENAI_API_KEY:-未设置}"
    echo "   ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-未设置}"
    echo "   SILICONFLOW_API_KEY: ${SILICONFLOW_API_KEY:-未设置}"
    exit 1
fi

# 设置默认值（如果.env中未设置）
export LLM_PROVIDER=${LLM_PROVIDER:-"siliconflow"}
export LLM_MODEL=${LLM_MODEL:-"Pro/Qwen/Qwen2.5-7B-Instruct"}
export PYTHON_AGENT_HOST=${PYTHON_AGENT_HOST:-"localhost"}
export PYTHON_AGENT_PORT=${PYTHON_AGENT_PORT:-8082}
export LOG_LEVEL=${LOG_LEVEL:-"info"}

# 将日志级别转换为小写（Go要求小写）
export LOG_LEVEL=$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')

echo "配置信息:"
echo "   LLM提供商: $LLM_PROVIDER"
echo "   LLM模型: $LLM_MODEL"
echo "   Python AI服务: $PYTHON_AGENT_HOST:$PYTHON_AGENT_PORT"
echo "   日志级别: $LOG_LEVEL"
echo "   API密钥状态: 已配置"

# 启动Python AI核心服务（后台）
echo "启动 Python AI 核心服务..."
cd zero-agent
source ../venv/bin/activate
# 强制设置AI服务端口为8082，避免与.env文件中的配置冲突
export API_PORT=8082
python -m scripts.start &
AI_SERVICE_PID=$!
cd ..

# 等待AI服务启动
echo "等待 AI 服务启动..."
sleep 5

# 检查AI服务是否启动成功
if ! curl -f http://localhost:8082/health >/dev/null 2>&1; then
    echo "AI 服务启动失败"
    kill $AI_SERVICE_PID 2>/dev/null
    exit 1
fi

echo "AI 服务启动成功 (PID: $AI_SERVICE_PID)"

# 启动Go API网关（后台）
echo "启动 Go API 网关..."
cd zero-gateway
go run cmd/api-gateway/main.go &
GATEWAY_PID=$!

# 等待网关启动
echo "等待 API 网关启动..."
sleep 3

# 检查网关是否启动成功
if ! curl -f http://localhost:8080/health >/dev/null 2>&1; then
    echo "API 网关启动失败"
    kill $AI_SERVICE_PID $GATEWAY_PID 2>/dev/null
    exit 1
fi

echo "API 网关启动成功 (PID: $GATEWAY_PID)"
echo ""
echo "Nexus Agent 系统启动完成！"
echo ""
echo "服务地址:"
echo "   API网关: http://localhost:8080"
echo "   AI服务:  http://localhost:8082"
echo "   健康检查: http://localhost:8080/health"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
trap 'echo ""; echo "正在停止服务..."; kill $AI_SERVICE_PID $GATEWAY_PID 2>/dev/null; echo "所有服务已停止"; exit 0' INT

# 保持脚本运行，监控子进程
while true; do
    if ! kill -0 $AI_SERVICE_PID 2>/dev/null; then
        echo "AI 服务异常退出"
        kill $GATEWAY_PID 2>/dev/null
        exit 1
    fi

    if ! kill -0 $GATEWAY_PID 2>/dev/null; then
        echo "API 网关异常退出"
        kill $AI_SERVICE_PID 2>/dev/null
        exit 1
    fi

    sleep 5
done
