# Zero Gateway

高性能Go API网关，为Zero Agent提供网络接口和请求路由服务。

## 概述

Zero Gateway是Zero Agent生态系统中的高性能API网关，通过Go语言实现高并发HTTP处理，将客户端请求路由到Python核心服务。

## 架构组件

### API Gateway
- **端口**: 8080
- **职责**: HTTP API网关、请求路由、认证授权、负载均衡
- **技术栈**: Gin, HTTP/2, Redis, JWT

## 性能目标

| 指标 | 目标值 | 提升幅度 |
|------|--------|----------|
| API响应时间 | <50ms (P95) | 5-10x |
| 并发连接数 | >10000 | 10x |
| 内存使用率 | 降低30% | -30% |

## 项目结构

```
zero-gateway/
├── cmd/                    # 主程序入口
│   └── api-gateway/       # API网关服务
├── internal/              # 私有应用代码
│   ├── api/              # HTTP API处理器
│   └── config/           # 配置管理
├── pkg/                  # 可共享的库代码
│   ├── grpc/            # gRPC客户端
│   ├── cache/           # 缓存层
│   └── middleware/      # 中间件
├── proto/               # Protocol Buffers定义
├── docker/              # Docker构建配置
├── build/               # 构建输出目录
├── Makefile            # 构建脚本
├── go.mod              # Go模块定义
└── README.md           # 项目文档
```

## 快速开始

### 环境要求
- Go 1.21+
- Docker & Docker Compose
- Redis (可选，用于缓存)

### 构建和运行

```bash
# 安装依赖
make deps

# 构建API网关
make build

# 运行API网关
make run

# 或者使用Docker
make docker-build
make docker-run
```

### 测试

```bash
# 运行单元测试
make test

# 运行基准测试
make bench

# 生成测试覆盖率
make test-coverage
```

## 开发指南

### 代码规范
- 使用 `gofmt` 格式化代码
- 使用 `go vet` 进行静态检查
- 使用 `golangci-lint` 进行代码质量检查

```bash
# 运行所有检查
make check
```

### 添加新依赖
```bash
go get package-name
go mod tidy
```

### 生成Protobuf代码
```bash
make proto-gen
```

## API文档

### API Gateway

#### POST /api/v1/chat
处理对话请求，通过HTTP/2转发到Python FastAPI服务。

**请求体**:
```json
{
  "session_id": "string",
  "message": "string",
  "metadata": {}
}
```

**响应**:
```json
{
  "message": "AI回复内容",
  "tool_calls": [],
  "usage": {},
  "processing_time": 0.1
}
```

#### GET /api/v1/tools
获取可用工具列表。

#### POST /api/v1/sessions
创建新会话。

## 监控和可观测性

### 指标收集
- Prometheus指标暴露在 `/metrics` 端点
- 自定义业务指标和性能指标

### 日志记录
- 结构化JSON日志
- 支持不同日志级别
- 请求追踪ID

### 健康检查
- `/health` - 服务健康状态
- `/ready` - 服务就绪状态

## 部署

### Docker部署
```bash
# 构建镜像
make docker-build

# 使用docker-compose部署
docker-compose up -d
```

### Kubernetes部署
参考 `k8s/` 目录下的配置文件。

## 性能优化

### API Gateway优化
- HTTP/2协议
- 连接池复用
- 请求压缩
- 缓存层
- JWT认证
- 请求限流
- 负载均衡

## 安全考虑

- 请求频率限制
- 请求大小限制
- 输入验证
- 超时控制
- 错误信息过滤

## 贡献指南

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

## 许可证

本项目采用MIT许可证。
