#!/bin/bash
# Zero Agent 流式聊天测试脚本
# 测试流式请求、会话管理以及context canceled处理

# 移除 set -e，因为需要手动处理错误
# set -e

# 配置
GATEWAY_URL="http://localhost:8080"
AI_URL="http://localhost:8082"
TIMEOUT=30
MAX_RETRIES=3
RETRY_DELAY=2

# 颜色定义
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

# 检查工具是否可用
check_tools() {
    if ! command -v curl &> /dev/null; then
        log_error "curl 未安装，请先安装 curl"
        exit 1
    fi

    # 检查 jq 是否可用（可选，用于更好的 JSON 解析）
    if command -v jq &> /dev/null; then
        USE_JQ=true
    else
        USE_JQ=false
        log_warning "jq 未安装，将使用 grep 解析 JSON（建议安装 jq 以获得更好的解析）"
    fi
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
                log_error "AI服务检查失败，请检查服务状态"
                log_info "请确保服务已启动，执行 ./start.sh 并等待服务就绪"
                exit 1
            fi
        fi
    done

    log_success "所有服务运行正常"
}

# 创建新会话
create_session() {
    echo "创建新会话..." >&2

    local http_code=$(curl -s -o /tmp/session_response.json -w "%{http_code}" -X POST "$GATEWAY_URL/api/v1/sessions" \
        -H "Content-Type: application/json" \
        -d '{"metadata": {"test": true}}' \
        --max-time $TIMEOUT 2>/dev/null)

    # 检查HTTP状态码
    if [ "$http_code" != "201" ] && [ "$http_code" != "200" ]; then
        local response=$(cat /tmp/session_response.json 2>/dev/null)
        echo "创建会话失败: HTTP $http_code - $response" >&2
        rm -f /tmp/session_response.json
        return 1
    fi

    local response=$(cat /tmp/session_response.json 2>/dev/null)
    rm -f /tmp/session_response.json

    # 检查响应是否为空
    if [ -z "$response" ]; then
        echo "创建会话失败: 响应为空" >&2
        return 1
    fi

    # 处理可能的重复响应：只取第一个完整的JSON对象
    # 如果响应包含多个JSON对象（没有换行符分隔），提取第一个
    local session_id=""
    if [ "$USE_JQ" = true ]; then
        # 使用jq提取第一个有效的JSON对象
        # 如果响应包含多个JSON，jq会报错，所以先尝试提取第一个
        local first_json=$(echo "$response" | sed 's/}{/}\n{/' | head -n 1)
        if [ -z "$first_json" ]; then
            first_json="$response"
        fi
        session_id=$(echo "$first_json" | jq -r '.session_id' 2>/dev/null | tr -d '\n\r' | head -n 1)
    else
        # 使用grep提取第一个session_id（更简单可靠）
        # 直接提取第一个匹配的session_id，因为即使有重复，session_id也是相同的
        session_id=$(echo "$response" | grep -o '"session_id":"[^"]*"' | head -n 1 | cut -d'"' -f4 | tr -d '\n\r' | head -n 1)
    fi

    # 验证 session_id 格式（UUID格式）
    if [ -z "$session_id" ] || ! echo "$session_id" | grep -qE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
        echo "创建会话失败: 无法解析session_id" >&2
        echo "响应内容: $response" >&2
        return 1
    fi

    echo "会话创建成功: $session_id" >&2
    echo "$session_id"
}

# 测试普通聊天请求
test_normal_chat() {
    local session_id=$1

    # 验证 session_id
    if [ -z "$session_id" ]; then
        log_error "会话ID为空"
        return 1
    fi

    log_info "测试普通聊天请求 (session: $session_id)..."

    local retry_count=0
    while [ $retry_count -lt $MAX_RETRIES ]; do
        local http_code=$(curl -s -o /tmp/chat_response.json -w "%{http_code}" -X POST "$GATEWAY_URL/api/v1/chat" \
            -H "Content-Type: application/json" \
            -d "{\"session_id\": \"$session_id\", \"message\": \"你好，请简单介绍一下你自己\"}" \
            --max-time $TIMEOUT 2>/dev/null)

        if [ "$http_code" = "200" ]; then
            local response=$(cat /tmp/chat_response.json 2>/dev/null)
            if [ "$USE_JQ" = true ]; then
                if echo "$response" | jq -e '.message' > /dev/null 2>&1; then
                    log_success "普通聊天请求成功"
                    rm -f /tmp/chat_response.json
                    return 0
                fi
            else
                if echo "$response" | grep -q '"message"'; then
                    log_success "普通聊天请求成功"
                    rm -f /tmp/chat_response.json
                    return 0
                fi
            fi
        fi

        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $MAX_RETRIES ]; then
            log_warning "聊天请求失败，重试中... ($retry_count/$MAX_RETRIES)"
            sleep $RETRY_DELAY
        else
            local response=$(cat /tmp/chat_response.json 2>/dev/null)
            log_error "普通聊天请求失败: $response"
            rm -f /tmp/chat_response.json
            return 1
        fi
    done
}

# 测试流式聊天请求
test_streaming_chat() {
    local session_id=$1

    # 验证 session_id
    if [ -z "$session_id" ]; then
        log_error "会话ID为空"
        return 1
    fi

    log_info "测试流式聊天请求 (session: $session_id)..."

    log_info "发送流式请求..."
    local start_time=$(date +%s)

    # 使用timeout命令测试流式请求
    if timeout 10s curl -s -X POST "$GATEWAY_URL/api/v1/chat/stream" \
        -H "Content-Type: application/json" \
        -d "{\"session_id\": \"$session_id\", \"message\": \"请给我讲一个短的故事\"}" \
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

    # 验证 session_id
    if [ -z "$session_id" ]; then
        log_error "会话ID为空"
        return 1
    fi

    log_info "测试流式请求提前断开连接 (session: $session_id)..."

    log_info "启动流式请求并在2秒后断开..."

    # 在后台启动curl请求
    curl -s -X POST "$GATEWAY_URL/api/v1/chat/stream" \
        -H "Content-Type: application/json" \
        -d "{\"session_id\": \"$session_id\", \"message\": \"请给我一个很长的回答，需要重复很多次\"}" \
        --max-time $TIMEOUT > /dev/null 2>&1 &

    local curl_pid=$!

    # 等待2秒后杀死进程，模拟客户端断开
    sleep 2
    kill $curl_pid 2>/dev/null || true

    log_success "模拟客户端断开完成"
    log_info "检查网关日志，应该会看到 'context canceled' 相关的日志"
    return 0  # 这个测试总是"成功"，因为它只是模拟断开
}

# 测试会话历史
test_session_history() {
    local session_id=$1

    # 验证 session_id
    if [ -z "$session_id" ]; then
        log_error "会话ID为空"
        return 1
    fi

    log_info "测试会话历史 (session: $session_id)..."

    local http_code=$(curl -s -o /tmp/history_response.json -w "%{http_code}" \
        "$GATEWAY_URL/api/v1/sessions/$session_id/history" \
        --max-time $TIMEOUT 2>/dev/null)

    if [ "$http_code" = "200" ]; then
        local response=$(cat /tmp/history_response.json 2>/dev/null)
        if [ "$USE_JQ" = true ]; then
            local message_count=$(echo "$response" | jq '. | length' 2>/dev/null || echo "0")
            if [ "$message_count" -gt 0 ]; then
                log_success "会话历史获取成功，共 $message_count 条消息"
                rm -f /tmp/history_response.json
                return 0
            fi
        else
            local message_count=$(echo "$response" | grep -o '"role"' | wc -l)
            if [ "$message_count" -gt 0 ]; then
                log_success "会话历史获取成功，共 $message_count 条消息"
                rm -f /tmp/history_response.json
                return 0
            fi
        fi
    fi

    local response=$(cat /tmp/history_response.json 2>/dev/null)
    log_error "会话历史获取失败: $response"
    rm -f /tmp/history_response.json
    return 1
}

# 测试工具列表
test_tools_list() {
    log_info "测试工具列表..."

    local http_code=$(curl -s -o /tmp/tools_response.json -w "%{http_code}" \
        "$GATEWAY_URL/api/v1/tools" \
        --max-time $TIMEOUT 2>/dev/null)

    if [ "$http_code" = "200" ]; then
        local response=$(cat /tmp/tools_response.json 2>/dev/null)
        
        # 处理可能的重复响应：只取第一个JSON对象
        local first_json=$(echo "$response" | sed 's/}{/}\n{/' | head -n 1)
        if [ -z "$first_json" ]; then
            first_json="$response"
        fi
        
        if [ "$USE_JQ" = true ]; then
            if echo "$first_json" | jq -e '. | length > 0' > /dev/null 2>&1; then
                log_success "工具列表获取成功"
                rm -f /tmp/tools_response.json
                return 0
            fi
        else
            if echo "$first_json" | grep -q '"name"'; then
                log_success "工具列表获取成功"
                rm -f /tmp/tools_response.json
                return 0
            fi
        fi
    fi

    local response=$(cat /tmp/tools_response.json 2>/dev/null)
    log_warning "工具列表获取失败或为空: $response"
    rm -f /tmp/tools_response.json
    return 1
}

# 测试无效请求
test_invalid_request() {
    log_info "测试无效请求..."

    # 缺少必需字段
    local http_code=$(curl -s -o /tmp/invalid_response.json -w "%{http_code}" -X POST "$GATEWAY_URL/api/v1/chat/stream" \
        -H "Content-Type: application/json" \
        -d '{"message": "test"}' \
        --max-time $TIMEOUT 2>/dev/null)

    if [ "$http_code" = "400" ] || [ "$http_code" = "404" ]; then
        local response=$(cat /tmp/invalid_response.json 2>/dev/null)
        
        # 处理可能的重复响应：只取第一个JSON对象
        local first_json=$(echo "$response" | sed 's/}{/}\n{/' | head -n 1)
        if [ -z "$first_json" ]; then
            first_json="$response"
        fi
        
        if [ "$USE_JQ" = true ]; then
            if echo "$first_json" | jq -e '.error' > /dev/null 2>&1; then
                log_success "无效请求正确返回错误"
                rm -f /tmp/invalid_response.json
                return 0
            fi
        else
            if echo "$first_json" | grep -q "error"; then
                log_success "无效请求正确返回错误"
                rm -f /tmp/invalid_response.json
                return 0
            fi
        fi
    fi

    local response=$(cat /tmp/invalid_response.json 2>/dev/null)
    log_warning "无效请求未返回预期错误: $response"
    rm -f /tmp/invalid_response.json
    return 1
}

# 主函数
main() {
    echo "======================================"
    echo "   Zero Agent 流式聊天测试脚本"
    echo "======================================"
    echo

    # 检查工具
    check_tools
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
    echo "$SESSION_ID"
    echo

    # 执行各项测试
    echo "开始测试..."
    echo

    # 记录测试结果
    local test_results=()

    # if test_normal_chat "$SESSION_ID"; then
    #     test_results+=("✓ 普通聊天请求")
    # else
    #     test_results+=("✗ 普通聊天请求")
    # fi
    # echo

    # if test_streaming_chat "$SESSION_ID"; then
    #     test_results+=("✓ 流式聊天请求")
    # else
    #     test_results+=("✗ 流式聊天请求")
    # fi
    # echo

    # if test_streaming_disconnect "$SESSION_ID"; then
    #     test_results+=("✓ 流式请求断开连接 (检查context canceled日志)")
    # else
    #     test_results+=("✗ 流式请求断开连接 (检查失败)")
    # fi
    # echo

    if test_session_history "$SESSION_ID"; then
        test_results+=("✓ 会话历史查询")
    else
        test_results+=("✗ 会话历史查询")
    fi
    echo

    # if test_tools_list; then
    #     test_results+=("✓ 工具列表查询")
    # else
    #     test_results+=("✗ 工具列表查询")
    # fi
    # echo

    # if test_invalid_request; then
    #     test_results+=("✓ 错误处理")
    # else
    #     test_results+=("✗ 错误处理")
    # fi
    # echo

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

# 如果脚本被直接调用，执行主函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi