# Nexus Agent

高性能AI Agent系统，采用微服务架构：Go API网关 + Python AI核心。

## 🏗️ 架构概览

```
客户端请求 → Go API网关 (8080) → Python AI核心 (8082)
     ↓              ↓                     ↓
   HTTP/2       路由转发              AI推理
   认证         负载均衡              MCP工具
   监控         缓存优化              LangGraph
```

## 🚀 快速启动

### 方式1：一键启动（推荐）
```bash
# 设置API密钥
export OPENAI_API_KEY="your-key-here"

# 启动完整系统
./start.sh
```

### 方式2：Docker Compose
```bash
# 构建并启动所有服务
docker-compose -f nexus-gateway/docker-compose.yml up --build
```

### 方式3：手动启动
```bash
# 终端1：启动Python AI服务
cd nexus-agent
python -m scripts.start

# 终端2：启动Go API网关
cd nexus-gateway
make run
```

## 📋 服务端口

- **Go API网关**: http://localhost:8080 (外部HTTP接口)
- **Python AI核心**: http://localhost:8082 (内部AI服务)
- **Redis缓存**: localhost:6379
- **Prometheus**: http://localhost:9090 (可选)
- **Grafana**: http://localhost:3000 (可选)

## 🔧 环境配置

### 必需环境变量
```bash
# 至少设置一个LLM API密钥
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export SILICONFLOW_API_KEY="sk-..."

# LLM配置
export LLM_PROVIDER="openai"          # openai, anthropic, siliconflow
export LLM_MODEL="gpt-4o-mini"       # 根据提供商选择模型
```

### 可选环境变量
```bash
export LOG_LEVEL="info"              # debug, info, warn, error
export PYTHON_AGENT_HOST="localhost" # Python AI服务主机
export PYTHON_AGENT_PORT="8082"      # Python AI服务端口
```

## 🧪 测试API

```bash
# 健康检查
curl http://localhost:8080/health

# 创建会话
curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"metadata": {}}'

# 发送对话
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-123",
    "message": "你好，请介绍一下你自己",
    "metadata": {}
  }'
```

## 📁 项目结构

```
nexus-agent/          # Python AI核心服务
├── api/             # FastAPI应用
├── core/            # AI推理引擎
├── orchestration/   # LangGraph工作流
├── tools/           # MCP工具管理
└── scripts/start.py # AI服务启动脚本

nexus-gateway/        # Go API网关服务
├── cmd/             # 主程序
├── internal/        # 私有代码
├── pkg/             # 共享库
├── proto/           # Protocol Buffers
└── docker/          # 容器配置

start.sh             # 系统启动脚本
```

## 🛠️ 开发指南

### 构建Go API网关
```bash
cd nexus-gateway
make build
```

### 单独启动服务

**Python AI服务**:
```bash
cd nexus-agent
python -m scripts.start
```

**Go API网关**:
```bash
cd nexus-gateway
make run
```

## 🔍 故障排除

### 检查服务状态
```bash
# 检查AI服务
curl http://localhost:8082/health

# 检查API网关
curl http://localhost:8080/health
```

### 查看日志
```bash
# AI服务日志（在另一个终端）
cd nexus-agent && python -m scripts.start

# API网关日志
cd nexus-gateway && make run
```

## 🤝 贡献

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。
