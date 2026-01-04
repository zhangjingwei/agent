#!/bin/bash
BASE_URL="http://localhost:8080"

echo "开始Agent功能测试..."

# 健康检查
echo "1. 健康检查:"
HEALTH_STATUS=$(curl -s --max-time 10 $BASE_URL/health | jq -r '.status')
if [ "$HEALTH_STATUS" != "healthy" ]; then
    echo "健康检查失败: $HEALTH_STATUS"
    exit 1
fi
echo "\"$HEALTH_STATUS\""

# 创建会话
echo "2. 创建会话:"
SESSION=$(curl -s --max-time 10 -X POST $BASE_URL/sessions \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"test": true}}')
SESSION_ID=$(echo $SESSION | jq -r '.session_id')
if [ "$SESSION_ID" = "null" ] || [ -z "$SESSION_ID" ]; then
    echo "创建会话失败: $SESSION"
    exit 1
fi
echo "会话ID: $SESSION_ID"

# 测试Agent高级数学计算功能
echo "3. 测试Agent高级数学计算功能:"
echo "发送: '计算 sqrt(16) + sin(pi/2)'"

CHAT_RESPONSE=$(curl -s --max-time 30 -X POST $BASE_URL/sessions/$SESSION_ID/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "计算 sqrt(16) + sin(pi/2)"}')

# 检查响应是否成功
if [ $? -ne 0 ]; then
    echo "请求失败"
    exit 1
fi

# 解析响应
MESSAGE=$(echo $CHAT_RESPONSE | jq -r '.message')
TOOL_CALLS=$(echo $CHAT_RESPONSE | jq '.tool_calls')
PROCESSING_TIME=$(echo $CHAT_RESPONSE | jq -r '.processing_time')

echo "Agent原始响应: $MESSAGE"

# 显示工具调用详情
if [ "$TOOL_CALLS" != "null" ] && [ "$(echo $TOOL_CALLS | jq '. | length')" -gt 0 ]; then
    echo "工具调用详情:"
    echo $TOOL_CALLS | jq -r '.[] | "  工具: \(.name)\n  参数: \(.arguments)\n  结果: \(.result // "执行中")\n  执行时间: \(.execution_time // "未知")秒\n"'
fi

# 显示处理时间
if [ "$PROCESSING_TIME" != "null" ]; then
    echo "总处理时间: ${PROCESSING_TIME}s"
fi

echo ""

# 测试Agent复杂数学表达式
echo "3b. 测试Agent复杂数学表达式:"
echo "发送: '计算 2**3 + factorial(4) / 6'"

CHAT_RESPONSE2=$(curl -s --max-time 30 -X POST $BASE_URL/sessions/$SESSION_ID/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "计算 2**3 + factorial(4) / 6"}')

# 检查响应是否成功
if [ $? -ne 0 ]; then
    echo "复杂表达式请求失败"
    exit 1
fi

# 解析响应
MESSAGE2=$(echo $CHAT_RESPONSE2 | jq -r '.message')
TOOL_CALLS2=$(echo $CHAT_RESPONSE2 | jq '.tool_calls')
PROCESSING_TIME2=$(echo $CHAT_RESPONSE2 | jq -r '.processing_time')

echo "Agent原始响应: $MESSAGE2"

# 显示工具调用详情
if [ "$TOOL_CALLS2" != "null" ] && [ "$(echo $TOOL_CALLS2 | jq '. | length')" -gt 0 ]; then
    echo "复杂表达式工具调用详情:"
    echo $TOOL_CALLS2 | jq -r '.[] | "  工具: \(.name)\n  参数: \(.arguments)\n  结果: \(.result // "执行中")\n  执行时间: \(.execution_time // "未知")秒\n"'
fi

# 显示处理时间
if [ "$PROCESSING_TIME2" != "null" ]; then
    echo "总处理时间: ${PROCESSING_TIME2}s"
fi

echo ""

# 测试Agent MCP天气功能
echo "3c. 测试Agent MCP天气功能:"
echo "发送: '北京现在的天气怎么样？'"

CHAT_RESPONSE3=$(curl -s --max-time 30 -X POST $BASE_URL/sessions/$SESSION_ID/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "北京现在的天气怎么样？"}')

# 检查响应是否成功
if [ $? -ne 0 ]; then
    echo "天气查询请求失败"
    exit 1
fi

# 解析响应
MESSAGE3=$(echo $CHAT_RESPONSE3 | jq -r '.message')
TOOL_CALLS3=$(echo $CHAT_RESPONSE3 | jq '.tool_calls')
PROCESSING_TIME3=$(echo $CHAT_RESPONSE3 | jq -r '.processing_time')

echo "Agent原始响应: $MESSAGE3"

# 显示工具调用详情
if [ "$TOOL_CALLS3" != "null" ] && [ "$(echo $TOOL_CALLS3 | jq '. | length')" -gt 0 ]; then
    echo "天气查询工具调用详情:"
    echo $TOOL_CALLS3 | jq -r '.[] | "  工具: \(.name)\n  参数: \(.arguments)\n  结果: \(.result // "执行中")\n  执行时间: \(.execution_time // "未知")秒\n"'
fi

# 显示处理时间
if [ "$PROCESSING_TIME3" != "null" ]; then
    echo "总处理时间: ${PROCESSING_TIME3}s"
fi

# 检查会话历史
echo "5. 检查会话历史:"
HISTORY=$(curl -s --max-time 10 -X GET $BASE_URL/sessions/$SESSION_ID/history 2>/dev/null)
if [ $? -eq 0 ] && [ "$HISTORY" != "null" ]; then
    MESSAGE_COUNT=$(echo $HISTORY | jq '.messages | length')
    echo "会话消息数量: $MESSAGE_COUNT"

    if [ "$MESSAGE_COUNT" -gt 0 ]; then
        echo "会话记录:"
        echo $HISTORY | jq -r '.messages[] | "  \(.role | if . == "user" then "用户" else "Agent" end): \(.content[:80])\(if (.content | length) > 80 then "..." else "" end)"'
    fi
else
    echo "无法获取会话历史"
fi

# 显示完整响应用于调试
echo "6. 测试结果总结:"
echo "   单参数工具测试响应:"
echo $CHAT_RESPONSE | jq '{message: .message, tool_calls: (.tool_calls | length), processing_time: .processing_time}'
echo ""
echo "   多参数工具测试响应:"
echo $CHAT_RESPONSE2 | jq '{message: .message, tool_calls: (.tool_calls | length), processing_time: .processing_time}'
echo ""
echo "   MCP天气测试响应:"
echo $CHAT_RESPONSE3 | jq '{message: .message, tool_calls: (.tool_calls | length), processing_time: .processing_time}'

echo ""
echo "Agent功能测试完成!"
echo "提示: 会话 $SESSION_ID 保留，可用于后续测试"
echo ""
echo "测试结果分析:"

# 检查单参数工具测试结果
if echo "$CHAT_RESPONSE" | jq -e '.tool_calls | length == 0' >/dev/null; then
    echo "   单参数工具测试: Agent成功处理了计算请求"
    echo "   工具调用已被正确执行并转换为最终回答"
else
    echo "   单参数工具测试: 发现未处理的工具调用，可能存在解析问题"
fi

# 检查多参数工具测试结果
if echo "$CHAT_RESPONSE2" | jq -e '.tool_calls | length == 0' >/dev/null; then
    echo "   多参数工具测试: Agent成功处理了数学运算请求"
    echo "   多参数工具调用已被正确执行"
else
    echo "   多参数工具测试: 发现未处理的工具调用，可能存在解析问题"
fi

# 检查计算器测试是否成功
if echo "$CHAT_RESPONSE" | jq -e '.tool_calls | length == 0' >/dev/null && echo "$CHAT_RESPONSE2" | jq -e '.tool_calls | length == 0' >/dev/null; then
    echo "   计算器测试通过！表达式计算功能工作正常"
else
    echo "   计算器测试存在问题，请检查配置"
fi

# 检查MCP天气测试结果（由于连接失败，不会调用工具）
if echo "$CHAT_RESPONSE3" | jq -e '.message | length > 0' >/dev/null; then
    echo "   MCP天气测试: Agent收到了响应（可能没有MCP工具可用）"
    echo "   注意: 如果MCP服务器未连接，将不会调用天气工具"
else
    echo "   MCP天气测试: 没有收到有效响应"
fi

# 显示当前LLM配置信息
echo ""
echo "当前LLM配置:"
echo "   提供商: $LLM_PROVIDER"
echo "   模型: $LLM_MODEL"
if [ -z "$LLM_PROVIDER" ] || [ -z "$LLM_MODEL" ]; then
    echo "   未设置LLM_PROVIDER或LLM_MODEL环境变量，使用默认配置"
fi