#!/bin/bash
# Zero Agent 压力测试脚本
# 用于测试 Gateway 和 Agent 的性能和并发处理能力

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
CONCURRENT="${CONCURRENT:-10}"        # 并发数
TOTAL_REQUESTS="${TOTAL_REQUESTS:-100}"  # 总请求数
TEST_TYPE="${TEST_TYPE:-chat}"        # 测试类型: chat, health, session
SESSION_ID="${SESSION_ID:-stress-test-$(date +%s)}"

# 统计变量
SUCCESS_COUNT=0
FAIL_COUNT=0
TOTAL_TIME=0
MIN_TIME=999999
MAX_TIME=0
TIMEOUT_COUNT=0
ERROR_COUNT=0

# 临时文件
RESULT_FILE=$(mktemp)
TIMING_FILE=$(mktemp)

# 清理函数
cleanup() {
    rm -f "$RESULT_FILE" "$TIMING_FILE"
}
trap cleanup EXIT

# 打印帮助信息
print_help() {
    cat << EOF
Zero Agent 压力测试脚本

用法:
    $0 [选项]

选项:
    -u, --url URL            Gateway URL (默认: http://localhost:8080)
    -c, --concurrent NUM    并发数 (默认: 10)
    -n, --requests NUM      总请求数 (默认: 100)
    -t, --type TYPE         测试类型: chat, health, session (默认: chat)
    -s, --session-id ID     会话ID (默认: 自动生成)
    -h, --help              显示帮助信息

环境变量:
    GATEWAY_URL              Gateway 地址
    CONCURRENT               并发数
    TOTAL_REQUESTS           总请求数
    TEST_TYPE                测试类型

示例:
    # 基本压力测试
    $0 -c 20 -n 200

    # 测试健康检查接口
    $0 -t health -c 50 -n 500

    # 使用自定义 Gateway URL
    $0 -u http://192.168.1.100:8080 -c 10 -n 100

    # 使用环境变量
    export CONCURRENT=30
    export TOTAL_REQUESTS=300
    $0
EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -u|--url)
                GATEWAY_URL="$2"
                shift 2
                ;;
            -c|--concurrent)
                CONCURRENT="$2"
                shift 2
                ;;
            -n|--requests)
                TOTAL_REQUESTS="$2"
                shift 2
                ;;
            -t|--type)
                TEST_TYPE="$2"
                shift 2
                ;;
            -s|--session-id)
                SESSION_ID="$2"
                shift 2
                ;;
            -h|--help)
                print_help
                exit 0
                ;;
            *)
                echo -e "${RED}未知参数: $1${NC}"
                print_help
                exit 1
                ;;
        esac
    done
}

# 检查依赖
check_dependencies() {
    local missing=0
    
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}错误: 未找到 curl 命令${NC}"
        missing=1
    fi
    
    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}警告: 未找到 jq 命令，JSON 解析功能将受限${NC}"
    fi
    
    if [ $missing -eq 1 ]; then
        exit 1
    fi
}

# 测试健康检查接口
test_health() {
    local start_time=$(date +%s.%N)
    local response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
        -X GET \
        "$GATEWAY_URL/health" \
        -H "Content-Type: application/json" 2>&1)
    local end_time=$(date +%s.%N)
    local duration=$(echo "$end_time - $start_time" | bc)
    
    local http_code=$(echo "$response" | tail -n 1)
    local curl_time=$(echo "$response" | tail -n 2 | head -n 1)
    
    echo "$duration|$http_code|$curl_time"
}

# 测试会话创建
test_session() {
    local start_time=$(date +%s.%N)
    local response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
        -X POST \
        "$GATEWAY_URL/api/v1/sessions" \
        -H "Content-Type: application/json" \
        -d '{"metadata": {}}' 2>&1)
    local end_time=$(date +%s.%N)
    local duration=$(echo "$end_time - $start_time" | bc)
    
    local http_code=$(echo "$response" | tail -n 1)
    local curl_time=$(echo "$response" | tail -n 2 | head -n 1)
    
    echo "$duration|$http_code|$curl_time"
}

# 测试聊天接口
test_chat() {
    local session_id="${1:-$SESSION_ID}"
    local message="${2:-压力测试消息 $(date +%s.%N)}"
    local start_time=$(date +%s.%N)
    
    local response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
        -X POST \
        "$GATEWAY_URL/api/v1/chat" \
        -H "Content-Type: application/json" \
        -d "{
            \"session_id\": \"$session_id\",
            \"message\": \"$message\",
            \"stream\": false
        }" \
        --max-time 30 2>&1)
    
    local end_time=$(date +%s.%N)
    local duration=$(echo "$end_time - $start_time" | bc)
    
    local http_code=$(echo "$response" | tail -n 1)
    local curl_time=$(echo "$response" | tail -n 2 | head -n 1)
    
    echo "$duration|$http_code|$curl_time"
}

# 注意: run_single_test 函数已移除，逻辑已内联到 xargs 中

# 处理测试结果
process_results() {
    local success=0
    local fail=0
    local total_time=0
    local min_time=999999
    local max_time=0
    local timeout=0
    local error=0
    local times=()
    
    while IFS='|' read -r duration http_code curl_time; do
        if [ -z "$duration" ] || [ -z "$http_code" ]; then
            continue
        fi
        
        # 转换为数字（处理可能的错误）
        duration_num=$(echo "$duration" | bc 2>/dev/null || echo "0")
        http_code_num=$(echo "$http_code" | grep -oE '[0-9]+' | head -1 || echo "0")
        
        if [ "$http_code_num" = "200" ] || [ "$http_code_num" = "201" ]; then
            success=$((success + 1))
            total_time=$(echo "$total_time + $duration_num" | bc)
            times+=("$duration_num")
            
            # 更新最小最大时间
            if (( $(echo "$duration_num < $min_time" | bc -l) )); then
                min_time=$duration_num
            fi
            if (( $(echo "$duration_num > $max_time" | bc -l) )); then
                max_time=$duration_num
            fi
        elif [ "$http_code_num" = "0" ] || [ -z "$http_code_num" ]; then
            timeout=$((timeout + 1))
        else
            fail=$((fail + 1))
            if [ "$http_code_num" -ge 500 ]; then
                error=$((error + 1))
            fi
        fi
    done < "$RESULT_FILE"
    
    SUCCESS_COUNT=$success
    FAIL_COUNT=$fail
    TIMEOUT_COUNT=$timeout
    ERROR_COUNT=$error
    
    if [ $success -gt 0 ]; then
        TOTAL_TIME=$total_time
        MIN_TIME=$min_time
        MAX_TIME=$max_time
    fi
}

# 计算百分位数
calculate_percentile() {
    local percentile=$1
    local sorted_times=($(printf '%s\n' "${times[@]}" | sort -n))
    local count=${#sorted_times[@]}
    
    if [ $count -eq 0 ]; then
        echo "0"
        return
    fi
    
    local index=$(echo "scale=0; $count * $percentile / 100" | bc)
    if [ $index -ge $count ]; then
        index=$((count - 1))
    fi
    
    echo "${sorted_times[$index]:-0}"
}

# 打印测试结果
print_results() {
    local test_duration=$1
    local total=$((SUCCESS_COUNT + FAIL_COUNT + TIMEOUT_COUNT))
    local success_rate=0
    local avg_time=0
    local qps=0
    
    if [ $total -gt 0 ]; then
        success_rate=$(echo "scale=2; $SUCCESS_COUNT * 100 / $total" | bc)
    fi
    
    # 计算平均响应时间
    if [ "$TOTAL_TIME" != "0" ] && [ $SUCCESS_COUNT -gt 0 ]; then
        avg_time=$(echo "scale=3; $TOTAL_TIME / $SUCCESS_COUNT" | bc)
    else
        avg_time=0
    fi
    
    # 计算 QPS（使用测试总耗时）
    if [ $SUCCESS_COUNT -gt 0 ] && [ "$test_duration" -gt 0 ]; then
        qps=$(echo "scale=2; $SUCCESS_COUNT / $test_duration" | bc)
    else
        qps=0
    fi
    
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}        压力测试结果报告${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "${GREEN}测试配置:${NC}"
    echo "  Gateway URL:     $GATEWAY_URL"
    echo "  测试类型:       $TEST_TYPE"
    echo "  并发数:         $CONCURRENT"
    echo "  总请求数:       $TOTAL_REQUESTS"
    echo "  会话ID:         $SESSION_ID"
    echo ""
    echo -e "${GREEN}测试结果:${NC}"
    echo -e "  总请求数:       ${BLUE}$total${NC}"
    echo -e "  成功:           ${GREEN}$SUCCESS_COUNT${NC}"
    echo -e "  失败:           ${RED}$FAIL_COUNT${NC}"
    echo -e "  超时:           ${YELLOW}$TIMEOUT_COUNT${NC}"
    echo -e "  服务器错误:     ${RED}$ERROR_COUNT${NC}"
    echo -e "  成功率:         ${GREEN}${success_rate}%${NC}"
    echo ""
    
    if [ $SUCCESS_COUNT -gt 0 ]; then
        # 计算平均响应时间
        if [ "$TOTAL_TIME" != "0" ] && [ $SUCCESS_COUNT -gt 0 ]; then
            avg_time=$(echo "scale=3; $TOTAL_TIME / $SUCCESS_COUNT" | bc)
        else
            avg_time=0
        fi
        
        echo -e "${GREEN}性能指标:${NC}"
        echo -e "  平均响应时间:   ${BLUE}${avg_time}s${NC}"
        echo -e "  最小响应时间:   ${BLUE}${MIN_TIME}s${NC}"
        echo -e "  最大响应时间:   ${BLUE}${MAX_TIME}s${NC}"
        echo -e "  QPS (每秒请求): ${BLUE}${qps}${NC}"
        echo ""
    fi
    
    echo -e "${BLUE}========================================${NC}"
}

# 执行压力测试
run_stress_test() {
    local test_num=$1
    local test_type=$2
    local gateway_url=$3
    local session_id=$4
    
    local result=""
    local start_time=$(date +%s.%N)
    
    case $test_type in
        health)
            local response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
                -X GET \
                "$gateway_url/health" \
                -H "Content-Type: application/json" 2>&1)
            ;;
        session)
            local response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
                -X POST \
                "$gateway_url/api/v1/sessions" \
                -H "Content-Type: application/json" \
                -d '{"metadata": {}}' 2>&1)
            ;;
        chat)
            local message="测试消息 $test_num"
            local response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
                -X POST \
                "$gateway_url/api/v1/chat" \
                -H "Content-Type: application/json" \
                -d "{
                    \"session_id\": \"$session_id\",
                    \"message\": \"$message\",
                    \"stream\": false
                }" \
                --max-time 30 2>&1)
            ;;
    esac
    
    local end_time=$(date +%s.%N)
    local duration=$(echo "$end_time - $start_time" | bc)
    local http_code=$(echo "$response" | tail -n 1)
    local curl_time=$(echo "$response" | tail -n 2 | head -n 1)
    
    echo "$duration|$http_code|$curl_time"
}

# 主函数
main() {
    parse_args "$@"
    
    echo -e "${BLUE}Zero Agent 压力测试${NC}"
    echo "Gateway URL: $GATEWAY_URL"
    echo "测试类型: $TEST_TYPE"
    echo "并发数: $CONCURRENT"
    echo "总请求数: $TOTAL_REQUESTS"
    echo ""
    
    check_dependencies
    
    # 检查 Gateway 是否可用
    echo -e "${YELLOW}检查 Gateway 连接...${NC}"
    if ! curl -s --max-time 5 "$GATEWAY_URL/health" > /dev/null; then
        echo -e "${RED}错误: 无法连接到 Gateway ($GATEWAY_URL)${NC}"
        exit 1
    fi
    echo -e "${GREEN}Gateway 连接正常${NC}"
    echo ""
    
    # 执行压力测试
    echo -e "${YELLOW}开始压力测试...${NC}"
    local start_time=$(date +%s)
    
    # 使用 xargs 进行并发控制，将函数逻辑内联
    seq 1 $TOTAL_REQUESTS | xargs -P $CONCURRENT -I {} bash -c "
        test_num={}
        test_type='$TEST_TYPE'
        gateway_url='$GATEWAY_URL'
        session_id='$SESSION_ID'
        
        start_time=\$(date +%s.%N)
        
        case \$test_type in
            health)
                response=\$(curl -s -w \"\\n%{http_code}\\n%{time_total}\" \
                    -X GET \
                    \"\$gateway_url/health\" \
                    -H \"Content-Type: application/json\" 2>&1)
                ;;
            session)
                response=\$(curl -s -w \"\\n%{http_code}\\n%{time_total}\" \
                    -X POST \
                    \"\$gateway_url/api/v1/sessions\" \
                    -H \"Content-Type: application/json\" \
                    -d '{\"metadata\": {}}' 2>&1)
                ;;
            chat)
                message=\"测试消息 \$test_num\"
                response=\$(curl -s -w \"\\n%{http_code}\\n%{time_total}\" \
                    -X POST \
                    \"\$gateway_url/api/v1/chat\" \
                    -H \"Content-Type: application/json\" \
                    -d \"{\\\"session_id\\\": \\\"\$session_id\\\", \\\"message\\\": \\\"\$message\\\", \\\"stream\\\": false}\" \
                    --max-time 30 2>&1)
                ;;
        esac
        
        end_time=\$(date +%s.%N)
        duration=\$(echo \"\$end_time - \$start_time\" | bc 2>/dev/null || echo \"0\")
        # curl 输出格式: 响应体\n\nHTTP状态码\ntime_total
        # 所以 HTTP 状态码是倒数第二行，time_total 是最后一行
        http_code=\$(echo \"\$response\" | tail -n 2 | head -n 1 | grep -oE '^[0-9]{3}$' | head -1 || echo \"0\")
        curl_time=\$(echo \"\$response\" | tail -n 1 | grep -oE '^[0-9.]+$' | head -1 || echo \"0\")
        
        echo \"\$duration|\$http_code|\$curl_time\" >> '$RESULT_FILE'
        if [ \"\$http_code\" = \"200\" ] || [ \"\$http_code\" = \"201\" ]; then
            echo \"请求 \$test_num: 成功 (\$http_code) - \${duration}s\"
        else
            echo \"请求 \$test_num: 失败 (\$http_code) - \${duration}s\"
        fi
    "
    
    local end_time=$(date +%s)
    local test_duration=$((end_time - start_time))
    
    echo ""
    echo -e "${GREEN}测试完成，耗时: ${test_duration}秒${NC}"
    echo -e "${YELLOW}正在分析结果...${NC}"
    
    # 处理结果
    process_results
    
    # 打印结果
    print_results $test_duration
}

# 运行主函数
main "$@"
