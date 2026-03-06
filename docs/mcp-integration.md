# MCP 集成指南

## 概述

本项目已集成 Model Context Protocol (MCP)，允许 agent 无缝连接和使用外部 MCP 服务器提供的工具。

## 支持的传输方式

当前实现 **仅支持 stdio 传输**，这是最常用和最安全的 MCP 服务器部署方式。

### 支持的 MCP 服务器类型
- ✅ **本地 MCP 服务器**：通过命令行启动，如 `caiyun-weather`
- ✅ **官方 MCP 工具**：filesystem、git、database 等
- ✅ **自定义 MCP 服务器**：任何支持 stdio 的 MCP 实现

### 不支持的传输方式
- ❌ HTTP/WebSocket：为保持架构简洁，暂时不支持
- ❌ gRPC：不在 MCP 官方规范中

## 配置方法

### 1. 环境变量

确保设置必要的环境变量：

```bash
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-3.5-turbo
export OPENAI_API_KEY=your-api-key
```

### 2. MCP 服务器配置

在 `config/settings.py` 中添加 MCP 服务器配置：

```python
from config.models import MCPConfig

# 添加到 mcp_servers 列表
MCPConfig(
    id="caiyun-weather",                    # 唯一标识符
    name="彩云天气",                        # 显示名称
    description="提供中国天气预报服务",      # 描述
    command="uvx",                         # 启动命令
    args=["mcp-caiyun-weather"],           # 命令参数
    env={                                  # 环境变量
        "CAIYUN_WEATHER_API_TOKEN": os.getenv("CAIYUN_WEATHER_API_TOKEN", "")
    },
    enabled=True,                          # 是否启用
    timeout=30000,                         # 超时时间(毫秒)
    working_dir=None                       # 工作目录(可选)
)
```

### 3. 工具配置（可选）

可以自定义特定工具的配置：

```python
from config.models import MCPToolConfig

# 添加到 mcp_tools 列表
MCPToolConfig(
    server_id="caiyun-weather",                    # 对应服务器ID
    tool_name="get_realtime_weather",             # 工具名称
    enabled=True,                                 # 是否启用
    description_override="获取指定位置的实时天气信息" # 自定义描述(可选)
)
```

## 启动时初始化

MCP 服务在 FastAPI 应用启动时就会初始化，确保：

- ✅ **预热连接**：应用启动时立即连接 MCP 服务器
- ✅ **工具发现**：启动时发现并注册所有可用工具
- ✅ **错误可见**：启动失败时立即可见，便于调试
- ✅ **性能优化**：避免首次请求时的延迟

### 启动日志示例

```bash
INFO - Starting Zero Agent Service
ERROR - 连接MCP服务器失败 caiyun-weather: [Errno 2] No such file or directory: 'uvx'
WARNING - MCP服务器 caiyun-weather 的工具将不可用，请检查服务器配置或网络连接
INFO - Agent initialized successfully
```

## 使用示例

### 基本使用

```python
from core.agent import UniversalAgent
from config.settings import get_agent_config

# 初始化 agent
config = get_agent_config()
agent = UniversalAgent(config)

# 创建会话并对话
session = await agent.create_session()
response = await agent.chat(session.id, ChatRequest(message="北京现在的天气怎么样？"))
print(response.message)
```

### 可用工具

配置彩云天气 MCP 服务器后，以下工具将自动可用：

- `get_realtime_weather`: 获取实时天气
- `get_hourly_forecast`: 获取小时预报
- `get_weekly_forecast`: 获取周预报
- `get_historical_weather`: 获取历史天气
- `get_weather_alerts`: 获取天气预警

## 架构说明

### 组件结构

```
tools/mcp/
├── __init__.py          # 模块导出
├── client.py           # MCP 客户端 (stdio 传输)
└── tool.py            # MCP 工具包装器

config/
└── models.py           # MCP 配置模型

tools/
└── manager.py          # MCP 工具管理

orchestration/
└── agent.py            # MCP 服务器生命周期管理

core/
└── agent.py            # 统一接口

api/
└── app.py              # FastAPI 应用启动时初始化 MCP 服务
```

### 生命周期

1. **应用启动**：FastAPI 应用启动时初始化 MCP 服务
2. **连接建立**：应用启动时立即连接到 MCP 服务器
3. **工具注册**：启动时发现并注册所有可用工具
4. **通信就绪**：通过 stdio 使用 JSON-RPC 协议通信
5. **应用关闭**：断开所有 MCP 连接并清理资源

### 错误处理

- MCP 服务器连接失败不会影响其他功能
- 单个工具失败不会影响其他工具
- 支持超时和重试机制
- 详细的日志记录

## 扩展指南

### 添加新的 MCP 服务器

1. 安装对应的 MCP 服务器包
2. 在配置中添加 MCPConfig
3. 设置必要的环境变量
4. 重启 agent 服务

### 自定义工具配置

通过 MCPToolConfig 可以：
- 启用/禁用特定工具
- 覆盖工具描述
- 映射参数名称（未来扩展）

## 故障排除

### 常见问题

1. **命令未找到**
   ```
   错误: [Errno 2] No such file or directory: 'uvx'
   解决: 安装 uv 或使用 python -m 方式启动
   ```

2. **MCP 包不存在或有问题**
   ```
   错误: 获取MCP工具列表失败: Invalid request parameters
   解决: 使用 MCP inspector 调试包
   ```

3. **API 密钥未设置**
   ```
   错误: MCP服务器进程启动失败
   解决: 设置必要的环境变量
   ```

4. **连接超时**
   ```
   错误: 请求超时
   解决: 增加 timeout 配置值
   ```

### MCP 包调试指南

当遇到 MCP 包问题时，可以使用 MCP inspector 进行调试：

#### **调试 Python MCP 包**:
```bash
# 对于 uvx 包
npx @modelcontextprotocol/inspector uvx mcp-caiyun-weather

# 对于本地 Python 包
npx @modelcontextprotocol/inspector python -m mcp_server_example
```

#### **调试 Node.js MCP 包**:
```bash
# 对于 npx 包
npx @modelcontextprotocol/inspector npx -y @modelcontextprotocol/server-filesystem /tmp

# 对于本地 Node.js 包
npx @modelcontextprotocol/inspector node /path/to/mcp-server.js
```

#### **MCP Inspector 功能**:
- ✅ 验证 MCP 服务器是否能正常启动
- ✅ 检查 JSON-RPC 通信是否正常
- ✅ 查看工具列表和参数定义
- ✅ 测试工具调用功能
- ✅ 发现协议兼容性问题

#### **常见调试结果**:
- **成功**: 显示可用工具列表
- **包不存在**: "command not found" 或 "module not found"
- **协议错误**: "Invalid request parameters"
- **启动失败**: 服务器进程异常退出

#### **解决方案**:
1. **包不存在**: 检查包名是否正确，尝试安装
2. **协议错误**: 可能是包版本问题或实现bug
3. **启动失败**: 检查环境变量和依赖

### 已验证可用的 MCP 服务器

当前配置中包含以下已验证可用的服务器：

- **文件系统工具** (`@modelcontextprotocol/server-filesystem`)
  - 提供 14 个文件操作工具
  - 无需额外配置，开箱即用

如需添加其他 MCP 服务器，建议先使用 inspector 验证其可用性。

### 调试方法

启用详细日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 最佳实践

1. **环境变量**：使用环境变量管理敏感信息
2. **超时设置**：根据 MCP 服务器响应时间调整
3. **错误处理**：在生产环境中添加重试逻辑
4. **资源管理**：确保在应用退出时调用 cleanup()

## 未来扩展

- **HTTP 传输**：支持远程 MCP 服务器
- **工具缓存**：缓存工具信息以提升性能
- **连接池**：复用 MCP 服务器连接
- **监控指标**：添加 MCP 操作的监控
