# Zero Agent

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
docker-compose -f zero-gateway/docker-compose.yml up --build
```

### 方式3：手动启动
```bash
# 终端1：启动Python AI服务
cd zero-agent
python -m scripts.start

# 终端2：启动Go API网关
cd zero-gateway
make run
```

## 📋 服务端口

- **Go API网关**: http://localhost:8080 (外部HTTP接口)
- **Python AI核心**: http://localhost:8082 (内部AI服务)
- **Redis缓存**: localhost:6379
- **Prometheus**: http://localhost:9090 (可选)
- **Grafana**: http://localhost:3000 (可选)

## 📦 安装

### 系统要求

- **Python**: 3.8+
- **Go**: 1.19+
- **Git**: 2.x+
- **操作系统**: Linux/macOS/Windows (WSL)

### 自动安装（推荐）

```bash
# 克隆项目（如果还没有的话）
git clone <repository-url>
cd zero-agent

# 运行自动安装脚本
./install.sh
```

安装脚本将自动：
- ✅ 检查系统依赖
- ✅ 创建Python虚拟环境
- ✅ 安装Python依赖包
- ✅ 安装Go依赖包
- ✅ 构建Go项目
- ✅ 创建环境配置文件
- ✅ 设置脚本权限

### 手动安装

如果需要手动安装或遇到问题，可以按以下步骤操作：

#### 1. 安装Python依赖
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖（包括hypercorn用于HTTP/2支持）
pip install fastapi hypercorn python-dotenv structlog langchain langchain-core langchain-openai langchain-anthropic langgraph openai anthropic mcp pydantic httpx

# 或者如果有requirements.txt
pip install -r zero-agent/requirements.txt
```

**注意**：Python服务使用 `hypercorn` 替代 `uvicorn` 以支持HTTP/2协议，提供更好的性能。

#### 2. 安装Go依赖
```bash
cd zero-gateway

# 下载依赖
go mod tidy
go mod download

# 构建项目
make build
```

#### 3. 配置环境变量
```bash
# 复制环境配置模板
cp zero-gateway/env.example zero-gateway/.env

# 编辑配置文件
nano zero-agent/.env     # 配置API密钥
nano zero-gateway/.env   # 调整Go服务配置
```

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
zero-agent/          # Python AI核心服务
├── api/             # FastAPI应用
├── core/            # AI推理引擎
├── orchestration/   # LangGraph工作流
├── tools/           # MCP工具管理
└── scripts/start.py # AI服务启动脚本

zero-gateway/        # Go API网关服务
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
cd zero-gateway
make build
```

### 单独启动服务

**Python AI服务**:
```bash
cd zero-agent
python -m scripts.start
```

**Go API网关**:
```bash
cd zero-gateway
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
cd zero-agent && python -m scripts.start

# API网关日志
cd zero-gateway && make run
```

## 🤝 贡献

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。


python服务需要使用Nuitka 进行编译。
