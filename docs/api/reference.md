# API参考文档

## 概述

Zero Agent 提供 RESTful API 接口，支持与 AI Agent 进行对话交互。

**Base URL**: `http://localhost:8080`

**API版本**: v1

**API前缀**: `/api/v1`

## 认证

目前API不需要认证，后续版本会添加API密钥认证。

## 公共响应格式

### 成功响应
```json
{
  "status": "success",
  "data": { ... },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 错误响应
```json
{
  "status": "error",
  "message": "错误描述",
  "code": "ERROR_CODE",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 端点

### 1. 健康检查

检查服务是否正常运行。

**端点**: `GET /health`

**响应**:
```json
{
  "status": "healthy",
  "service": "api-gateway",
  "timestamp": 1704067200
}
```

**状态码**:
- `200`: 服务正常
- `503`: 服务不可用

---

### 2. 创建会话

创建新的对话会话。

**端点**: `POST /api/v1/sessions`

**请求体**:
```json
{
  "metadata": {
    "user_id": "user123",
    "session_type": "chat",
    "tags": ["demo", "test"]
  }
}
```

**参数说明**:
- `metadata` (可选): 会话元数据
  - `user_id`: 用户标识
  - `session_type`: 会话类型
  - `tags`: 标签列表

**响应**:
```json
{
  "session_id": "uuid-generated-session-id",
  "agent_id": "demo-agent",
  "created_at": "2024-01-01T00:00:00Z",
  "metadata": {
    "user_id": "user123",
    "session_type": "chat"
  }
}
```

**状态码**:
- `201`: 会话创建成功
- `400`: 请求参数错误
- `503`: 服务不可用

---

### 3. 发送消息

向Agent发送消息并获取回复。

**端点**: `POST /api/v1/chat`

**请求体**:
```json
{
  "session_id": "sess_abc123def456",
  "message": "计算 15 + 27 的结果",
  "metadata": {
    "priority": "normal",
    "timeout": 30
  }
}
```

**参数说明**:
- `session_id` (必需): 会话ID
- `message` (必需): 用户消息
- `metadata` (可选): 消息元数据
  - `priority`: 优先级 ("low", "normal", "high")
  - `timeout`: 超时时间(秒)

**响应**:
```json
{
  "message": "15 + 27 = 42",
  "tool_calls": [
    {
      "id": "call_123456",
      "name": "calculator",
      "arguments": {
        "expression": "15 + 27"
      },
      "result": "42",
      "execution_time": 0.05
    }
  ],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 25,
    "total_tokens": 175
  },
  "processing_time": 1.23
}
```

**响应字段**:
- `message`: Agent回复消息
- `tool_calls`: 使用的工具列表（可选）
- `usage`: Token使用统计（可选）
- `processing_time`: 处理时间(秒)

**状态码**:
- `200`: 消息处理成功
- `400`: 请求参数错误
- `404`: 会话不存在
- `408`: 请求超时
- `503`: 服务不可用

---

### 4. 获取会话历史

获取指定会话的消息历史。

**端点**: `GET /api/v1/sessions/{session_id}/history`

**路径参数**:
- `session_id`: 会话ID

**查询参数**:
- `limit` (可选): 返回的最大消息数量，默认所有
- `offset` (可选): 跳过的消息数量，默认0

**响应**:
```json
{
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "计算 15 + 27 的结果",
      "timestamp": "2024-01-01T00:00:00Z",
      "metadata": null
    },
    {
      "id": "msg_002",
      "role": "assistant",
      "content": "15 + 27 = 42",
      "timestamp": "2024-01-01T00:00:01Z",
      "metadata": null
    }
  ]
}
```

**状态码**:
- `200`: 获取成功
- `404`: 会话不存在
- `503`: 服务不可用

---

### 5. 列出可用工具

获取当前可用的工具列表。

**端点**: `GET /api/v1/tools`

**响应**:
```json
{
  "tools": [
    {
      "id": "calculator",
      "name": "calculator",
      "description": "数学计算器，支持四则运算",
      "parameters": {}
    }
  ]
}
```

**状态码**:
- `200`: 获取成功
- `503`: 服务不可用

---

### 6. 删除会话

删除指定的会话及其所有历史记录。

**端点**: `DELETE /api/v1/sessions/{session_id}`

**路径参数**:
- `session_id`: 要删除的会话ID

**响应**:
```json
{
  "message": "会话已删除",
  "session_id": "sess_abc123def456"
}
```

**状态码**:
- `200`: 删除成功
- `404`: 会话不存在
- `503`: 服务不可用

## 数据模型

### 会话 (Session)

```typescript
interface Session {
  session_id: string;
  created_at: string;  // ISO 8601格式
  metadata?: {
    user_id?: string;
    session_type?: string;
    tags?: string[];
    [key: string]: any;
  };
}
```

### 消息 (Message)

```typescript
interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;  // ISO 8601格式
  tool_calls?: ToolCall[];
  metadata?: Record<string, any>;
}
```

### 工具调用 (ToolCall)

```typescript
interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, any>;
  result?: any;
  error?: string;
  execution_time?: number;
}
```

### 聊天请求 (ChatRequest)

```typescript
interface ChatRequest {
  session_id: string;
  message: string;
  metadata?: {
    priority?: "low" | "normal" | "high";
    timeout?: number;
    [key: string]: any;
  };
}
```

### 聊天响应 (ChatResponse)

```typescript
interface ChatResponse {
  message: string;
  tool_calls?: ToolCall[];
  usage?: Usage;
  processing_time: number;
}
```

## 错误码

### 客户端错误 (4xx)

- `400 Bad Request`: 请求参数无效
  ```json
  {
    "error": "Invalid request format"
  }
  ```

- `404 Not Found`: 资源不存在
  ```json
  {
    "error": "Session not found"
  }
  ```

- `408 Request Timeout`: 请求超时
  ```json
  {
    "error": "Request timeout"
  }
  ```

### 服务端错误 (5xx)

- `500 Internal Server Error`: 服务器内部错误
  ```json
  {
    "error": "Internal server error"
  }
  ```

- `503 Service Unavailable`: 服务不可用
  ```json
  {
    "error": "Agent service unavailable"
  }
  ```

## 限制和配额

### 请求限制
- **最大消息长度**: 4096字符
- **最大会话历史**: 100条消息
- **请求频率限制**: 每分钟100次请求

### 处理限制
- **最大处理时间**: 60秒
- **最大工具调用**: 5个工具/请求
- **最大并发请求**: 10个并发连接

## SDK使用

### Python SDK

```python
from sdk.python import UniversalAgentSDK

# 初始化SDK
sdk = UniversalAgentSDK()

# 创建会话
session_id = await sdk.create_session("user123")

# 发送消息
response = await sdk.chat(session_id, "计算 1 + 2 * 3")

print(f"Agent: {response['message']}")
print(f"Tools used: {len(response.get('tool_calls', []))}")
```

### 其他语言

目前仅提供Python SDK，其他语言SDK正在开发中。

## 示例代码

### 基本对话

```python
import requests

BASE_URL = "http://localhost:8080"

# 1. 创建会话
response = requests.post(f"{BASE_URL}/sessions")
session_id = response.json()["session_id"]

# 2. 发送消息
response = requests.post(f"{BASE_URL}/chat", json={
    "session_id": session_id,
    "message": "你好！"
})

print(response.json()["message"])
```

### 工具使用

```python
import requests

BASE_URL = "http://localhost:8080"

# 创建会话
response = requests.post(f"{BASE_URL}/sessions")
session_id = response.json()["session_id"]

# 发送计算请求
response = requests.post(f"{BASE_URL}/chat", json={
    "session_id": session_id,
    "message": "计算圆周率的平方"
})

data = response.json()
print(f"结果: {data['message']}")

# 查看使用的工具
for tool in data.get("tool_calls", []):
    print(f"使用了工具: {tool['name']}")
```

### 错误处理

```python
import requests
from requests.exceptions import RequestException

BASE_URL = "http://localhost:8080"

def safe_request(method, url, **kwargs):
    try:
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        error_data = e.response.json()
        print(f"API错误: {error_data['message']}")
        raise
    except RequestException as e:
        print(f"网络错误: {e}")
        raise

# 使用示例
try:
    result = safe_request("POST", f"{BASE_URL}/chat", json={
        "session_id": "invalid-session",
        "message": "test"
    })
except Exception as e:
    print(f"请求失败: {e}")
```

## 版本信息

- **API版本**: v1
- **兼容性**: 向后兼容，新增字段为可选
- **废弃策略**: 废弃功能将在3个版本后移除

## 更新日志

### v1.0.0
- 初始API版本发布
- 支持基本对话功能
- 支持工具调用
- 支持会话管理
