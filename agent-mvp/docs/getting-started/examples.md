# 使用示例

## 基本对话

### 简单问答
```python
import asyncio
from sdk.python import UniversalAgentSDK

async def basic_chat():
    async with UniversalAgentSDK() as sdk:
        # 创建会话
        session_id = await sdk.create_session("example-user")

        # 发送消息
        response = await sdk.chat(session_id, "你好，请介绍一下你自己")
        print(f"Agent: {response['message']}")

asyncio.run(basic_chat())
```

### 工具调用示例
```python
import asyncio
from sdk.python import UniversalAgentSDK

async def calculator_example():
    async with UniversalAgentSDK() as sdk:
        session_id = await sdk.create_session("calc-user")

        # 数学计算
        response = await sdk.chat(session_id, "计算 (15 + 27) * 3 的结果")

        print(f"Agent: {response['message']}")

        # 显示工具调用详情
        if response.get('tool_calls'):
            for tool_call in response['tool_calls']:
                print(f"工具调用: {tool_call['name']}")
                print(f"参数: {tool_call['arguments']}")

asyncio.run(calculator_example())
```

## REST API示例

### 使用curl

#### 创建会话
```bash
curl -X POST http://localhost:8080/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "user_id": "user123",
      "session_type": "demo"
    }
  }'
```

#### 发送消息
```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "message": "请帮我计算一个复杂的数学表达式：(2 + 3) * (4 - 1) + 10 / 2",
    "metadata": {
      "priority": "normal"
    }
  }'
```

#### 获取会话历史
```bash
curl http://localhost:8080/sessions/your-session-id/history
```

#### 健康检查
```bash
curl http://localhost:8080/health
```

### 使用Python requests

```python
import requests

# 基础配置
BASE_URL = "http://localhost:8080"

def api_example():
    # 1. 创建会话
    response = requests.post(f"{BASE_URL}/sessions", json={
        "metadata": {"user": "api-example"}
    })
    session_data = response.json()
    session_id = session_data["session_id"]
    print(f"创建会话: {session_id}")

    # 2. 发送多个消息
    messages = [
        "你好！",
        "请计算 144 的平方根",
        "这个结果乘以2等于多少？",
        "再加上100呢？"
    ]

    for message in messages:
        response = requests.post(f"{BASE_URL}/chat", json={
            "session_id": session_id,
            "message": message
        })

        data = response.json()
        print(f"\n用户: {message}")
        print(f"Agent: {data['message']}")

        if data.get('tool_calls'):
            print(f"工具调用: {len(data['tool_calls'])} 次")

        print(".2f"
    # 3. 查看历史记录
    history = requests.get(f"{BASE_URL}/sessions/{session_id}/history")
    print(f"\n会话总消息数: {len(history.json())}")

if __name__ == "__main__":
    api_example()
```

## 高级用法

### 多轮对话
```python
import asyncio
from sdk.python import UniversalAgentSDK

async def multi_turn_conversation():
    async with UniversalAgentSDK() as sdk:
        session_id = await sdk.create_session("multi-turn-user")

        conversation = [
            "我想建一个简单的计算器应用",
            "它需要支持加减乘除运算",
            "请给出Python代码实现",
            "如何添加错误处理？"
        ]

        for message in conversation:
            print(f"\n用户: {message}")

            response = await sdk.chat(session_id, message)
            print(f"Agent: {response['message']}")

            # 等待一下，模拟真实对话节奏
            await asyncio.sleep(1)

asyncio.run(multi_turn_conversation())
```

### 批量处理
```python
import asyncio
from sdk.python import UniversalAgentSDK

async def batch_processing():
    async with UniversalAgentSDK() as sdk:
        # 创建多个会话
        tasks = []
        for i in range(5):
            task = sdk.create_session(f"batch-user-{i}")
            tasks.append(task)

        session_ids = await asyncio.gather(*tasks)

        # 并发发送消息
        calculations = [
            "计算 2^10",
            "计算 100 的阶乘",
            "计算圆周率前10位",
            "计算斐波那契数列第20项",
            "计算 1 到 100 的和"
        ]

        async def process_calculation(session_id, expression):
            response = await sdk.chat(session_id, f"请计算：{expression}")
            return {
                "session_id": session_id,
                "expression": expression,
                "result": response['message']
            }

        # 并发处理所有计算
        results = await asyncio.gather(*[
            process_calculation(session_ids[i], calc)
            for i, calc in enumerate(calculations)
        ])

        # 显示结果
        for result in results:
            print(f"{result['expression']} = {result['result']}")

asyncio.run(batch_processing())
```

## 错误处理

### 网络错误处理
```python
import asyncio
from sdk.python import UniversalAgentSDK
from sdk.python.exceptions import ConnectionError, TimeoutError

async def error_handling_example():
    try:
        async with UniversalAgentSDK(timeout=10) as sdk:
            session_id = await sdk.create_session("error-test")

            # 尝试发送一个可能导致超时的复杂请求
            response = await sdk.chat(
                session_id,
                "请分析一篇10000字的文章摘要",  # 假设这是一个复杂请求
                timeout=30
            )

            print(f"成功响应: {response['message'][:100]}...")

    except TimeoutError:
        print("请求超时，请稍后重试")
    except ConnectionError:
        print("网络连接失败，请检查网络设置")
    except Exception as e:
        print(f"其他错误: {e}")

asyncio.run(error_handling_example())
```

### 重试机制
```python
import asyncio
from sdk.python import UniversalAgentSDK

async def retry_example():
    async with UniversalAgentSDK() as sdk:
        session_id = await sdk.create_session("retry-test")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await sdk.chat(session_id, "计算一个复杂的表达式")
                print(f"第{attempt+1}次尝试成功")
                break
            except Exception as e:
                print(f"第{attempt+1}次尝试失败: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    print("所有重试都失败了")

asyncio.run(retry_example())
```

## 自定义工具示例

### 扩展内置工具
```python
# 在config/agent.yaml中添加自定义工具
tools:
  - id: "weather"
    name: "weather"
    description: "获取天气信息"
    enabled: true
    handler:
      type: "http"
      url: "https://api.weatherapi.com/v1/current.json"
      method: "GET"
      params_mapping:
        city: "q"
      response_mapping:
        temperature: "current.temp_c"
        condition: "current.condition.text"
        city: "location.name"
      headers:
        key: "${WEATHER_API_KEY}"
```

### 使用自定义工具
```python
import asyncio
from sdk.python import UniversalAgentSDK

async def custom_tool_example():
    async with UniversalAgentSDK() as sdk:
        session_id = await sdk.create_session("weather-user")

        # 使用天气工具
        response = await sdk.chat(session_id, "北京今天的天气怎么样？")

        print(f"天气信息: {response['message']}")

        # 查看工具调用详情
        if response.get('tool_calls'):
            for tool_call in response['tool_calls']:
                if tool_call['name'] == 'weather':
                    print(f"查询城市: {tool_call['arguments'].get('city', '未知')}")

asyncio.run(custom_tool_example())
```

## 性能优化示例

### 连接池管理
```python
from sdk.python import UniversalAgentSDK, SDKConfig

# 配置连接池
config = SDKConfig(
    api_url="http://localhost:8080",
    timeout=30,
    max_keepalive_connections=10,
    max_connections=20
)

async def connection_pool_example():
    async with UniversalAgentSDK(config) as sdk:
        # SDK会自动管理连接池
        session_id = await sdk.create_session("pool-test")

        # 并发发送多个请求
        tasks = []
        for i in range(10):
            task = sdk.chat(session_id, f"计算 {i} + {i*2}")
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        print(f"成功处理 {len(results)} 个并发请求")

asyncio.run(connection_pool_example())
```

### 缓存策略
```python
# 对于频繁的计算结果，可以实现客户端缓存
import asyncio
from functools import lru_cache
from sdk.python import UniversalAgentSDK

@lru_cache(maxsize=100)
def cached_calculation(expression: str) -> str:
    # 这里可以实现缓存逻辑
    return f"缓存结果: {expression}"

async def caching_example():
    async with UniversalAgentSDK() as sdk:
        session_id = await sdk.create_session("cache-test")

        # 相同的计算会使用缓存
        expressions = ["1+1", "2+2", "1+1", "3+3", "1+1"]

        for expr in expressions:
            cached_result = cached_calculation(expr)
            print(f"缓存结果: {cached_result}")

            # 也可以发送给Agent进行验证
            response = await sdk.chat(session_id, f"验证计算: {expr}")
            print(f"Agent验证: {response['message']}")

asyncio.run(caching_example())
```

## 生产环境部署

### 配置监控
```python
from sdk.python import UniversalAgentSDK, SDKConfig

# 生产环境配置
config = SDKConfig(
    api_url="https://your-agent-api.com",
    timeout=60,
    retry_attempts=3,
    enable_metrics=True
)

async def production_example():
    async with UniversalAgentSDK(config) as sdk:
        # 生产环境的最佳实践
        session_id = await sdk.create_session("prod-user")

        try:
            response = await sdk.chat(session_id, "生产环境测试消息")
            print(f"生产环境响应: {response['message']}")
        except Exception as e:
            # 记录错误日志
            print(f"生产环境错误: {e}")
            # 发送告警通知
            # notify_admin(f"Agent服务异常: {e}")

asyncio.run(production_example())
```
