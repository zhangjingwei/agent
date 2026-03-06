# 架构设计总览

Zero Agent 采用 **Gateway + Agent Core** 的分层微服务架构：

- `zero-gateway`（Go/Gin）负责统一 API 接入、会话管理、转发、负载与熔断
- `zero-agent`（Python/FastAPI）负责对话编排、LLM 调用、工具执行与 Skill 注入
- Redis 作为会话与服务发现基础设施（按部署模式可选/必需）

## 整体架构

```text
Client
  │  HTTP/HTTPS
  ▼
zero-gateway (Go)
  ├─ API routing (/api/v1/*)
  ├─ Session management (Redis)
  ├─ Circuit breaker / retry
  ├─ Service discovery + load balancing (optional, Redis-based)
  └─ SSE stream forwarding
  │
  │  Internal HTTP
  ▼
zero-agent (Python)
  ├─ Agent registry (/agents)
  ├─ Chat endpoint (/agents/{agent_id}/chat?stream=...)
  ├─ Tools endpoint (/agents/{agent_id}/tools)
  ├─ LangGraph workflow orchestration
  ├─ LLM provider invocation
  ├─ Builtin tools + MCP tools
  └─ Skill context injection (metadata/full/resources)
  │
  ▼
External Services
  ├─ LLM providers (OpenAI / Anthropic / SiliconFlow ...)
  ├─ MCP servers (stdio transport)
  └─ Other HTTP APIs
```

## 真实接口拓扑（当前代码）

### Gateway 对外接口

- `GET /health`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/:session_id/history`
- `DELETE /api/v1/sessions/:session_id`
- `POST /api/v1/chat`（`stream=false/true` 统一入口）
- `GET /api/v1/tools`（支持 `agent_id` 查询参数）

### Agent 内部接口（Gateway 调用）

- `GET /health`
- `GET /agents`
- `POST /agents/{agent_id}/chat?stream=false|true`
- `GET /agents/{agent_id}/tools`

## 关键设计点

### 1) 统一对话入口（流式/非流式）

Gateway 仅暴露一个聊天端点 `POST /api/v1/chat`：

- `stream=false`：返回 JSON 响应
- `stream=true`：以 `text/event-stream` 转发 SSE 数据块

这样能保持客户端接入简单，同时减少路由分叉带来的维护成本。

### 2) 会话与上下文链路

- 会话由 Gateway 管理（Redis）
- 请求转发前读取历史消息并注入 `message_history`
- Agent 生成回复后，Gateway 再写回会话历史

会话不存在时，系统会尽量降级处理（不中断核心对话路径）。

### 3) 编排与工具执行

Agent 使用 LangGraph 驱动工作流，支持：

- 常规内容生成（`content` chunk）
- 工具调用事件（`tool_call_start` / `tool_call_end`）
- 完成与错误事件（`done` / `error`）

工具来源包括：

- 内置工具（如 `calculator`）
- MCP 工具（动态发现并注册）

### 4) MCP 降级容错

MCP 初始化采用并行策略，单个 MCP 服务失败不会阻塞 Agent 启动：

- 失败服务会记录到降级摘要日志
- 可用工具仍可正常对话
- 失败连接会执行清理，避免残留资源

## 请求数据流

### 非流式

```text
Client
  -> POST /api/v1/chat (stream=false)
Gateway
  -> prepare history/session
  -> POST /agents/{id}/chat?stream=false
Agent
  -> workflow + llm + tools
  <- JSON response
Gateway
  -> persist assistant message
  <- {"data": {...}}
```

### 流式（SSE）

```text
Client
  -> POST /api/v1/chat (stream=true)
Gateway
  -> POST /agents/{id}/chat?stream=true
Agent
  -> emits SSE chunks: content/tool_call_start/tool_call_end/done
Gateway
  -> forwards SSE chunks to client
  -> assembles final text for session persistence
```

## 组件职责

### zero-gateway（Go）

- API 路由与协议适配
- 会话生命周期管理（创建/历史/删除）
- 请求转发与错误码归一化
- SSE 透传
- 熔断器与基础可观测
- Redis 服务发现与负载均衡（生产模式）

### zero-agent（Python）

- Agent 实例工厂与注册
- LangGraph 工作流执行
- LLM 适配（多提供商）
- 工具注册与执行（内置 + MCP）
- Skill 解析与分级加载（`metadata/full/resources`）
- 流式事件输出

## 部署模式

### 开发模式（单实例）

- Gateway：`:8080`
- Agent：`:8082`
- Redis：可按场景启用（建议启用以覆盖完整链路）

### 生产模式（多实例）

- 多个 Agent 实例注册到 Redis
- Gateway 基于服务发现进行负载均衡
- 结合熔断与健康检查保障可用性

## 当前边界（文档与实现保持一致）

- 对外流式协议为 **SSE**（不是 WebSocket）
- Gateway 与 Agent 之间当前为 **HTTP 调用**（不是 gRPC）
- 未提供独立的 `/api/v1/chat/stream` 端点（统一使用 `/api/v1/chat` + `stream=true`）

---

如需查看字段级接口定义与示例，请配合阅读：

- `docs/api/reference.md`
- `docs/api/examples.md`
- `docs/architecture/streaming.md`
