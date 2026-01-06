# 架构设计

Universal Agent 采用现代化的**微服务架构**设计，将不同职责分离到独立的微服务中，实现高可用性、可扩展性和可维护性。

## 整体架构

### 微服务架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              🎯 客户端层                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  🌐 Web Frontend / Mobile App / API Clients                           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ HTTP/HTTPS (REST + Streaming)
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           🏗️ API网关层 (Go)                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  🚪 zero-gateway (Go/Gin)                                            │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │ │
│  │  │  HTTP路由   │ │  会话管理   │ │   限流控    │ │   监控日    │      │ │
│  │  │ (Routing)   │ │ (Session)   │ │ (RateLimit) │ │ 志(Logging) │      │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │ │
│  │  │   SSE流     │ │  WebSocket  │ │   缓存     │ │   认证      │      │ │
│  │  │ (Streaming) │ │             │ │ (Caching)  │ │ (Auth)      │      │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ HTTP/GRPC (Internal API)
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           🤖 推理引擎层 (Python)                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  🧠 zero-agent (Python/FastAPI)                                       │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │ │
│  │  │  对话编排   │ │  状态管理   │ │  工具执行   │ │  LLM调用    │      │ │
│  │  │ (Orch)      │ │ (State)     │ │ (Tools)     │ │ (LLM)       │      │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │ │
│  │  │  流式推理   │ │ MCP协议     │ │  异步处理   │ │  错误处理   │      │ │
│  │  │ (Streaming) │ │ (MCP)       │ │ (Async)     │ │ (Error)     │      │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ External APIs
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           🔧 外部服务层                                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │  OpenAI     │ │ Anthropic   │ │ Ollama     │ │ MCP服务器   │ │ 其他API     │ │
│  │  API        │ │ API         │ │ API        │ │             │ │ (Tools)     │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 传统分层架构图 (每个服务内部)

#### Go网关服务内部架构
```
🏗️ zero-gateway (Go)
├── 🌐 接口层 (API Layer)
│   ├── HTTP路由处理
│   ├── 请求验证
│   ├── 响应格式化
│   └── 流式响应 (SSE/WebSocket)
├── 📊 会话层 (Session Layer)
│   ├── Redis会话存储
│   ├── 会话生命周期管理
│   └── 上下文缓存
├── 🛡️ 网关层 (Gateway Layer)
│   ├── 负载均衡
│   ├── 限流控制
│   ├── 请求转发
│   └── 熔断降级
└── 📈 监控层 (Monitoring Layer)
    ├── 指标收集
    ├── 日志记录
    └── 健康检查
```

#### Python推理服务内部架构
```
🤖 zero-agent (Python)
├── 🎯 核心层 (Core Layer)
│   └── UniversalAgent接口
├── 🎭 编排层 (Orchestration Layer)
│   ├── 状态管理 (State)
│   ├── 工作流 (Workflow)
│   └── 编排Agent (Agent)
├── 🔧 工具层 (Tools Layer)
│   ├── 工具接口 (Base)
│   ├── 注册器 (Registry)
│   └── 执行器 (Executor)
├── 🧠 LLM层 (LLM Layer)
│   ├── 基础接口 (Base)
│   ├── 工厂 (Factory)
│   └── 提供商 (Providers)
└── ⚙️ 配置层 (Config Layer)
    └── 配置管理 (Settings)
```

## 架构设计原则

### 1. 单一职责原则 (SRP)
每个层级只负责一个明确的功能：
- **LLM层**: 专门处理LLM提供商集成
- **工具层**: 专注工具管理
- **编排层**: 负责对话流程控制
- **核心层**: 提供统一接口
- **接口层**: 处理外部请求

### 2. 依赖倒置原则 (DIP)
高层模块不依赖低层模块，通过接口进行交互：
- 编排层依赖抽象的工具接口
- 核心层依赖抽象的编排接口
- 接口层依赖抽象的核心接口

### 3. 开闭原则 (OCP)
对扩展开放，对修改封闭：
- 新增LLM提供商无需修改现有代码
- 添加新工具不需要更改核心逻辑
- 扩展API接口不影响业务逻辑

### 4. 接口隔离原则 (ISP)
客户端不依赖不需要的接口：
- 每个层级只暴露必要的接口
- 依赖最小化原则
- 避免接口污染

## 数据流

### 完整请求处理流程 (服务分离架构)

```
🌐 客户端请求
    ↓ HTTP/HTTPS
🏗️ Go网关 (zero-gateway)
    ↓ (路由 + 会话管理)
    ├─► 缓存检查 (Redis)
    ├─► 限流控制 (Rate Limiting)
    ├─► 请求验证 (Validation)
    ↓
🤖 Python推理服务 (zero-agent)
    ↓ (内部API调用)
🎯 核心层 (UniversalAgent)
    ↓ (业务编排)
🎭 编排层 (OrchestratorAgent)
    ↓ (状态管理 - LangGraph)
🧠 LLM层 (LLM Provider)
    ↙ (工具调用)
🔧 工具层 (Tool Executor)
    ├─► MCP服务器调用
    ├─► 内置工具执行
    └─► 外部API调用
    ↓ (结果返回)
🎭 编排层 (状态更新)
    ↓
🎯 核心层 (响应格式化)
    ↓
🤖 Python推理服务响应
    ↓ HTTP/GRPC
🏗️ Go网关 (响应处理)
    ├─► 会话状态更新 (Redis)
    ├─► 响应缓存
    └─► 监控指标记录
    ↓
🌐 客户端响应
```

### 流式输出数据流

#### 传统响应流程
```
Client Request → Go网关 → Python Agent → LLM推理 → 完整响应 → 网关 → Client
```

#### 流式响应流程
```
Client Request → Go网关 → Python Agent → LLM流式推理 → 流式数据块 → 网关SSE → Client
                      │                       │                        │
                      ├─ 建立流式连接        ├─ 实时生成内容          ├─ 实时推送SSE
                      ├─ 设置超时控制        ├─ 工具调用流            ├─ 心跳保活
                      └─ 错误处理重试        └─ 状态流更新            └─ 连接管理
```

### 工具调用流程 (支持流式)

```
对话进行中...
    ↓
🎭 编排层检测工具调用需求
    ↓ [流式输出: tool_call_start]
🔧 工具层查找工具
    ↓
🔧 工具层执行工具
    ├─► 同步工具 (立即返回)
    ├─► 异步工具 (流式返回)
    └─► MCP工具 (协议调用)
    ↓ [流式输出: tool_call_end + 结果]
🎭 编排层更新状态
    ↓
🧠 LLM层继续流式生成响应
    ↓ [流式输出: content chunks]
🎯 核心层格式化最终响应
    ↓ [流式输出: done]
```

## 层级详细说明

### 🏗️ API网关层 (Go网关服务)

**服务位置**: `zero-gateway/`

**核心职责**:
- HTTP/HTTPS API接口管理
- 会话状态管理 (Redis)
- 请求路由和负载均衡
- 流式响应处理 (SSE/WebSocket)
- 安全认证和授权
- 请求限流和熔断
- 监控和日志记录

**关键特性**:
- **双流式支持**: 同时支持传统HTTP响应和流式SSE响应
- **会话一致性**: 维护跨请求的会话状态
- **高可用性**: 支持多实例部署和负载均衡
- **容错机制**: 重试、熔断、降级策略

**技术栈**: Go + Gin + Redis + Zap

---

### 🤖 推理引擎层 (Python推理服务)

**服务位置**: `zero-agent/`

**核心职责**:
- AI模型推理和对话生成
- 工具调用编排和执行
- 对话状态管理
- 流式推理处理
- MCP协议支持

#### 🧠 LLM层 (LLM Layer)

**职责范围**:
- 统一LLM提供商接口 (支持流式调用)
- 管理不同的AI服务集成
- 处理API认证和错误重试
- 提供同步和异步调用接口

**组件**:
- `LLMProvider`: 抽象基类，定义标准接口 (新增流式方法)
- `LLMFactory`: 工厂模式，创建具体提供商实例
- `OpenAIProvider`: OpenAI服务集成 (支持流式)
- `AnthropicProvider`: Anthropic服务集成 (支持流式)
- `SiliconFlowProvider`: SiliconFlow服务集成 (支持流式)

**流式特性**:
- `stream_chat()`: 基础流式对话接口
- `stream_chat_with_tools()`: 带工具的流式对话
- 支持内容流、工具调用流、状态流

#### 🔧 工具层 (Tools Layer)

**职责范围**:
- 工具注册和发现
- 工具实例管理和生命周期
- 工具执行和结果处理 (支持流式执行)
- 工具权限和安全控制
- MCP协议工具集成

**组件**:
- `Tool`: 工具抽象基类
- `ToolRegistry`: 工具注册中心
- `ToolExecutor`: 工具执行器 (支持异步执行)
- `CalculatorTool`: 内置计算器工具
- `MCPClient`: MCP协议客户端
- `MCPTool`: MCP工具适配器

**流式特性**:
- 异步工具执行支持
- 工具调用流式事件
- MCP工具的协议级流式支持

#### 🎭 编排层 (Orchestration Layer)

**职责范围**:
- 对话状态管理 (支持流式状态更新)
- 工作流编排和执行 (支持流式工作流)
- 工具调用协调 (支持流式工具调用)
- 错误处理和重试
- 对话上下文维护

**组件**:
- `AgentState`: LangGraph状态定义 (扩展流式字段)
- `WorkflowManager`: 基于LangGraph的工作流管理器 (新增流式执行)
- `OrchestratorAgent`: 编排Agent核心逻辑 (支持流式推理)

**流式特性**:
- `execute_stream()`: 流式工作流执行
- 状态实时更新机制
- 工具调用流式事件处理
- 对话上下文流式维护

### 🎯 核心层 (Core Layer)

**职责范围**:
- 提供统一的外部接口
- 协调各层级组件
- 处理跨层级的业务逻辑
- 保证API稳定性

**组件**:
- `UniversalAgent`: 统一接口类

**设计模式**:
- **外观模式**: 简化复杂子系统的接口
- **适配器模式**: 适配不同层级的接口
- **桥接模式**: 解耦抽象和实现

### 🌐 接口层 (API Layer)

**职责范围**:
- HTTP请求处理和路由
- 请求验证和序列化
- 响应格式化和错误处理
- API文档自动生成

**组件**:
- FastAPI应用
- 请求/响应模型
- 中间件和异常处理器

**设计模式**:
- **控制器模式**: 处理HTTP请求分发
- **管道模式**: 请求处理管道
- **装饰器模式**: 路由和中间件装饰

### ⚙️ 配置层 (Config Layer)

**职责范围**:
- 配置文件的加载和解析
- 配置验证和类型检查
- 环境变量管理
- 配置热重载支持

**组件**:
- `Settings`: 配置管理类
- YAML/JSON配置解析器
- 环境变量处理器

## 通信机制

### 客户端 ↔ 网关层通信

#### 同步通信 (REST API)
```http
POST /api/v1/chat HTTP/1.1
Content-Type: application/json

{
  "session_id": "sess_123",
  "message": "Hello",
  "stream": false
}
```

#### 流式通信 (SSE/WebSocket)
```http
POST /api/v1/chat/stream HTTP/1.1
Content-Type: application/json
Accept: text/event-stream

{
  "session_id": "sess_123",
  "message": "Hello",
  "stream": true
}

# 响应格式
data: {"type": "content", "content": "Hello", "done": false}
data: {"type": "content", "content": " there!", "done": false}
data: {"type": "done", "done": true}
```

### 网关层 ↔ 推理层通信

#### 同步调用 (HTTP)
```http
POST /chat HTTP/1.1
Host: zero-agent:8000
Content-Type: application/json

{
  "message": "Hello",
  "message_history": [...],
  "metadata": {...}
}
```

#### 流式调用 (HTTP Streaming)
```http
POST /chat/stream HTTP/1.1
Host: zero-agent:8000
Content-Type: application/json
Accept: application/json-seq  # 或 text/plain

# 请求体
{
  "message": "Hello",
  "stream": true
}

# 响应流
{"type": "content", "content": "Hel"}
{"type": "content", "content": "lo "}
{"type": "tool_call_start", "tool_call": {...}}
{"type": "tool_call_end", "result": "..."}
{"type": "done", "done": true}
```

### 推理层 ↔ 外部服务通信

#### LLM API调用
- **OpenAI/Anthropic**: REST API + Streaming
- **SiliconFlow**: REST API + Streaming
- **Ollama**: Local HTTP API

#### MCP协议通信
```json
// MCP Initialize
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {...},
    "clientInfo": {...}
  }
}

// MCP Tool Call
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {"location": "Beijing"}
  }
}
```

### 异步通信机制

#### 内部服务通信
- **asyncio协程**: Python服务内部异步处理
- **Goroutine**: Go服务内部并发处理
- **Channel**: Go内部数据流转

#### 外部集成通信
- **Webhook**: 外部服务回调
- **Message Queue**: 异步任务处理
- **Event Streaming**: 实时事件流

### 协议栈对比

| 通信场景 | 协议 | 优势 | 适用场景 |
|---------|------|------|----------|
| 客户端→网关 | HTTP/1.1 | 通用性强 | 所有API调用 |
| 客户端→网关 | HTTP/2 | 多路复用 | 高并发场景 |
| 客户端→网关 | WebSocket | 双向通信 | 实时交互 |
| 网关→推理 | HTTP/1.1 | 简单可靠 | 同步调用 |
| 网关→推理 | HTTP/2 | 性能更好 | 流式调用 |
| 推理→外部 | REST API | 标准协议 | LLM调用 |
| 推理→外部 | MCP | 工具集成 | MCP服务器 |
| 推理→外部 | gRPC | 高性能 | 内部服务 |

## 扩展点

### LLM提供商扩展 (支持流式)
```python
from llm.base import LLMProvider
from typing import AsyncIterator, Dict, Any
from langchain_core.messages import BaseMessage

class CustomProvider(LLMProvider):
    def create_llm(self):
        return CustomLLM(api_key=self.api_key)

    async def stream_chat(self, messages: list[BaseMessage], **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """实现流式对话"""
        llm = CustomLLM(api_key=self.api_key, streaming=True)

        async for chunk in llm.astream(messages):
            if chunk.content:
                yield {
                    "type": "content",
                    "content": chunk.content,
                    "done": False
                }
            # 支持工具调用流
            if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                for tool_call in chunk.tool_calls:
                    yield {
                        "type": "tool_call_start",
                        "tool_call": tool_call,
                        "done": False
                    }

# 注册新提供商
from llm.factory import LLMFactory
LLMFactory.register_provider("custom", CustomProvider)
```

### 工具扩展 (支持流式执行)
```python
from tools.base import Tool
from typing import AsyncIterator, Dict, Any

class CustomTool(Tool):
    def __init__(self):
        super().__init__("custom", "自定义工具")

    async def execute(self, **kwargs) -> Any:
        # 同步执行
        return "自定义结果"

    async def execute_stream(self, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """流式执行 (可选)"""
        yield {"type": "progress", "message": "开始执行..."}
        # 执行逻辑
        result = await self._do_work(**kwargs)
        yield {"type": "result", "data": result}
        yield {"type": "done", "completed": True}

# 注册工具
from tools.registry import ToolRegistry
registry = ToolRegistry()
registry.register(CustomTool())
```

### API网关扩展 (Go)
```go
// 新增流式端点
func (h *Handler) ChatStream(c *gin.Context) {
    // 流式处理逻辑
    // 1. 验证请求
    // 2. 调用Python Agent流式接口
    // 3. 转发SSE响应
}

// 新增WebSocket端点
func (h *Handler) ChatWebSocket(c *gin.Context) {
    // WebSocket处理逻辑
    // 1. 升级连接
    // 2. 双向通信
    // 3. 流式数据交换
}
```

### 推理服务扩展 (Python)
```python
# 新增流式推理接口
@app.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """流式对话端点"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not available")

    async def generate():
        async for chunk in agent.chat_with_history_stream(request):
            # SSE格式输出
            data = f"data: {json.dumps(chunk.model_dump())}\n\n"
            yield data.encode('utf-8')
        yield "data: [DONE]\n\n".encode('utf-8')

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache"}
    )
```

### MCP工具扩展
```python
# MCP服务器配置
mcp_config = MCPConfig(
    id="weather-server",
    name="Weather Service",
    command="python",
    args=["-m", "weather_server"],
    tools=[MCPToolConfig(
        server_id="weather-server",
        tool_name="get_weather",
        enabled=True
    )]
)

# 自动集成到工作流
agent_config = AgentConfig(
    # ... 其他配置
    mcp_servers=[mcp_config],
    mcp_tools=[tool_config]
)
```

### 流式响应处理器扩展
```python
class CustomStreamProcessor:
    """自定义流式响应处理器"""

    async def process_chunk(self, chunk: StreamChunk) -> StreamChunk:
        """处理单个数据块"""
        if chunk.type == "content":
            # 内容过滤/修改
            chunk.content = self._filter_content(chunk.content)
        elif chunk.type == "tool_call_start":
            # 工具调用监控
            self._log_tool_call(chunk.tool_call)
        return chunk

    async def process_stream(self, stream: AsyncIterator[StreamChunk]) -> AsyncIterator[StreamChunk]:
        """处理完整流"""
        async for chunk in stream:
            processed = await self.process_chunk(chunk)
            yield processed
```

## 性能优化

### 缓存策略 (多层缓存)

#### 网关层缓存
- **会话缓存**: Redis存储用户会话上下文
- **响应缓存**: 短期缓存常用查询结果
- **配置缓存**: API配置和路由规则缓存

#### 推理层缓存
- **LLM响应缓存**: 相似查询的结果缓存
- **工具执行缓存**: 确定性工具调用的结果缓存
- **向量缓存**: 嵌入向量的本地缓存

#### 流式缓存优化
- **流状态缓存**: 流式会话的中间状态缓存
- **断点续传**: 支持流式传输的中断恢复

### 连接池管理

#### 网关层连接池
```go
// HTTP客户端连接池配置
transport := &http.Transport{
    MaxIdleConns:        100,
    MaxIdleConnsPerHost: 10,
    IdleConnTimeout:     90 * time.Second,
}
```

#### 推理层连接池
- **LLM API连接池**: 复用外部API连接
- **MCP连接池**: 维护与MCP服务器的长连接
- **数据库连接池**: 状态存储的连接管理

### 异步处理优化

#### 并发架构
```
请求处理流程:
Client → 网关Goroutine → Agent协程池 → LLM并发调用
    ↓         ↓              ↓            ↓
   SSE      流式转发       状态管理     工具并行执行
```

#### 流式处理优化
- **响应分块**: 将大响应分割为小数据块
- **管道处理**: 多级流式处理管道
- **背压控制**: 防止下游处理过载
- **内存管理**: 流式数据的内存池管理

### 性能指标

#### 响应时间指标
- **TTFB** (Time To First Byte): 首字节响应时间
- **TP50/95/99**: 分位数响应时间
- **流式延迟**: 流式数据块间延迟

#### 吞吐量指标
- **QPS**: 每秒查询数
- **并发连接数**: 同时处理的流式连接数
- **带宽使用**: 流式数据传输带宽

#### 资源利用率
- **CPU使用率**: 推理和编排的计算资源
- **内存使用率**: 状态管理和缓存的内存占用
- **网络I/O**: 内外网络通信的I/O负载

## 监控和可观测性

### 指标收集体系

#### 业务指标
- **请求量**: 总请求数、流式请求数、同步请求数
- **成功率**: API成功率、流式完成率
- **响应时间**: 平均响应时间、P95/P99响应时间
- **会话指标**: 活跃会话数、会话持续时间

#### 性能指标
- **LLM指标**: Token使用量、推理时间、API调用延迟
- **工具指标**: 工具调用次数、执行时间、成功率
- **流式指标**: 连接数、数据块大小、传输延迟

#### 系统指标
- **资源使用**: CPU、内存、磁盘、网络I/O
- **连接池**: 连接数、使用率、错误数
- **缓存指标**: 命中率、存储大小、过期清理

### 日志记录架构

#### 结构化日志
```json
{
  "timestamp": "2024-01-04T12:00:00Z",
  "level": "INFO",
  "service": "zero-gateway",
  "request_id": "req_12345",
  "session_id": "sess_67890",
  "user_id": "user_111",
  "operation": "chat_stream",
  "duration_ms": 2500,
  "stream_chunks": 15,
  "tool_calls": 2,
  "tokens_used": 450,
  "status": "success"
}
```

#### 日志级别分层
- **DEBUG**: 详细的调试信息，包含流式数据块内容
- **INFO**: 关键业务事件，会话创建、工具调用等
- **WARN**: 异常情况，可自动恢复的错误
- **ERROR**: 需要人工干预的错误

#### 分布式追踪
```
Client Request (req_123)
├── Go网关处理 (gateway_001)
│   ├── 会话验证 (redis_check)
│   ├── 请求转发 (http_call)
│   └── 响应处理 (stream_forward)
└── Python推理 (agent_002)
    ├── 状态初始化 (state_init)
    ├── LLM推理 (llm_call)
    │   ├── 内容生成 (content_gen)
    │   └── 工具调用 (tool_call)
    └── 结果返回 (response_build)
```

### 健康检查体系

#### 网关层健康检查
```go
// /health 端点
{
  "status": "healthy",
  "service": "zero-gateway",
  "version": "1.0.0",
  "checks": {
    "redis": "healthy",
    "python_agent": "healthy",
    "database": "healthy"
  },
  "metrics": {
    "active_connections": 150,
    "requests_per_second": 25.5,
    "memory_usage_mb": 256
  }
}
```

#### 推理层健康检查
```python
# /health 端点
{
  "status": "healthy",
  "service": "zero-agent",
  "llm_providers": {
    "openai": "healthy",
    "anthropic": "healthy"
  },
  "tool_registry": {
    "total_tools": 15,
    "active_tools": 12
  },
  "performance": {
    "avg_response_time": 2.3,
    "active_sessions": 45
  }
}
```

#### 流式健康检查
- **连接健康**: WebSocket/SSE连接状态监控
- **流式延迟**: 数据块传输延迟监控
- **断开率**: 异常断开连接的比例

### 可观测性仪表盘

#### 实时监控面板
- **流量监控**: 请求量、错误率、响应时间趋势
- **流式性能**: 并发连接数、数据传输速率
- **资源使用**: CPU/内存使用率、服务实例状态

#### 业务洞察面板
- **用户行为**: 会话长度、工具使用频率
- **AI性能**: Token消耗、推理质量指标
- **系统效率**: 缓存命中率、连接池利用率

#### 告警规则
- **性能告警**: 响应时间超过阈值、错误率上升
- **容量告警**: 连接数接近上限、资源使用率过高
- **业务告警**: 关键功能不可用、数据异常

## 安全考虑

### API安全 (网关层)

#### 身份认证和授权
- **JWT Token**: 无状态身份验证
- **API Key**: 服务级别的访问控制
- **OAuth 2.0**: 第三方应用集成
- **会话管理**: Redis存储的安全会话

#### 请求安全
- **输入验证**: 严格的请求参数验证
- **XSS防护**: HTML内容转义和过滤
- **SQL注入防护**: 参数化查询和预编译
- **速率限制**: 基于用户的请求频率控制

#### 传输安全
- **TLS 1.3**: 端到端加密通信
- **证书管理**: 自动证书轮换和验证
- **HSTS**: 强制HTTPS访问

### 数据安全

#### 存储安全
- **数据加密**: 敏感数据的AES256加密存储
- **密钥管理**: HSM或云密钥管理服务
- **访问控制**: 最小权限原则的数据库访问

#### 传输安全
- **端到端加密**: 客户端到服务的完整加密
- **证书固定**: 防止中间人攻击
- **完美前向保密**: DH密钥交换

#### 审计安全
- **操作日志**: 所有敏感操作的详细审计
- **不可变日志**: 防止日志篡改
- **合规记录**: GDPR、SOX等合规要求

### 工具安全 (推理层)

#### 执行安全
- **沙箱执行**: 工具在隔离环境中运行
- **资源限制**: CPU时间、内存、磁盘I/O限制
- **网络隔离**: 工具网络访问的白名单控制

#### 权限控制
- **工具授权**: 基于角色的工具访问控制
- **参数验证**: 工具参数的安全验证和清理
- **结果过滤**: 工具输出的安全过滤

### 流式输出安全

#### 实时安全监控
- **内容过滤**: 流式内容的实时安全检查
- **速率控制**: 防止流式数据洪水攻击
- **连接管理**: 异常连接的自动断开和清理

#### 隐私保护
- **数据脱敏**: 流式响应中的敏感信息处理
- **会话隔离**: 用户数据的严格隔离
- **审计追踪**: 流式会话的完整审计记录

### 基础设施安全

#### 网络安全
- **防火墙**: 多层网络访问控制
- **入侵检测**: 实时安全威胁监控
- **DDoS防护**: 分布式拒绝服务攻击防护

#### 容器安全
- **镜像扫描**: 容器镜像的漏洞扫描
- **运行时保护**: 容器运行时的安全监控
- **最小权限**: 容器的最小权限运行

#### 云安全 (如果适用)
- **IAM角色**: 云资源的精细化权限控制
- **VPC隔离**: 网络层面的服务隔离
- **加密存储**: 云存储的数据加密

### 安全监控和响应

#### 安全事件监控
- **实时告警**: 安全事件的即时通知
- **威胁情报**: 外部威胁情报的集成
- **异常检测**: 基于AI的异常行为检测

#### 应急响应
- **事件响应**: 标准的安全事件处理流程
- **备份恢复**: 数据和系统的备份恢复策略
- **灾难恢复**: 重大安全事件的恢复计划

## 部署架构

### 单机部署 (开发环境)
```
┌─────────────────────────────────────┐
│         Universal Agent             │
│  ┌─────────┐ ┌─────────┐            │
│  │ Go网关  │ │Python推理│            │
│  │(Gateway)│ │ (Agent)  │            │
│  │  :8080  │ │  :8000   │            │
│  └─────────┘ └─────────┘            │
│           │         │               │
│           └─────────┘               │
│             HTTP调用                │
└─────────────────────────────────────┘
```

### 分布式部署 (生产环境)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   API Gateway   │    │   Monitoring    │
│   (Nginx/Envoy) │    │   (Kong/APISIX) │    │   (Prometheus)   │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                        │                   │
          ├────────────────────────┼───────────────────┤
          │                        │                   │
┌─────────────────┐       ┌─────────────────┐    ┌─────────────────┐
│   Go网关集群    │◄─────►│   Redis集群     │    │   ELK Stack     │
│ (zero-gateway) │       │   (Session)     │    │   (Logging)     │
│                 │       │                 │    │                 │
│  ┌─────────┐    │       └─────────────────┘    └─────────────────┘
│  │ SSE流   │    │                │
│  │处理     │    │                │
│  └─────────┘    │                │
└─────────────────┘                │
          │                        │
          ▼                        ▼
┌─────────────────┐       ┌─────────────────┐    ┌─────────────────┐
│ Python推理集群  │◄─────►│   状态存储      │    │   LLM APIs      │
│ (zero-agent)   │       │   (SQLite/      │    │   (OpenAI/       │
│                 │       │    Redis)       │    │    Anthropic)    │
│  ┌─────────┐    │       └─────────────────┘    └─────────────────┘
│  │ 流式推 │    │                │
│  │ 理引擎  │    │                │
│  └─────────┘    │                │
└─────────────────┘                │
          │                        │
          ▼                        ▼
┌─────────────────┐       ┌─────────────────┐    ┌─────────────────┐
│   工具服务      │◄─────►│   MCP服务器     │    │   外部工具      │
│   (Tools)       │       │   (MCP)         │    │   (APIs)         │
└─────────────────┘       └─────────────────┘    └─────────────────┘
```

### 云原生部署 (Kubernetes)
```
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │  Ingress    │ │  Service    │ │  ConfigMap │ │  Secret     │ │
│  │  Controller │ │  Mesh       │ │             │ │  Management│ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │ nexus-gate │ │ zero-agent │ │  Redis      │ │  Prometheus │ │
│  │ way Deploy │ │ Deploy      │ │  StatefulSet│ │  Deploy     │ │
│  │ (3 replicas)│ │ (5 replicas)│ │             │ │             │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │  HPA        │ │  VPA        │ │  Network   │ │  Storage    │ │
│  │  (Auto      │ │  (Resource  │ │  Policies  │ │  Classes    │ │
│  │   Scale)    │ │   Mgmt)     │ │             │ │             │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 服务通信架构

```
🌐 客户端
    ↓ HTTPS/WSS (公网)
┌─────────────────────────────────────┐
│         🔒 API Gateway              │
│  ┌─────────────┐ ┌─────────────┐    │
│  │   HTTPS     │ │   WSS       │    │
│  │  (REST)     │ │ (Streaming) │    │
│  └─────────────┘ └─────────────┘    │
└─────────────────────────────────────┘
    ↓ HTTP/GRPC (内网)
┌─────────────────────────────────────┐
│         🤖 Inference Engine         │
│  ┌─────────────┐ ┌─────────────┐    │
│  │   HTTP      │ │   GRPC      │    │
│  │  (Sync)     │ │  (Stream)   │    │
│  └─────────────┘ └─────────────┘    │
└─────────────────────────────────────┘
    ↓ HTTPS (外网)
┌─────────────────────────────────────┐
│         🔧 External Services        │
│  ┌─────────────┐ ┌─────────────┐    │
│  │   LLM APIs  │ │ MCP Servers │    │
│  └─────────────┘ └─────────────┘    │
└─────────────────────────────────────┘
```

这个分层架构设计为Universal Agent提供了坚实的技术基础，支持未来的扩展和演进。
