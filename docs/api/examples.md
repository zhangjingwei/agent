# API 使用示例

本文档基于当前 Gateway API（`http://localhost:8080`）整理，示例均可直接验证。

## 快速验证（cURL）

```bash
# 1) 健康检查
curl http://localhost:8080/health

# 2) 创建会话
curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"metadata":{"user":"demo","source":"curl"}}'

# 3) 普通对话（非流式）
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "替换为上一步返回的 session_id",
    "message": "计算 123 + 456",
    "stream": false
  }'
```

## 会话相关

### 创建会话

```bash
curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"metadata":{"user_id":"u001","tags":["demo"]}}'
```

示例响应：

```json
{
  "session_id": "sess_xxx",
  "agent_id": "zero",
  "created_at": "2026-03-07T10:00:00Z",
  "metadata": {
    "user_id": "u001",
    "tags": ["demo"]
  }
}
```

### 查询会话历史

```bash
curl "http://localhost:8080/api/v1/sessions/sess_xxx/history?limit=20"
```

### 删除会话

```bash
curl -X DELETE http://localhost:8080/api/v1/sessions/sess_xxx
```

## 对话接口

### 非流式对话

```bash
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_xxx",
    "message": "请帮我算 15 * 27",
    "stream": false,
    "metadata": {"client":"curl"}
  }'
```

示例响应（Gateway 当前返回 `data` 包裹）：

```json
{
  "data": {
    "message": "15 * 27 = 405",
    "tool_calls": [
      {
        "id": "call_123",
        "name": "calculator",
        "arguments": {
          "expression": "15 * 27"
        },
        "result": "405"
      }
    ],
    "usage": {
      "prompt_tokens": 120,
      "completion_tokens": 25,
      "total_tokens": 145
    },
    "processing_time": 0.82
  }
}
```

### 流式对话（SSE）

> 当前流式与非流式共用同一个端点：`POST /api/v1/chat`，通过 `stream=true` 开启流式。

```bash
curl -N -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_xxx",
    "message": "请分析今天的销售趋势并给出建议",
    "stream": true
  }'
```

示例 SSE 数据块：

```text
data: {"type":"content","content":"好的，我们先看整体趋势。","done":false}

data: {"type":"tool_call_start","tool_call":{"id":"call_1","name":"calculator","arguments":{"expression":"..."}},"done":false}

data: {"type":"tool_call_end","tool_call_id":"call_1","result":"...","done":false}

data: {"type":"done","processing_time":1.37,"done":true}
```

## 工具列表

### 列出默认 Agent 工具

```bash
curl http://localhost:8080/api/v1/tools
```

### 指定 Agent 查询工具（可选）

```bash
curl "http://localhost:8080/api/v1/tools?agent_id=zero"
```

示例响应：

```json
{
  "agent_id": "zero",
  "tools": [
    {
      "id": "calculator",
      "name": "calculator",
      "description": "执行数学表达式计算",
      "type": "builtin",
      "parameters": {
        "type": "object",
        "properties": {
          "expression": {"type": "string"}
        }
      }
    }
  ]
}
```

## Python 示例（requests）

```python
import requests

BASE_URL = "http://localhost:8080"

# 1) 创建会话
sess = requests.post(
    f"{BASE_URL}/api/v1/sessions",
    json={"metadata": {"user": "python-demo"}}
).json()
session_id = sess["session_id"]

# 2) 非流式对话
resp = requests.post(
    f"{BASE_URL}/api/v1/chat",
    json={
        "session_id": session_id,
        "message": "计算 2^10",
        "stream": False
    },
    timeout=60,
).json()

print("reply:", resp["data"]["message"])
print("tool_calls:", resp["data"].get("tool_calls", []))

# 3) 查询历史
history = requests.get(
    f"{BASE_URL}/api/v1/sessions/{session_id}/history?limit=10",
    timeout=30,
).json()
print("history_count:", len(history.get("messages", [])))
```

## Python 示例（SSE 流式）

```python
import json
import requests

BASE_URL = "http://localhost:8080"

session_id = requests.post(
    f"{BASE_URL}/api/v1/sessions", json={}
).json()["session_id"]

with requests.post(
    f"{BASE_URL}/api/v1/chat",
    json={
        "session_id": session_id,
        "message": "请一步步解释 144 的平方根",
        "stream": True
    },
    stream=True,
    timeout=120,
) as resp:
    resp.raise_for_status()
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw:
            continue
        if not raw.startswith("data: "):
            continue
        chunk = json.loads(raw[len("data: "):])
        ctype = chunk.get("type")
        if ctype == "content":
            print(chunk.get("content", ""), end="", flush=True)
        elif ctype == "tool_call_start":
            print(f"\n[tool start] {chunk.get('tool_call', {}).get('name')}")
        elif ctype == "tool_call_end":
            print(f"\n[tool end] {chunk.get('tool_call_id')}")
        elif ctype == "error":
            print(f"\n[error] {chunk.get('error')}")
        elif ctype == "done":
            print("\n[done]")
            break
```

## 常见问题

- `404 session not found`：请先调用 `POST /api/v1/sessions` 创建会话，再发起对话。
- 流式无输出：检查是否使用 `stream=true`，并确保客户端支持 `text/event-stream`。
- 工具列表为空：检查 Agent 配置中工具是否启用，以及 MCP 服务是否可连接（不可连接时会降级运行）。
