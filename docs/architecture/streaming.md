# 流式输出设计（SSE 专项）

本文件聚焦 Zero Agent 当前的流式实现细节。  
整体架构与组件边界请先阅读：`docs/architecture/overview.md`。

## 1. 流式入口与边界

当前对外流式能力基于 **SSE**，统一通过以下端点开启：

- `POST /api/v1/chat`
- 请求体中设置 `stream: true`

说明：

- 不提供独立 `POST /api/v1/chat/stream` 端点
- 当前不提供 WebSocket 流式接口
- Gateway 与 Agent 间流式转发使用 HTTP + `text/event-stream`

## 2. 端到端链路

```text
Client
  -> POST /api/v1/chat (stream=true)
zero-gateway
  -> POST /agents/{agent_id}/chat?stream=true
zero-agent
  -> LangGraph workflow stream events
  -> emits SSE chunks
zero-gateway
  -> forwards SSE chunks to client
  -> aggregates assistant text for session persistence
```

## 3. 请求与响应格式

### 3.1 请求示例

```json
{
  "session_id": "sess_xxx",
  "message": "请一步步分析 2025 Q4 销售数据",
  "stream": true,
  "metadata": {
    "client": "web"
  }
}
```

### 3.2 SSE 数据块格式

每个数据块遵循 `data: <json>\n\n`：

```text
data: {"type":"content","content":"先看总体趋势。","done":false}

data: {"type":"tool_call_start","tool_call":{"id":"call_1","name":"calculator","arguments":{"expression":"..."}},"done":false}

data: {"type":"tool_call_end","tool_call_id":"call_1","result":"...","done":false}

data: {"type":"done","processing_time":1.42,"done":true}
```

## 4. 事件类型（当前实现）

- `content`：文本内容片段
- `tool_call_start`：工具调用开始
- `tool_call_end`：工具调用结束
- `error`：流式处理异常
- `done`：流式结束标记

与 `zero-agent/config/models.py` 中 `StreamChunk` 对齐的核心字段：

- `type`
- `content`（可选）
- `tool_call`（可选）
- `tool_call_id`（可选）
- `result`（可选）
- `error`（可选）
- `done`
- `processing_time`（通常在 `done` 中返回）

## 5. Gateway 转发行为

Gateway 处理流式请求时会：

1. 读取会话历史并注入给 Agent（若有）
2. 调用 Agent 内部流式接口：`/agents/{agent_id}/chat?stream=true`
3. 设置 SSE 响应头并逐块转发
4. 解析流内文本内容，流结束后写回会话历史

这保证了流式体验和会话持久化同时成立。

## 6. 超时、断连与错误处理

### 6.1 上游调用异常

- Agent 不可达/超时：Gateway 返回 `503`，并附带标准错误字段
- Agent 返回错误状态码：Gateway 映射并透出错误

### 6.2 流中异常

- 若流式执行中出现错误，Agent 会发送 `type=error` 数据块并结束
- Gateway 记录错误日志；若客户端中断连接，按断连场景处理

### 6.3 客户端断连

- Gateway 检测请求上下文取消后停止转发
- 已收到的内容不再继续推送
- 会话写回按已收集内容执行（可能是部分内容）

## 7. 最小可用验证

```bash
curl -N -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_xxx",
    "message": "计算 123 * 456",
    "stream": true
  }'
```

期望看到连续 `data: {...}` 输出，并以 `type=done` 结束。

## 8. 与其他文档的关系

- 架构全景：`docs/architecture/overview.md`
- 字段与接口定义：`docs/api/reference.md`
- 调用样例：`docs/api/examples.md`
