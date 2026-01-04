#!/bin/bash
# Nexus Agent 流式聊天测试脚本
# 测试流式请求、会话管理以及context canceled错误

# 移除 set -e，改为手动处理错误
# set -e

# 配置
GATEWAY_URL="http://localhost:8080"
AI_URL="http://localhost:8082"
TIMEOUT=30
MAX_RETRIES=3
RETRY_DELAY=2

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查服务是否运行
check_services() {
    log_info "检查服务状态..."

    # 检查API网关
    if ! curl -f -s "$GATEWAY_URL/health" > /dev/null 2>&1; then
        log_error "API网关未运行，请先执行 ./start.sh 启动服务"
        exit 1
    fi

    # 检查AI服务
    log_info "检查AI服务状态..."
    local retry_count=0
    while [ $retry_count -lt $MAX_RETRIES ]; do
        if curl -f -s --max-time 10 "$AI_URL/health" > /dev/null 2>&1; then
            log_success "AI服务运行正常"
            break
        else
            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $MAX_RETRIES ]; then
                log_warning "AI服务未就绪，重试中... ($retry_count/$MAX_RETRIES)"
                sleep $RETRY_DELAY
            else
                log_error "AI服务启动失败，请检查服务状态"
                log_info "您可以尝试重新运行 ./start.sh 或等待更长时间"
                exit 1
            fi
        fi
    done

    log_success "所有服务运行正常"
}

# 创建新会话
create_session() {
    echo "创建新会话..." >&2

    local response=$(curl -s -X POST "$GATEWAY_URL/api/v1/sessions" \
        -H "Content-Type: application/json" \
        -d '{"metadata": {"test": true}}' \
        --max-time $TIMEOUT 2>/dev/null)

    local session_id=$(echo "$response" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$session_id" ]; then
        echo "创建会话失败: $response" >&2
        return 1
    fi

    echo "会话创建成功: $session_id" >&2
    echo "$session_id"
}

# 测试普通聊天请求
test_normal_chat() {
    local session_id=$1
    log_info "测试普通聊天请求 (session: $session_id)..."

    local retry_count=0
    while [ $retry_count -lt $MAX_RETRIES ]; do
        local response=$(curl -s -X POST "$GATEWAY_URL/api/v1/chat" \
            -H "Content-Type: application/json" \
            -d "{\"session_id\": \"$session_id\", \"message\": \"你好，请简单介绍一下自己\"}" \
            --max-time $TIMEOUT 2>/dev/null)

        if echo "$response" | grep -q "message"; then
            log_success "普通聊天请求成功"
            return 0
        else
            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $MAX_RETRIES ]; then
                log_warning "聊天请求失败，重试中... ($retry_count/$MAX_RETRIES)"
                sleep $RETRY_DELAY
            else
                log_error "普通聊天请求失败: $response"
                return 1
            fi
        fi
    done
}

# 测试流式聊天请求
test_streaming_chat() {
    local session_id=$1
    log_info "测试流式聊天请求 (session: $session_id)..."

    log_info "发送流式请求..."
    local start_time=$(date +%s)

    # 使用timeout命令测试流式请求
    if timeout 10s curl -s -X POST "$GATEWAY_URL/api/v1/chat/stream" \
        -H "Content-Type: application/json" \
        -d "{\"session_id\": \"$session_id\", \"message\": \"请给我讲一个简短的故事\"}" \
        --max-time $TIMEOUT > /dev/null 2>&1; then

        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_success "流式请求完成 (耗时: ${duration}s)"
        return 0
    else
        log_error "流式请求失败"
        return 1
    fi
}

# 测试提前断开连接的流式请求 (模拟context canceled)
test_streaming_disconnect() {
    local session_id=$1
    log_info "测试流式请求提前断开连接 (session: $session_id)..."

    log_info "启动流式请求并在2秒后断开..."

    # 在后台启动curl请求
    curl -s -X POST "$GATEWAY_URL/api/v1/chat/stream" \
        -H "Content-Type: application/json" \
        -d "{\"session_id\": \"$session_id\", \"message\": \"这是一个很长的请求，请慢慢回复\"}" \
        --max-time $TIMEOUT > /dev/null 2>&1 &

    local curl_pid=$!

    # 等待2秒后杀掉进程，模拟客户端断开
    sleep 2
    kill $curl_pid 2>/dev/null || true

    log_success "模拟客户端断开完成"
    log_info "检查网关日志，应该会看到 'context canceled' 相关的日志"
    return 0  # 这个测试总是"成功"，因为我们只是模拟断开
}

# 测试会话历史
test_session_history() {
    local session_id=$1
    log_info "测试会话历史 (session: $session_id)..."

    local response=$(curl -s "$GATEWAY_URL/api/v1/sessions/$session_id/history" \
        --max-time $TIMEOUT 2>/dev/null)

    if echo "$response" | grep -q "role"; then
        local message_count=$(echo "$response" | grep -o '"role"' | wc -l)
        log_success "会话历史获取成功，共 $message_count 条消息"
        return 0
    else
        log_error "会话历史获取失败: $response"
        return 1
    fi
}

# 测试工具列表
test_tools_list() {
    log_info "测试工具列表..."

    local response=$(curl -s "$GATEWAY_URL/api/v1/tools" \
        --max-time $TIMEOUT 2>/dev/null)

    if echo "$response" | grep -q "name"; then
        log_success "工具列表获取成功"
        return 0
    else
        log_warning "工具列表获取失败或为空: $response"
        return 1
    fi
}

# 测试无效请求
test_invalid_request() {
    log_info "测试无效请求..."

    # 缺少必需字段
    local response=$(curl -s -X POST "$GATEWAY_URL/api/v1/chat/stream" \
        -H "Content-Type: application/json" \
        -d '{"message": "test"}' \
        --max-time $TIMEOUT 2>/dev/null)

    if echo "$response" | grep -q "error"; then
        log_success "无效请求正确返回错误"
        return 0
    else
        log_warning "无效请求未返回预期错误: $response"
        return 1
    fi
}

# 主测试流程
main() {
    echo "======================================"
    echo "   Nexus Agent 流式聊天测试脚本"
    echo "======================================"
    echo

    # 检查服务
    check_services
    echo

    # 创建会话
    SESSION_ID=$(create_session)
    if [ -z "$SESSION_ID" ]; then
        log_error "无法创建会话，退出测试"
        exit 1
    fi
    echo

    # 运行各项测试
    echo "开始测试..."
    echo

    # 跟踪测试结果
    local test_results=()

    if test_normal_chat "$SESSION_ID"; then
        test_results+=("✓ 普通聊天请求")
    else
        test_results+=("✗ 普通聊天请求")
    fi
    echo

    if test_streaming_chat "$SESSION_ID"; then
        test_results+=("✓ 流式聊天请求")
    else
        test_results+=("✗ 流式聊天请求")
    fi
    echo

    if test_streaming_disconnect "$SESSION_ID"; then
        test_results+=("✓ 流式请求断开连接 (检查context canceled日志)")
    else
        test_results+=("? 流式请求断开连接 (可能正常)")
    fi
    echo

    if test_session_history "$SESSION_ID"; then
        test_results+=("✓ 会话历史查询")
    else
        test_results+=("✗ 会话历史查询")
    fi
    echo

    if test_tools_list; then
        test_results+=("✓ 工具列表查询")
    else
        test_results+=("? 工具列表查询")
    fi
    echo

    if test_invalid_request; then
        test_results+=("✓ 错误处理")
    else
        test_results+=("✗ 错误处理")
    fi
    echo

    log_success "所有测试完成！"
    echo
    log_info "测试总结:"
    for result in "${test_results[@]}"; do
        log_info "$result"
    done

    # 检查是否有关键测试失败
    local critical_failures=0
    for result in "${test_results[@]}"; do
        if [[ $result == ✗* ]]; then
            critical_failures=$((critical_failures + 1))
        fi
    done

    if [ $critical_failures -gt 0 ]; then
        log_warning "发现 $critical_failures 个关键测试失败，请检查服务状态"
        exit 1
    else
        log_success "所有关键测试通过！"
    fi
}

# 如果脚本被直接调用，运行主函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi