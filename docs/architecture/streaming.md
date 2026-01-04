# 流式输出架构设计

## 概述

Universal Agent 支持完整的流式输出能力，在服务分离架构下实现高效的实时AI对话体验。本文档详细说明流式输出的设计原则、实现架构和技术细节。

## 核心设计原则

### 1. 双层流式架构
```
客户端 ←───── HTTP流式 ─────→ Go网关 ←───── 内部流式 ─────→ Python推理服务
   ↑                                ↑                                ↑
   │                          SSE/WebSocket                   LLM流式推理
   │                       响应格式化 & 转发               内容+工具调用流
   │                    缓存 & 会话管理                   状态管理 & 编排
```

### 2. 渐进式增强
- **向后兼容**: 现有同步API保持不变
- **可选流式**: 客户端可选择同步或流式模式
- **平滑降级**: 流式失败时自动降级到同步模式

### 3. 性能优先
- **低延迟**: 优化首字节响应时间(TTFB)
- **高吞吐**: 支持大量并发流式连接
- **资源控制**: 智能的背压和资源管理

## 架构组件

### 客户端层

#### 支持的协议
- **SSE (Server-Sent Events)**: 推荐，用于简单流式场景
- **WebSocket**: 用于复杂双向交互场景
- **HTTP/2 Streaming**: 用于高性能场景

#### 客户端实现示例
```javascript
// SSE客户端
const eventSource = new EventSource('/api/v1/chat/stream');
eventSource.onmessage = (event) => {
  const chunk = JSON.parse(event.data);
  handleStreamChunk(chunk);
};

// WebSocket客户端
const ws = new WebSocket('ws://localhost:8080/ws/chat');
ws.onmessage = (event) => {
  const chunk = JSON.parse(event.data);
  handleStreamChunk(chunk);
};
```

### 网关层 (Go)

#### 核心职责
- **协议转换**: HTTP请求 ↔ 内部流式协议
- **连接管理**: 维护大量并发流式连接
- **负载均衡**: 智能分发到不同的推理实例
- **安全过滤**: 流式内容的实时安全检查

#### 流式端点设计
```go
// SSE流式端点
func (h *Handler) ChatStreamSSE(c *gin.Context) {
    // 1. 设置SSE响应头
    c.Header("Content-Type", "text/event-stream")
    c.Header("Cache-Control", "no-cache")
    c.Header("Connection", "keep-alive")

    // 2. 调用Python Agent流式接口
    streamReader, err := h.callPythonAgentStream(request)
    if err != nil {
        c.SSEvent("error", err.Error())
        return
    }

    // 3. 转发流式数据
    for {
        chunk, err := streamReader.ReadChunk()
        if err != nil {
            break
        }

        c.SSEvent("chunk", chunk.ToJSON())
        c.Writer.Flush()
    }

    c.SSEvent("done", "{}")
}

// WebSocket流式端点
func (h *Handler) ChatStreamWS(c *gin.Context) {
    ws, err := upgrader.Upgrade(c.Writer, c.Request, nil)
    if err != nil {
        return
    }
    defer ws.Close()

    // 双向流式通信
    for {
        // 接收客户端消息
        _, message, err := ws.ReadMessage()
        if err != nil {
            break
        }

        // 处理消息并流式响应
        responseStream := h.processWebSocketMessage(message)
        for chunk := range responseStream {
            ws.WriteJSON(chunk)
        }
    }
}
```

### 推理层 (Python)

#### 流式推理引擎
```python
class StreamingInferenceEngine:
    """流式推理引擎"""

    async def stream_chat(
        self,
        messages: List[BaseMessage],
        config: StreamingConfig
    ) -> AsyncIterator[StreamChunk]:
        """流式对话推理"""

        # 1. 准备LLM流式调用
        llm_stream = await self._prepare_llm_stream(messages, config)

        # 2. 流式生成内容
        async for llm_chunk in llm_stream:
            if llm_chunk.content:
                yield StreamChunk(
                    type="content",
                    content=llm_chunk.content,
                    done=False
                )

            # 3. 处理工具调用
            if llm_chunk.tool_calls:
                for tool_call in llm_chunk.tool_calls:
                    # 流式输出工具调用开始
                    yield StreamChunk(
                        type="tool_call_start",
                        tool_call=tool_call,
                        done=False
                    )

                    # 执行工具 (可能也是流式的)
                    tool_result = await self._execute_tool_stream(tool_call)
                    yield StreamChunk(
                        type="tool_call_end",
                        tool_call_id=tool_call.get("id"),
                        result=tool_result,
                        done=False
                    )

        # 4. 发送完成信号
        yield StreamChunk(type="done", done=True)
```

#### 工作流集成
```python
class StreamingWorkflowManager(WorkflowManager):
    """支持流式的工作流管理器"""

    async def execute_stream(
        self,
        initial_state: AgentState,
        config: Dict[str, Any]
    ) -> AsyncIterator[StreamChunk]:
        """流式工作流执行"""

        # 状态初始化
        current_state = initial_state

        # 流式LLM调用
        streaming_llm = self._get_streaming_llm()
        messages = current_state["messages"]

        async for chunk in streaming_llm.stream_chat_with_tools(
            messages, self._langchain_tools
        ):
            # 处理内容块
            if chunk["type"] == "content":
                yield StreamChunk(
                    type="content",
                    content=chunk["content"],
                    done=False
                )

            # 处理工具调用
            elif chunk["type"] == "tool_call_start":
                tool_call = chunk["tool_call"]

                # 更新状态
                current_state["tool_calls"] = [tool_call]
                current_state["iteration_count"] += 1

                # 执行工具
                result = await self.tool_executor.execute(
                    tool_call["name"],
                    tool_call["arguments"]
                )

                # 流式输出工具结果
                yield StreamChunk(
                    type="tool_call_end",
                    tool_call_id=tool_call["id"],
                    result=str(result),
                    done=False
                )

                # 继续LLM推理
                continue

        # 完成
        yield StreamChunk(type="done", done=True)
```

## 数据流协议

### 流式数据块格式

```typescript
interface StreamChunk {
  // 块类型
  type: 'content' | 'tool_call_start' | 'tool_call_end' | 'error' | 'done';

  // 内容 (内容块)
  content?: string;

  // 工具调用信息 (工具调用块)
  tool_call?: {
    id: string;
    name: string;
    arguments: Record<string, any>;
  };

  // 工具调用结果 (工具结束块)
  tool_call_id?: string;
  result?: any;

  // 错误信息 (错误块)
  error?: string;

  // 元数据
  metadata?: Record<string, any>;

  // 完成标志
  done: boolean;

  // 时间戳
  timestamp?: string;
}
```

### SSE协议格式
```
data: {"type": "content", "content": "Hello", "done": false}

data: {"type": "tool_call_start", "tool_call": {"id": "call_123", "name": "calculator", "arguments": {"expression": "1+1"}}, "done": false}

data: {"type": "tool_call_end", "tool_call_id": "call_123", "result": "2", "done": false}

data: {"type": "done", "done": true}
```

### WebSocket协议格式
```json
{
  "type": "content",
  "content": "Hello",
  "done": false,
  "timestamp": "2024-01-04T12:00:00Z"
}
```

## 性能优化

### 连接层优化

#### 连接池管理
```go
type ConnectionPool struct {
    sync.RWMutex
    connections map[string]*Connection
    maxConnections int
    idleTimeout time.Duration
}

func (p *ConnectionPool) GetConnection(agentAddr string) (*Connection, error) {
    p.RLock()
    if conn, exists := p.connections[agentAddr]; exists {
        p.RUnlock()
        return conn, nil
    }
    p.RUnlock()

    p.Lock()
    defer p.Unlock()

    // 创建新连接
    conn, err := p.createConnection(agentAddr)
    if err != nil {
        return nil, err
    }

    p.connections[agentAddr] = conn
    return conn, nil
}
```

#### 背压控制
```python
class BackpressureController:
    """背压控制"""

    def __init__(self, max_queue_size: int = 1000):
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.is_backpressured = False

    async def enqueue_chunk(self, chunk: StreamChunk) -> bool:
        """入队数据块，带背压控制"""
        try:
            await asyncio.wait_for(
                self.queue.put(chunk),
                timeout=1.0  # 1秒超时
            )
            return True
        except asyncio.TimeoutError:
            self.is_backpressured = True
            return False

    async def dequeue_chunk(self) -> Optional[StreamChunk]:
        """出队数据块"""
        try:
            chunk = self.queue.get_nowait()
            self.queue.task_done()
            self.is_backpressured = False
            return chunk
        except asyncio.QueueEmpty:
            return None
```

### 内存管理

#### 流式缓冲区
```python
class StreamingBuffer:
    """流式缓冲区"""

    def __init__(self, max_memory_mb: int = 100):
        self.max_size = max_memory_mb * 1024 * 1024
        self.buffers: Dict[str, List[StreamChunk]] = {}
        self.sizes: Dict[str, int] = {}

    def add_chunk(self, session_id: str, chunk: StreamChunk):
        """添加数据块"""
        if session_id not in self.buffers:
            self.buffers[session_id] = []
            self.sizes[session_id] = 0

        # 检查内存限制
        chunk_size = len(str(chunk).encode('utf-8'))
        if self.sizes[session_id] + chunk_size > self.max_size:
            # 清理旧数据
            self._cleanup_old_chunks(session_id, chunk_size)

        self.buffers[session_id].append(chunk)
        self.sizes[session_id] += chunk_size

    def get_chunks(self, session_id: str, start_idx: int = 0) -> List[StreamChunk]:
        """获取数据块"""
        return self.buffers.get(session_id, [])[start_idx:]
```

### 缓存策略

#### 流式缓存
```python
class StreamingCache:
    """流式缓存"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.chunk_ttl = 300  # 5分钟TTL

    async def cache_chunk(self, session_id: str, chunk_idx: int, chunk: StreamChunk):
        """缓存数据块"""
        key = f"stream:{session_id}:{chunk_idx}"
        await self.redis.setex(key, self.chunk_ttl, chunk.json())

    async def get_cached_chunks(self, session_id: str, start_idx: int = 0) -> List[StreamChunk]:
        """获取缓存的数据块"""
        chunks = []
        idx = start_idx

        while True:
            key = f"stream:{session_id}:{idx}"
            chunk_data = await self.redis.get(key)
            if not chunk_data:
                break

            chunk = StreamChunk.parse_raw(chunk_data)
            chunks.append(chunk)
            idx += 1

        return chunks

    async def invalidate_session(self, session_id: str):
        """使会话缓存失效"""
        # 使用SCAN删除所有相关键
        pattern = f"stream:{session_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
```

## 监控和调试

### 流式指标收集

#### 性能指标
```python
class StreamingMetrics:
    """流式指标收集"""

    def __init__(self):
        self.active_connections = 0
        self.total_chunks_sent = 0
        self.avg_chunk_size = 0
        self.connection_duration = Histogram()

    def record_chunk_sent(self, chunk: StreamChunk, size_bytes: int):
        """记录发送的数据块"""
        self.total_chunks_sent += 1
        self.avg_chunk_size = (self.avg_chunk_size + size_bytes) / 2

        # 按类型统计
        chunk_type = chunk.type
        self.chunk_type_counter[chunk_type] += 1

    def record_connection_start(self):
        """记录连接开始"""
        self.active_connections += 1

    def record_connection_end(self, duration: float):
        """记录连接结束"""
        self.active_connections -= 1
        self.connection_duration.observe(duration)
```

#### 业务指标
- **连接数**: 当前活跃的流式连接数
- **数据块统计**: 各类数据块的数量和大小分布
- **延迟指标**: 首字节延迟、数据块间延迟
- **错误率**: 流式传输的错误率和重试率

### 调试支持

#### 流式调试器
```python
class StreamingDebugger:
    """流式调试器"""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.session_logs: Dict[str, List[StreamChunk]] = {}

    async def log_chunk(self, session_id: str, chunk: StreamChunk, direction: str):
        """记录数据块日志"""
        if not self.enabled:
            return

        if session_id not in self.session_logs:
            self.session_logs[session_id] = []

        logged_chunk = chunk.copy()
        logged_chunk.metadata = logged_chunk.metadata or {}
        logged_chunk.metadata.update({
            "debug_timestamp": datetime.now().isoformat(),
            "debug_direction": direction,
            "debug_session_id": session_id
        })

        self.session_logs[session_id].append(logged_chunk)

        # 限制日志大小
        if len(self.session_logs[session_id]) > 1000:
            self.session_logs[session_id] = self.session_logs[session_id][-500:]

    def get_session_log(self, session_id: str) -> List[StreamChunk]:
        """获取会话调试日志"""
        return self.session_logs.get(session_id, [])

    def export_logs(self, session_id: str, format: str = "json") -> str:
        """导出调试日志"""
        logs = self.get_session_log(session_id)
        if format == "json":
            return json.dumps([chunk.dict() for chunk in logs], indent=2)
        return "\n".join(str(chunk) for chunk in logs)
```

## 故障处理

### 连接异常处理

#### 自动重连
```javascript
class StreamReconnector {
    constructor(url, options = {}) {
        this.url = url;
        this.maxRetries = options.maxRetries || 3;
        this.retryDelay = options.retryDelay || 1000;
        this.onReconnect = options.onReconnect || (() => {});
    }

    connect() {
        this.attempts = 0;
        this._connect();
    }

    _connect() {
        try {
            this.eventSource = new EventSource(this.url);
            this.eventSource.onopen = () => {
                console.log('Stream connected');
                this.attempts = 0;
            };

            this.eventSource.onerror = (error) => {
                console.error('Stream error:', error);
                this._handleError();
            };
        } catch (error) {
            this._handleError();
        }
    }

    _handleError() {
        if (this.attempts < this.maxRetries) {
            this.attempts++;
            setTimeout(() => {
                console.log(`Reconnecting... (attempt ${this.attempts})`);
                this.onReconnect(this.attempts);
                this._connect();
            }, this.retryDelay * this.attempts);
        } else {
            console.error('Max retries reached, giving up');
        }
    }
}
```

#### 降级策略
```python
class StreamFallback:
    """流式降级策略"""

    async def execute_with_fallback(
        self,
        stream_func: Callable,
        fallback_func: Callable,
        timeout: float = 30.0
    ):
        """带降级的流式执行"""
        try:
            # 尝试流式执行
            async for chunk in asyncio.wait_for(stream_func(), timeout=timeout):
                yield chunk

        except (asyncio.TimeoutError, ConnectionError, Exception) as e:
            logger.warning(f"Streaming failed, falling back to sync: {e}")

            # 降级到同步执行
            result = await fallback_func()
            yield StreamChunk(
                type="content",
                content=result,
                done=True,
                metadata={"fallback": True, "error": str(e)}
            )
```

### 数据一致性

#### 状态同步
```python
class StreamStateSynchronizer:
    """流式状态同步器"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def sync_state(self, session_id: str, state: AgentState):
        """同步状态到缓存"""
        key = f"session_state:{session_id}"
        await self.redis.setex(key, 3600, state.json())

    async def get_state(self, session_id: str) -> Optional[AgentState]:
        """从缓存获取状态"""
        key = f"session_state:{session_id}"
        state_data = await self.redis.get(key)
        if state_data:
            return AgentState.parse_raw(state_data)
        return None

    async def invalidate_state(self, session_id: str):
        """使状态失效"""
        key = f"session_state:{session_id}"
        await self.redis.delete(key)
```

## 扩展点

### 自定义流式处理器
```python
class CustomStreamProcessor:
    """自定义流式处理器"""

    async def process_chunk(self, chunk: StreamChunk) -> StreamChunk:
        """处理单个数据块"""
        # 自定义处理逻辑
        if chunk.type == "content":
            chunk.content = self._custom_filter(chunk.content)

        return chunk

    async def process_stream(
        self,
        stream: AsyncIterator[StreamChunk]
    ) -> AsyncIterator[StreamChunk]:
        """处理完整流"""
        async for chunk in stream:
            processed = await self.process_chunk(chunk)
            yield processed

# 使用自定义处理器
processor = CustomStreamProcessor()
processed_stream = processor.process_stream(original_stream)
```

### 新的流式协议支持
```python
class WebRTCStreamingHandler:
    """WebRTC流式处理器"""

    def __init__(self):
        self.peer_connections = {}

    async def create_peer_connection(self, session_id: str) -> RTCPeerConnection:
        """创建WebRTC对等连接"""
        pc = RTCPeerConnection()

        # 设置数据通道
        dc = pc.createDataChannel("ai-stream")
        dc.onmessage = self._handle_message

        self.peer_connections[session_id] = pc
        return pc

    async def send_chunk(self, session_id: str, chunk: StreamChunk):
        """通过WebRTC发送数据块"""
        pc = self.peer_connections.get(session_id)
        if pc and pc.dataChannel:
            pc.dataChannel.send(chunk.json())
```

这个流式输出架构设计为Universal Agent提供了完整的实时AI对话能力，支持高并发、高性能的流式交互体验。</contents>
</xai:function_call">Write
