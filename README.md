# Zero Agent

**语言**: 简体中文 | [English](README.en.md)

面向生产落地的 AI Agent 系统，采用 Go 网关 + Python Agent 核心的微服务架构，聚焦可扩展编排、工具生态接入与稳定性保障。

## 项目定位

- **双服务解耦**: `zero-gateway` 负责流量治理与接入层能力，`zero-agent` 负责推理编排与工具执行
- **稳定优先**: 支持 MCP 下线降级运行，避免外部工具故障阻塞核心对话服务
- **渐进式能力注入**: Skill 支持 `metadata/full/resources` 分级加载，平衡上下文质量与 Token 成本
- **面向运维**: 内置服务发现、负载均衡、熔断、结构化日志与健康检查

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
- **Skill系统**: 支持渐进式加载的Agent技能系统，通过SKILL.md文件提供任务级指导
- **流式响应**: 支持Server-Sent Events (SSE) 流式输出

### 企业级特性
- **熔断器**: 自动故障检测和恢复机制
- **缓存优化**: Redis缓存层，提升响应速度
- **可观测性**: 结构化日志、指标收集、健康检查
- **过滤器系统**: 输入验证、输出处理、审计日志等中间件
- **MCP降级容错**: MCP不可用时仍可完成Agent启动与基础工具对话

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
│  │  • Skill系统（渐进式加载）     │  │
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

### 快速启动（推荐）

**适用场景**：单机开发、快速测试、不需要负载均衡的场景

```bash
# 终端1：启动 Python AI 服务（8082）
cd zero-agent
source ../venv/bin/activate
python -m scripts.start

# 终端2：启动 Go API 网关（8080）
cd zero-gateway
make run
```

### 启用服务发现和负载均衡（生产模式）

**适用场景**：多实例部署、负载均衡测试、生产环境、高可用需求

**特点**：
- 支持服务注册与发现（基于 Redis）
- 支持多个 Agent 实例负载均衡
- 支持多种负载均衡策略（轮询、最少连接、随机等）
- 需要 Redis 服务支持
- 适合生产环境和性能测试

**前置要求**：
- Redis 服务必须运行（用于服务注册与发现）
- 需要配置相关环境变量

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

在多个终端中启动不同端口的Agent实例，Gateway会自动发现并负载均衡：

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

**两种方式对比**：

| 特性 | 方式一（简单模式） | 方式二（生产模式） |
|------|------------------|------------------|
| **启动命令** | `python -m scripts.start` | `python3 -m api.app` |
| **配置复杂度** | 低（使用默认配置） | 中（需要环境变量） |
| **Redis依赖** | 可选（仅缓存） | 必需（服务发现） |
| **负载均衡** | 不支持 | 支持（多实例） |
| **适用场景** | 开发、测试 | 生产、高可用 |
| **扩展性** | 单实例 | 多实例横向扩展 |
| **服务发现** | 无 | 自动发现和注册 |
| **推荐用途** | 快速启动、功能验证 | 性能测试、生产部署 |

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
skills:
  - id: test_skill
    name: 测试技能
    path: skills/examples/test_skill
    enabled: true
    load_level: full  # metadata, full, resources
    priority: 50
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

### Skill系统说明

Skill系统支持渐进式加载机制，通过SKILL.md文件为Agent提供任务级指导：

- **Level 1 (metadata)**: 仅加载名称和描述，Token消耗最小（< 100 tokens）
- **Level 2 (full)**: 加载完整Markdown内容（< 1000 tokens）
- **Level 3 (resources)**: 加载所有资源文件（scripts/, references/, assets/等）

Skill会在Agent初始化时自动加载，并在对话时作为上下文注入到LLM，帮助Agent更好地理解任务和提供指导。

## 项目结构

```
prodject/
├── zero-agent/              # Python Agent核心服务（编排/技能/MCP）
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
│   ├── skills/             # Skill系统
│   │   ├── base.py         # Skill基础类
│   │   ├── parser.py       # SKILL.md解析器
│   │   ├── registry.py     # Skill注册器
│   │   ├── loader.py       # 渐进式加载器
│   │   ├── manager.py      # Skill管理器
│   │   └── examples/       # 示例Skill
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

### 添加新Skill

1. 在 `zero-agent/skills/examples/` 创建Skill目录
2. 创建 `SKILL.md` 文件，包含YAML frontmatter和Markdown正文：
   ```markdown
   ---
   name: 我的技能
   description: 技能描述
   version: 1.0.0
   tags: [tag1, tag2]
   required_tools: [tool1, tool2]
   examples:
     - "示例1"
     - "示例2"
   ---
   
   # 技能标题
   
   技能详细说明...
   ```
3. 在Agent配置中注册Skill：
   ```yaml
   skills:
     - id: my_skill
       name: 我的技能
       path: skills/examples/my_skill
       enabled: true
       load_level: metadata  # metadata, full, resources
       priority: 100
   ```

### 添加新Skill

1. 在 `zero-agent/skills/examples/` 创建Skill目录
2. 创建 `SKILL.md` 文件，包含YAML frontmatter和Markdown正文
3. 在Agent配置中注册Skill：
   ```yaml
   skills:
     - id: my_skill
       name: 我的技能
       path: skills/examples/my_skill
       enabled: true
       load_level: metadata  # metadata, full, resources
       priority: 100
   ```

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

## 贡献指南

欢迎贡献代码与文档，建议先阅读集中规范：
`docs/project/contributing.md`

快速流程：
1. Fork 并创建分支（基于 `master`）
2. 完成功能与测试
3. 使用 Conventional Commits 提交
4. 发起 Pull Request（说明变更与验证结果）

## 许可证

本项目采用 MIT 许可证。

---

**注意**: 本项目仍在积极开发中，API可能会发生变化。建议在生产环境使用前进行充分测试。
