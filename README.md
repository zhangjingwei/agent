# Zero Agent

高性能AI Agent系统，采用微服务架构设计，结合Go语言的高并发API网关与Python的AI推理引擎，提供企业级的AI Agent服务能力。

## 目录

- [核心特性](#核心特性)
- [架构概览](#架构概览)
- [快速开始](#快速开始)
- [系统要求](#系统要求)
- [安装指南](#安装指南)
- [配置说明](#配置说明)
- [使用指南](#使用指南)
- [API文档](#api文档)
- [项目结构](#项目结构)
- [开发指南](#开发指南)
- [部署说明](#部署说明)
- [故障排除](#故障排除)
- [路线图](#路线图)
- [贡献指南](#贡献指南)

## 核心特性

### 高性能架构
- **Go API网关**: 基于Gin框架，支持HTTP/2协议，提供高并发处理能力
- **Python AI核心**: 基于FastAPI和Hypercorn，支持异步处理和流式响应
- **服务发现**: 基于Redis的服务注册与发现机制
- **负载均衡**: 支持轮询、最少连接、随机等多种负载均衡策略

### AI能力
- **多LLM支持**: 支持OpenAI、Anthropic、SiliconFlow等多种LLM提供商
- **LangGraph编排**: 基于状态图的Agent工作流编排引擎
- **工具集成**: 支持内置工具和MCP (Model Context Protocol) 工具
- **流式响应**: 支持Server-Sent Events (SSE) 流式输出

### 企业级特性
- **熔断器**: 自动故障检测和恢复机制
- **缓存优化**: Redis缓存层，提升响应速度
- **可观测性**: 结构化日志、指标收集、健康检查
- **过滤器系统**: 输入验证、输出处理、审计日志等中间件

## 架构概览

```
┌─────────────┐
│  客户端请求  │
└──────┬──────┘
       │ HTTP/2
       ↓
┌─────────────────────────────────────┐
│      Go API网关 (端口: 8080)         │
│  ┌────────────────────────────────┐  │
│  │  • 路由转发                     │  │
│  │  • 负载均衡                     │  │
│  │  • 服务发现                     │  │
│  │  • 缓存层                       │  │
│  │  • 熔断器                       │  │
│  │  • 认证授权                     │  │
│  └────────────────────────────────┘  │
└──────┬──────────────────────────────┘
       │ HTTP/2
       ↓
┌─────────────────────────────────────┐
│   Python AI核心 (端口: 8082)        │
│  ┌────────────────────────────────┐  │
│  │  • LangGraph工作流             │  │
│  │  • LLM推理引擎                 │  │
│  │  • 工具执行器                  │  │
│  │  • MCP工具集成                 │  │
│  │  • 会话管理                    │  │
│  └────────────────────────────────┘  │
└─────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────┐
│         Redis (端口: 6379)           │
│  • 服务注册与发现                    │
│  • 缓存存储                          │
│  • 会话状态                          │
└─────────────────────────────────────┘
```

## 快速开始

### 一键启动（推荐）

使用提供的启动脚本同时启动所有服务：

```bash
# 确保已配置环境变量（见配置说明）
./start.sh
```

启动脚本会自动：
1. 检查环境配置
2. 启动Python AI核心服务（端口8082）
3. 启动Go API网关（端口8080）
4. 验证服务健康状态

### 手动启动

#### 方式一：单独启动服务

**终端1 - 启动Python AI服务**:
```bash
cd zero-agent
source ../venv/bin/activate
python -m scripts.start
```

**终端2 - 启动Go API网关**:
```bash
cd zero-gateway
make run
```

#### 方式二：启用服务发现和负载均衡

**启动Agent实例（启用服务注册）**:
```bash
cd zero-agent
source ../venv/bin/activate

# 设置环境变量
export REDIS_HOST=localhost
export REDIS_PORT=6379
export API_PORT=8082
export LOG_FILE=logs/agent-1.log
export LOG_TO_CONSOLE=false

# 启动服务
python3 -m api.app
```

**启动Gateway（启用服务发现）**:
```bash
cd zero-gateway

# 设置环境变量启用服务发现
export PYTHON_USE_SERVICE_DISCOVERY=true
export PYTHON_SERVICE_NAME=zero-agent
export PYTHON_LOAD_BALANCE_STRATEGY=round_robin
export REDIS_HOST=localhost
export REDIS_PORT=6379
export LOG_FILE=logs/gateway.log
export LOG_TO_CONSOLE=false

# 启动网关
go run cmd/api-gateway/main.go
```

**启动多个Agent实例（测试负载均衡）**:

在多个终端中启动不同端口的Agent实例：

```bash
# 实例1 (端口8082)
export API_PORT=8082
export LOG_FILE=logs/agent-1.log
python3 -m api.app

# 实例2 (端口8083)
export API_PORT=8083
export LOG_FILE=logs/agent-2.log
python3 -m api.app

# 实例3 (端口8084)
export API_PORT=8084
export LOG_FILE=logs/agent-3.log
python3 -m api.app
```

## 系统要求

### 必需组件
- **Python**: 3.9+
- **Go**: 1.24+
- **Redis**: 6.0+ (用于缓存和服务发现)
- **Git**: 2.x+

### 操作系统
- Linux
- macOS
- Windows (推荐使用WSL)

### 可选组件
- **Prometheus**: 用于指标收集
- **Grafana**: 用于监控可视化

## 安装指南

### 1. 克隆项目

```bash
git clone <repository-url>
cd prodject
```

### 2. 安装Python依赖

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -r zero-agent/requirements.txt
```

**注意**: Python服务使用 `hypercorn` 替代 `uvicorn` 以支持HTTP/2协议，提供更好的性能。

### 3. 安装Go依赖

```bash
cd zero-gateway

# 下载依赖
go mod tidy
go mod download

# 构建项目
make build
```

### 4. 启动Redis

```bash
# 使用Docker启动Redis
docker run -d -p 6379:6379 redis:latest

# 或使用本地安装的Redis
redis-server
```

## 配置说明

### 环境变量配置

#### 必需环境变量

至少需要配置一个LLM API密钥：

```bash
# LLM API密钥（至少配置一个）
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export SILICONFLOW_API_KEY="sk-..."

# LLM配置
export LLM_PROVIDER="openai"          # openai, anthropic, siliconflow
export LLM_MODEL="gpt-4o-mini"        # 根据提供商选择模型
```

#### 可选环境变量

```bash
# 日志配置
export LOG_LEVEL="info"               # debug, info, warn, error
export LOG_FILE="logs/app.log"        # 日志文件路径
export LOG_TO_CONSOLE="true"          # 是否输出到控制台

# Python AI服务配置
export PYTHON_AGENT_HOST="localhost"  # Python AI服务主机
export PYTHON_AGENT_PORT="8082"       # Python AI服务端口
export API_PORT="8082"                # API服务端口

# Redis配置
export REDIS_HOST="localhost"         # Redis主机
export REDIS_PORT="6379"              # Redis端口

# 服务发现配置（Gateway）
export PYTHON_USE_SERVICE_DISCOVERY="true"      # 启用服务发现
export PYTHON_SERVICE_NAME="zero-agent"         # 服务名称
export PYTHON_LOAD_BALANCE_STRATEGY="round_robin"  # 负载均衡策略
```

#### 负载均衡策略

支持以下负载均衡策略：
- `round_robin`: 轮询策略（默认）
- `least_conn`: 最少连接策略
- `random`: 随机策略
- `weighted_round`: 加权轮询策略

### 配置文件

#### Python Agent配置

Agent配置位于 `zero-agent/config/agents/` 目录，支持YAML格式配置：

```yaml
id: zero
name: Zero Agent
llm_config:
  provider: openai
  model: gpt-4o-mini
  temperature: 0.7
tools:
  - id: calculator
    enabled: true
```

#### Go Gateway配置

Gateway配置可通过环境变量或配置文件设置，参考 `zero-gateway/.env.example`。

## 使用指南

### 服务端口

| 服务 | 地址 | 说明 |
|------|------|------|
| Go API网关 | http://localhost:8080 | 外部HTTP接口 |
| Python AI核心 | http://localhost:8082 | 内部AI服务 |
| Redis缓存 | localhost:6379 | 缓存和服务发现 |
| Prometheus | http://localhost:9090 | 指标收集（可选） |
| Grafana | http://localhost:3000 | 监控可视化（可选） |

### 健康检查

```bash
# 检查API网关
curl http://localhost:8080/health

# 检查AI服务
curl http://localhost:8082/health
```

## API文档

### 创建会话

```bash
curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"metadata": {}}'
```

**响应**:
```json
{
  "session_id": "session-123",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 发送对话

```bash
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-123",
    "message": "你好，请介绍一下你自己",
    "metadata": {}
  }'
```

**响应**:
```json
{
  "message": "AI回复内容",
  "tool_calls": [],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  },
  "processing_time": 0.1
}
```

### 流式对话

```bash
curl -X POST http://localhost:8080/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-123",
    "message": "请详细介绍一下AI",
    "metadata": {}
  }'
```

### 获取可用工具

```bash
curl http://localhost:8080/api/v1/tools
```

## 项目结构

```
prodject/
├── zero-agent/              # Python AI核心服务
│   ├── api/                 # FastAPI应用
│   ├── core/                # AI推理引擎
│   │   ├── agent.py        # Agent核心接口
│   │   ├── factory.py      # Agent工厂
│   │   └── circuit_breaker.py  # 熔断器
│   ├── orchestration/       # LangGraph工作流
│   │   ├── agent.py        # 编排Agent
│   │   ├── workflow.py     # 工作流定义
│   │   └── state.py        # 状态管理
│   ├── tools/              # 工具管理
│   │   ├── builtin/        # 内置工具
│   │   ├── mcp/            # MCP工具集成
│   │   └── executor.py     # 工具执行器
│   ├── config/             # 配置管理
│   │   ├── agents/         # Agent配置
│   │   └── templates/      # 配置模板
│   ├── filters/            # 过滤器系统
│   ├── llm/                # LLM提供商
│   └── scripts/            # 启动脚本
│
├── zero-gateway/            # Go API网关服务
│   ├── cmd/                # 主程序入口
│   │   └── api-gateway/    # API网关服务
│   ├── internal/           # 私有代码
│   │   ├── api/           # HTTP API处理器
│   │   ├── business/      # 业务逻辑
│   │   ├── config/        # 配置管理
│   │   └── infrastructure/ # 基础设施
│   └── pkg/               # 共享库
│       ├── cache/         # 缓存层
│       ├── circuitbreaker/ # 熔断器
│       ├── filters/       # 过滤器
│       └── session/       # 会话管理
│
├── start.sh                # 系统启动脚本
├── test.sh                 # 测试脚本
└── README.md              # 项目文档
```

## 开发指南

### 构建Go API网关

```bash
cd zero-gateway
make build
```

### 运行测试

```bash
# Python测试
cd zero-agent
pytest

# Go测试
cd zero-gateway
make test
```

### 代码规范

- **Python**: 遵循PEP 8规范，使用Black格式化
- **Go**: 使用 `gofmt` 格式化，遵循Go官方代码规范

### 添加新工具

1. 在 `zero-agent/tools/builtin/` 创建工具模块
2. 实现工具接口
3. 在Agent配置中注册工具

### 添加新LLM提供商

1. 在 `zero-agent/llm/` 创建提供商模块
2. 实现 `BaseLLMProvider` 接口
3. 在工厂中注册提供商

## 部署说明

### Docker部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d
```

### 生产环境建议

1. **使用Nuitka编译Python服务**: 提升性能和安全性
2. **启用HTTPS**: 配置SSL/TLS证书
3. **配置反向代理**: 使用Nginx或Traefik
4. **监控告警**: 集成Prometheus和Grafana
5. **日志聚合**: 使用ELK或Loki收集日志

## 故障排除

### 常见问题

#### 1. 服务启动失败

**检查服务状态**:
```bash
# 检查AI服务
curl http://localhost:8082/health

# 检查API网关
curl http://localhost:8080/health
```

**检查日志**:
```bash
# Python服务日志
tail -f zero-agent/logs/agent.log

# Go网关日志
tail -f zero-gateway/logs/gateway.log
```

#### 2. LLM API调用失败

- 检查API密钥是否正确配置
- 验证网络连接
- 检查API配额和限制

#### 3. Redis连接失败

- 确认Redis服务已启动
- 检查Redis主机和端口配置
- 验证Redis连接权限

#### 4. 服务发现不工作

- 确认Redis服务正常运行
- 检查服务注册环境变量
- 验证服务名称配置一致

### 调试模式

启用调试日志：

```bash
export LOG_LEVEL="debug"
```

## 路线图

### 已完成
- [x] Go API网关基础功能
- [x] Python AI核心服务
- [x] LangGraph工作流编排
- [x] 服务发现和负载均衡
- [x] 熔断器机制
- [x] 过滤器系统
- [x] MCP工具集成

### 计划中
- [ ] Python服务Nuitka编译
- [ ] gRPC支持
- [ ] WebSocket实时通信
- [ ] 分布式追踪
- [ ] 更多内置工具
- [ ] Kubernetes部署配置
- [ ] 性能优化和基准测试

## 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork本项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

### 贡献规范

- 遵循项目代码规范
- 添加必要的测试
- 更新相关文档
- 确保所有测试通过

## 许可证

本项目采用 MIT 许可证。

---

**注意**: 本项目仍在积极开发中，API可能会发生变化。建议在生产环境使用前进行充分测试。
