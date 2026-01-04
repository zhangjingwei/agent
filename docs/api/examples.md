# API使用示例

## 快速开始

### 使用cURL

```bash
# 1. 检查服务状态
curl http://localhost:8080/health

# 2. 创建会话
curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"user": "demo"}}'

# 3. 发送消息
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "message": "计算 123 + 456"
  }'
```

### 使用Python

```python
import requests

class AgentClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url

    def create_session(self, metadata=None):
        """创建会话"""
        response = requests.post(f"{self.base_url}/api/v1/sessions", json={
            "metadata": metadata or {}
        })
        return response.json()

    def chat(self, session_id, message, metadata=None):
        """发送消息"""
        response = requests.post(f"{self.base_url}/api/v1/chat", json={
            "session_id": session_id,
            "message": message,
            "metadata": metadata or {}
        })
        return response.json()

    def get_history(self, session_id):
        """获取历史"""
        response = requests.get(f"{self.base_url}/api/v1/sessions/{session_id}/history")
        return response.json()

    def list_tools(self):
        """列出工具"""
        response = requests.get(f"{self.base_url}/api/v1/tools")
        return response.json()

# 使用示例
client = AgentClient()

# 创建会话
session = client.create_session({"user": "example"})
session_id = session["session_id"]
print(f"创建会话: {session_id}")

# 发送消息
response = client.chat(session_id, "计算 15 + 27")
print(f"Agent回复: {response['message']}")

# 查看工具调用
if response.get("tool_calls"):
    print("使用的工具:")
    for tool in response["tool_calls"]:
        print(f"  - {tool['name']}: {tool['arguments']}")
```

## 流式输出API

### 流式对话

#### Server-Sent Events (SSE) 流式
```bash
# 流式对话 - SSE
curl -X POST http://localhost:8080/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_123",
    "message": "请介绍一下机器学习",
    "stream": true
  }'
```

**SSE响应格式**:
```
data: {"type": "content", "content": "机", "done": false}
data: {"type": "content", "content": "器", "done": false}
data: {"type": "content", "content": "学", "done": false}
data: {"type": "content", "content": "习", "done": false}
data: {"type": "tool_call_start", "tool_call": {"id": "call_123", "name": "web_search", "arguments": {"query": "机器学习"}}, "done": false}
data: {"type": "tool_call_end", "tool_call_id": "call_123", "result": "...搜索结果...", "done": false}
data: {"type": "done", "done": true}
```

#### JavaScript客户端示例
```javascript
// SSE流式客户端
function streamChat(message, sessionId) {
    const eventSource = new EventSource('/api/v1/chat/stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            session_id: sessionId,
            message: message,
            stream: true
        })
    });

    eventSource.onmessage = function(event) {
        const chunk = JSON.parse(event.data);

        switch(chunk.type) {
            case 'content':
                // 实时显示内容
                displayContent(chunk.content);
                break;
            case 'tool_call_start':
                // 显示工具调用开始
                showToolCall(chunk.tool_call);
                break;
            case 'tool_call_end':
                // 显示工具调用结果
                showToolResult(chunk.tool_call_id, chunk.result);
                break;
            case 'done':
                // 流式完成
                eventSource.close();
                onStreamComplete();
                break;
            case 'error':
                // 处理错误
                handleError(chunk.error);
                eventSource.close();
                break;
        }
    };

    eventSource.onerror = function(error) {
        console.error('Stream error:', error);
        handleConnectionError();
    };

    return eventSource;
}

// 使用示例
const stream = streamChat("解释量子计算", "session_123");
// 稍后可以调用 stream.close() 来中断流式输出
```

#### Python客户端示例
```python
import json
import requests
from sseclient import SSEClient

class StreamingClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url

    def stream_chat(self, message, session_id, callback=None):
        """流式对话"""
        url = f"{self.base_url}/api/v1/chat/stream"

        # 启动SSE连接
        response = requests.post(url, json={
            "session_id": session_id,
            "message": message,
            "stream": True
        }, stream=True)

        client = SSEClient(response)

        for event in client.events():
            if event.data == '[DONE]':
                break

            chunk = json.loads(event.data)

            if callback:
                callback(chunk)
            else:
                self._default_handler(chunk)

    def _default_handler(self, chunk):
        """默认的数据块处理器"""
        if chunk['type'] == 'content':
            print(chunk['content'], end='', flush=True)
        elif chunk['type'] == 'tool_call_start':
            print(f"\n[工具调用] {chunk['tool_call']['name']}", flush=True)
        elif chunk['type'] == 'tool_call_end':
            print(f"[工具完成] {chunk['tool_call_id']}", flush=True)
        elif chunk['type'] == 'done':
            print("\n[完成]", flush=True)

# 使用示例
client = StreamingClient()
print("AI: ", end='')
client.stream_chat("计算 123 * 456", "session_123")
```

#### WebSocket流式 (未来支持)
```javascript
// WebSocket流式客户端 (规划中)
const ws = new WebSocket('ws://localhost:8080/ws/chat');

ws.onopen = function() {
    // 发送初始消息
    ws.send(JSON.stringify({
        session_id: "session_123",
        message: "Hello",
        stream: true
    }));
};

ws.onmessage = function(event) {
    const chunk = JSON.parse(event.data);
    handleStreamChunk(chunk);
};

// 双向通信支持
function sendFollowUpMessage(message) {
    ws.send(JSON.stringify({
        type: "message",
        content: message
    }));
}
```

### 流式数据块格式

#### StreamChunk 数据结构
```typescript
interface StreamChunk {
  // 数据块类型
  type: 'content' | 'tool_call_start' | 'tool_call_end' | 'error' | 'done';

  // 内容数据 (type = 'content')
  content?: string;

  // 工具调用信息 (type = 'tool_call_start')
  tool_call?: {
    id: string;
    name: string;
    arguments: Record<string, any>;
  };

  // 工具调用结果 (type = 'tool_call_end')
  tool_call_id?: string;
  result?: any;

  // 错误信息 (type = 'error')
  error?: string;

  // 元数据
  metadata?: Record<string, any>;

  // 完成标志
  done: boolean;

  // 时间戳
  timestamp?: string;
}
```

#### 数据块类型说明

| 类型 | 说明 | 数据字段 |
|------|------|----------|
| `content` | 文本内容块 | `content` |
| `tool_call_start` | 工具调用开始 | `tool_call` |
| `tool_call_end` | 工具调用结束 | `tool_call_id`, `result` |
| `error` | 流式错误 | `error` |
| `done` | 流式完成 | 无 |

### 流式配置参数

```json
{
  "session_id": "session_123",
  "message": "用户消息",
  "stream": true,
  "stream_options": {
    "include_usage": true,
    "max_tokens": 1000,
    "temperature": 0.7
  },
  "metadata": {
    "user_id": "user_456",
    "client_version": "1.0.0"
  }
}
```

### 错误处理

#### 流式错误示例
```
data: {"type": "error", "error": "Rate limit exceeded", "done": true}
data: {"type": "done", "done": true}
```

#### 客户端错误处理
```javascript
function handleStreamError(chunk) {
    switch(chunk.error) {
        case 'rate_limit_exceeded':
            // 显示限流提示
            showRateLimitMessage();
            break;
        case 'session_not_found':
            // 重新创建会话
            createNewSession();
            break;
        default:
            // 通用错误处理
            showErrorMessage(chunk.error);
    }
}
```

## 对话场景示例

### 1. 简单问答

```python
import requests

BASE_URL = "http://localhost:8080"

# 创建会话
session = requests.post(f"{BASE_URL}/api/v1/sessions").json()
session_id = session["session_id"]

# 问答交互
questions = [
    "你好，请介绍一下你自己",
    "你能做什么？",
    "请解释一下工具调用是如何工作的"
]

for question in questions:
    response = requests.post(f"{BASE_URL}/api/v1/chat", json={
        "session_id": session_id,
        "message": question
    }).json()

    print(f"用户: {question}")
    print(f"Agent: {response['message']}")
    print("-" * 50)
```

### 2. 数学计算

```python
import requests

def math_demo():
    BASE_URL = "http://localhost:8080"

    # 创建会话
    session = requests.post(f"{BASE_URL}/api/v1/sessions").json()
    session_id = session["session_id"]

    calculations = [
        "计算 1 + 1",
        "计算 2^10",
        "计算 100 的阶乘",
        "计算圆周率前5位"
    ]

    for calc in calculations:
        print(f"请求: {calc}")

        response = requests.post(f"{BASE_URL}/api/v1/chat", json={
            "session_id": session_id,
            "message": calc
        }).json()

        print(f"结果: {response['message']}")

        # 显示工具调用详情
        if response.get("tool_calls"):
            for tool in response["tool_calls"]:
                print(f"  工具: {tool['name']}")
                print(f"  参数: {tool['arguments']}")

        print("-" * 30)

math_demo()
```

### 3. 多轮对话

```python
import requests
import time

def conversation_demo():
    BASE_URL = "http://localhost:8080"

    # 创建会话
    session = requests.post(f"{BASE_URL}/api/v1/sessions").json()
    session_id = session["session_id"]

    # 多轮对话
    conversation = [
        "我想建一个简单的待办事项应用",
        "它需要支持添加、删除、列出任务",
        "请用Python代码实现",
        "如何添加数据持久化？",
        "能否加上任务优先级功能？"
    ]

    for i, message in enumerate(conversation, 1):
        print(f"\n--- 第 {i} 轮对话 ---")
        print(f"用户: {message}")

        response = requests.post(f"{BASE_URL}/api/v1/chat", json={
            "session_id": session_id,
            "message": message
        }).json()

        print(f"Agent: {response['message']}")
        print(".2f")

        # 短暂延迟，模拟真实对话节奏
        time.sleep(1)

conversation_demo()
```

### 4. 错误处理

```python
import requests
from requests.exceptions import RequestException, Timeout

def error_handling_demo():
    BASE_URL = "http://localhost:8080"

    def safe_api_call(method, url, **kwargs):
        """安全的API调用"""
        try:
            response = requests.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_data = e.response.json()
            print(f"API错误 ({e.response.status_code}): {error_data.get('message', '未知错误')}")
            return None
        except Timeout:
            print("请求超时")
            return None
        except RequestException as e:
            print(f"网络错误: {e}")
            return None

    # 测试场景
    test_cases = [
        # 正常请求
        {
            "name": "正常对话",
            "method": "POST",
            "url": f"{BASE_URL}/api/v1/chat",
            "json": {"session_id": "test-session", "message": "你好"}
        },

        # 会话不存在
        {
            "name": "无效会话",
            "method": "POST",
            "url": f"{BASE_URL}/api/v1/chat",
            "json": {"session_id": "nonexistent", "message": "test"}
        },

        # 无效请求
        {
            "name": "无效请求",
            "method": "POST",
            "url": f"{BASE_URL}/api/v1/chat",
            "json": {"message": "缺少session_id"}
        }
    ]

    for test_case in test_cases:
        print(f"\n测试: {test_case['name']}")
        result = safe_api_call(**{k: v for k, v in test_case.items() if k != 'name'})

        if result:
            if 'message' in result:
                print(f"成功: {result['message'][:50]}...")
            else:
                print(f"成功: {result}")
        else:
            print("请求失败")

error_handling_demo()
```

## 高级用法

### 1. 会话管理

```python
import requests

def session_management_demo():
    BASE_URL = "http://localhost:8080"

    # 创建多个会话
    sessions = []
    for i in range(3):
        session = requests.post(f"{BASE_URL}/api/v1/sessions", json={
            "metadata": {"user": f"user_{i}", "purpose": "demo"}
        }).json()
        sessions.append(session)
        print(f"创建会话 {i+1}: {session['session_id']}")

    # 在不同会话中对话
    messages = ["你好", "再见", "谢谢"]

    for i, session in enumerate(sessions):
        print(f"\n--- 会话 {i+1} ---")

        response = requests.post(f"{BASE_URL}/api/v1/chat", json={
            "session_id": session["session_id"],
            "message": messages[i]
        }).json()

        print(f"用户: {messages[i]}")
        print(f"Agent: {response['message']}")

        # 获取会话历史
        history = requests.get(f"{BASE_URL}/api/v1/sessions/{session['session_id']}/history").json()
        print(f"会话消息数: {len(history.get('messages', []))}")

session_management_demo()
```

### 2. 批量处理

```python
import asyncio
import aiohttp
import json

async def batch_processing_demo():
    """异步批量处理示例"""

    async def chat_request(session_id, message):
        """单个聊天请求"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8080/api/v1/chat",
                json={"session_id": session_id, "message": message},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                return await response.json()

    # 创建会话
    async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:8080/api/v1/sessions") as response:
            session_data = await response.json()
            session_id = session_data["session_id"]

    # 批量发送消息
    messages = [
        f"计算 {i} + {i*2}" for i in range(1, 6)
    ]

    print("开始批量处理...")
    start_time = asyncio.get_event_loop().time()

    # 并发处理所有请求
    tasks = [chat_request(session_id, msg) for msg in messages]
    results = await asyncio.gather(*tasks)

    end_time = asyncio.get_event_loop().time()

    # 显示结果
    print(".2f"    print(f"处理了 {len(results)} 个请求")

    for i, result in enumerate(results, 1):
        print(f"{i}. {messages[i-1]} = {result['message']}")

asyncio.run(batch_processing_demo())
```

### 3. 实时流式响应

```python
import requests
import json

def streaming_demo():
    """模拟流式响应处理"""
    BASE_URL = "http://localhost:8080"

    # 创建会话
    session = requests.post(f"{BASE_URL}/sessions").json()
    session_id = session["session_id"]

    # 复杂的请求，可能会需要更长的处理时间
    complex_queries = [
        "写一个Python函数来计算斐波那契数列",
        "解释一下机器学习的工作原理",
        "设计一个简单的REST API架构"
    ]

    for query in complex_queries:
        print(f"\n查询: {query}")

        # 发送请求
        response = requests.post(f"{BASE_URL}/chat", json={
            "session_id": session_id,
            "message": query
        }, timeout=60)  # 较长的超时时间

        if response.status_code == 200:
            data = response.json()
            print(f"响应长度: {len(data['message'])} 字符")
            print(f"处理时间: {data['processing_time']:.2f}秒")

            if data.get('tool_calls'):
                print(f"使用了 {len(data['tool_calls'])} 个工具")
            else:
                print("直接回复，无工具调用")

            # 显示响应预览
            preview = data['message'][:100]
            print(f"预览: {preview}{'...' if len(data['message']) > 100 else ''}")
        else:
            print(f"请求失败: {response.status_code}")

streaming_demo()
```

### 4. 监控和日志

```python
import requests
import time
from datetime import datetime

def monitoring_demo():
    """监控和性能测试"""
    BASE_URL = "http://localhost:8080"

    # 性能测试
    def benchmark_requests(num_requests=10):
        """基准测试"""
        session = requests.post(f"{BASE_URL}/sessions").json()
        session_id = session["session_id"]

        times = []
        for i in range(num_requests):
            start_time = time.time()

            response = requests.post(f"{BASE_URL}/api/v1/chat", json={
                "session_id": session_id,
                "message": f"计算 {i} * {i+1}"
            })

            end_time = time.time()
            times.append(end_time - start_time)

            if response.status_code != 200:
                print(f"请求 {i+1} 失败: {response.status_code}")

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"\n性能测试结果 ({num_requests} 个请求):")
        print(f"  平均响应时间: {avg_time:.3f}秒")
        print(f"  最快响应时间: {min_time:.3f}秒")
        print(f"  最慢响应时间: {max_time:.3f}秒")
        print(f"  吞吐量: {num_requests / sum(times):.2f} 请求/秒")

    # 健康检查监控
    def health_monitor(duration_seconds=60):
        """健康监控"""
        print(f"开始 {duration_seconds} 秒健康监控...")

        start_time = time.time()
        checks = 0
        failures = 0

        while time.time() - start_time < duration_seconds:
            try:
                response = requests.get(f"{BASE_URL}/health", timeout=5)
                if response.status_code == 200:
                    print(".", end="", flush=True)
                else:
                    print("F", end="", flush=True)
                    failures += 1
            except:
                print("F", end="", flush=True)
                failures += 1

            checks += 1
            time.sleep(2)  # 每2秒检查一次

        success_rate = (checks - failures) / checks * 100
        print(".1f"
    # 运行测试
    print("=== 性能测试 ===")
    benchmark_requests(20)

    print("\n=== 健康监控 ===")
    health_monitor(30)

monitoring_demo()
```

## 不同编程语言示例

### JavaScript/Node.js

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:8080';

async function jsExample() {
    try {
        // 创建会话
        const sessionResponse = await axios.post(`${BASE_URL}/api/v1/sessions`, {
            metadata: { user: 'nodejs-client' }
        });
        const sessionId = sessionResponse.data.session_id;

        // 发送消息
        const chatResponse = await axios.post(`${BASE_URL}/api/v1/chat`, {
            session_id: sessionId,
            message: '计算 1 + 2 * 3'
        });

        console.log('Agent回复:', chatResponse.data.message);
        console.log('处理时间:', chatResponse.data.processing_time, '秒');

    } catch (error) {
        console.error('请求失败:', error.response?.data || error.message);
    }
}

jsExample();
```

### Go

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
)

const BASE_URL = "http://localhost:8080"

type ChatRequest struct {
    SessionID string `json:"session_id"`
    Message   string `json:"message"`
}

type ChatResponse struct {
    Message       string      `json:"message"`
    ToolCalls     interface{} `json:"tool_calls,omitempty"`
    ProcessingTime float64    `json:"processing_time"`
}

func main() {
    // 创建会话
    resp, err := http.Post(BASE_URL+"/api/v1/sessions", "application/json", bytes.NewBufferString("{}"))
    if err != nil {
        panic(err)
    }
    defer resp.Body.Close()

    var sessionData map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&sessionData)
    sessionID := sessionData["session_id"].(string)

    // 发送消息
    chatReq := ChatRequest{
        SessionID: sessionID,
        Message:   "计算斐波那契数列第10项",
    }

    reqBody, _ := json.Marshal(chatReq)
    resp, err = http.Post(BASE_URL+"/api/v1/chat", "application/json", bytes.NewBuffer(reqBody))
    if err != nil {
        panic(err)
    }
    defer resp.Body.Close()

    var chatResp ChatResponse
    json.NewDecoder(resp.Body).Decode(&chatResp)

    fmt.Printf("Agent回复: %s\n", chatResp.Message)
    fmt.Printf("处理时间: %.2f秒\n", chatResp.ProcessingTime)
}
```

## 生产环境配置

### 负载均衡

```python
import requests
from typing import List

class LoadBalancedClient:
    """负载均衡客户端"""

    def __init__(self, servers: List[str]):
        self.servers = servers
        self.current_server = 0

    def _get_server(self) -> str:
        """轮询获取服务器"""
        server = self.servers[self.current_server]
        self.current_server = (self.current_server + 1) % len(self.servers)
        return server

    def chat(self, session_id: str, message: str):
        """带重试的聊天请求"""
        max_retries = 3

        for attempt in range(max_retries):
            server = self._get_server()
            try:
                response = requests.post(
                    f"{server}/chat",
                    json={"session_id": session_id, "message": message},
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
            except (requests.exceptions.RequestException, requests.exceptions.HTTPError):
                if attempt == max_retries - 1:
                    raise
                continue

# 使用示例
client = LoadBalancedClient([
    "http://server1:8080/api/v1",
    "http://server2:8080/api/v1",
    "http://server3:8080/api/v1"
])

response = client.chat("session-123", "计算 1+1")
print(response["message"])
```

### 连接池管理

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_resilient_session():
    """创建具有重试和连接池的会话"""
    session = requests.Session()

    # 配置重试策略
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        backoff_factor=1
    )

    # 配置适配器
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,    # 连接池大小
        pool_maxsize=20         # 最大连接数
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

# 使用示例
session = create_resilient_session()

response = session.post("http://localhost:8080/api/v1/chat", json={
    "session_id": "session-123",
    "message": "测试请求"
})

print(response.json())
```
