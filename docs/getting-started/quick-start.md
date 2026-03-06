# 快速开始

## 启动服务

### 开发环境运行

#### 0. 进入项目目录
```bash
cd prodject  # 重要：所有命令都需在项目根目录运行
```

#### 1. 激活虚拟环境
```bash
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows
```

#### 2. 启动服务（开发环境）
```bash
# 方式1: 使用模块启动
python -m scripts.start

# 方式2: 使用Makefile
make run
```

#### 3. 验证服务运行
```bash
# 检查服务状态
curl http://localhost:8080/health

# 访问API文档
open http://localhost:8080/docs  # 或浏览器打开
```

### 生产环境部署

#### 使用Docker Compose
```bash
# 启动服务
docker-compose -f docker/docker-compose.yml up --build

# 后台运行
docker-compose -f docker/docker-compose.yml up -d --build

# 查看日志
docker-compose logs -f agent

# 停止服务
docker-compose down
```

#### 使用纯Docker
```bash
# 构建镜像
docker build -f docker/Dockerfile -t zero-agent .

# 运行容器
docker run -p 8080:8080 \
  -e SILICONFLOW_API_KEY="your-api-key" \
  --name agent-container \
  zero-agent

# 查看日志
docker logs agent-container
```

## 验证安装

### 健康检查
```bash
# API健康检查
curl http://localhost:8080/health

# 期望响应
{
  "status": "healthy",
  "agent_id": "demo-agent",
  "tools_count": 1,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 工具检查
```bash
# 查看可用工具
curl http://localhost:8080/tools

# 期望响应
{
  "tools": [
    {
      "id": "calculator",
      "name": "calculator",
      "description": "数学计算器，支持四则运算，如 '1 + 2 * 3'",
      "parameters": {}
    }
  ]
}
```

## 基本使用

### 创建会话
```bash
# 创建新会话
curl -X POST http://localhost:8080/sessions \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"user": "demo"}}'

# 响应示例
{
  "session_id": "sess_abc123",
  "created_at": "2024-01-01T00:00:00Z",
  "metadata": {"user": "demo"}
}
```

### 发送消息
```bash
# 发送对话消息
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_abc123",
    "message": "计算 15 + 27 的结果",
    "metadata": {}
  }'

# 响应示例
{
  "message": "15 + 27 = 42",
  "tool_calls": [
    {
      "id": "call_123",
      "name": "calculator",
      "arguments": {"expression": "15 + 27"}
    }
  ],
  "processing_time": 1.23
}
```

## 演示脚本

### 运行完整演示
```bash
# 运行演示脚本
python demo.py

# 或者使用uvicorn重载模式下的演示
python -c "
import asyncio
from sdk.python import UniversalAgentSDK

async def demo():
    async with UniversalAgentSDK() as sdk:
        # 创建会话
        session_id = await sdk.create_session('demo-user')

        # 发送消息
        response = await sdk.chat(session_id, '计算 123 * 456')
        print(f'Agent: {response[\"message\"]}')

asyncio.run(demo())
"
```

### 交互式测试
```bash
# 进入Python交互环境
python -c "
import asyncio
from sdk.python import UniversalAgentSDK

async def interactive_demo():
    async with UniversalAgentSDK() as sdk:
        session_id = await sdk.create_session('interactive')

        while True:
            msg = input('You: ')
            if msg.lower() in ['quit', 'exit']:
                break

            response = await sdk.chat(session_id, msg)
            print(f'Agent: {response[\"message\"]}')

            if response.get('tool_calls'):
                print('Tools used:')
                for tool in response['tool_calls']:
                    print(f'  - {tool[\"name\"]}')

asyncio.run(interactive_demo())
"
```

## 常用命令

### 开发环境服务管理
```bash
# 查看服务状态
ps aux | grep python
lsof -i :8080

# 重启服务
pkill -f "python -m scripts.start"
python -m scripts.start

# 查看日志
tail -f logs/agent.log
```

### Docker管理
```bash
# 查看运行中的容器
docker ps

# 进入容器
docker exec -it zero-agent bash

# 查看容器日志
docker logs -f zero-agent

# 清理容器
docker stop zero-agent
docker rm zero-agent
```

### 开发环境调试
```bash
# 启用调试日志
export LOG_LEVEL=DEBUG
python -m scripts.start

# 使用调试工具
python -c "
import pdb
import asyncio
from core import UniversalAgent

# 设置断点调试
asyncio.run(debug_function())
"
```

## 性能监控

### 基本监控
```bash
# 监控请求
watch -n 1 "curl -s http://localhost:8080/health | jq ."

# 监控系统资源
top -p $(pgrep -f "python -m scripts.start")

# 监控网络连接
netstat -tlnp | grep :8080
```

### 日志分析
```bash
# 查看错误日志
grep ERROR logs/agent.log | tail -10

# 统计请求数量
grep "Processing chat request" logs/agent.log | wc -l

# 分析响应时间
grep "processing_time" logs/agent.log | \
  sed 's/.*processing_time": \([0-9.]*\).*/\1/' | \
  awk '{sum+=$1; count++} END {print "平均响应时间:", sum/count, "秒"}'
```

## 故障排除

### 服务无法启动
```bash
# 检查端口占用
lsof -i :8080

# 检查环境变量
python -c "import os; print([k for k in os.environ.keys() if 'API' in k])"

# 检查依赖
python -c "import fastapi, langchain, langgraph; print('依赖正常')"
```

### API调用失败
```bash
# 测试基本连接
curl -v http://localhost:8080/health

# 检查API密钥
curl -H "Authorization: Bearer test" http://localhost:8080/health

# 查看详细错误
python -c "
import requests
try:
    r = requests.get('http://localhost:8080/health')
    print(f'状态码: {r.status_code}')
    print(f'响应: {r.text}')
except Exception as e:
    print(f'错误: {e}')
"
```

### LLM连接问题
```bash
# 测试LLM API
python -c "
from llm.factory import LLMFactory
import os

key = os.getenv('SILICONFLOW_API_KEY')
if key:
    llm = LLMFactory.create_llm('siliconflow', key, 'deepseek-ai/DeepSeek-V2.5')
    print('LLM初始化成功')
else:
    print('未找到API密钥')
"
```

## 下一步

服务启动成功后，你可以：
- 查看[使用示例](examples.md)了解更多功能
- 阅读[API文档](../api/reference.md)了解完整接口
- 学习[开发指南](../development/guide.md)进行定制开发
