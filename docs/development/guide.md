# 开发指南（实现对齐版）

本指南面向当前代码仓，聚焦“可执行步骤”。  
如果只看一份开发文档，优先看这份。

## 1. 项目结构（双服务）

```text
prodject/
├── zero-gateway/            # Go 网关：对外 API、会话、转发、熔断、服务发现
├── zero-agent/              # Python 核心：编排、LLM、工具、Skill、MCP
└── docs/                    # 文档
```

核心协作关系：

- 客户端只调用 Gateway：`/api/v1/*`
- Gateway 转发到 Agent：`/agents/{agent_id}/...`
- Agent 负责真正的 LLM 推理与工具执行

## 2. 新增内置工具（zero-agent）

### 2.1 实现工具函数/类

推荐与现有 `calculator` 一样，使用 function handler：

```python
# zero-agent/tools/builtin/echo.py
def echo(text: str) -> str:
    if not text:
        raise ValueError("text is required")
    return f"echo: {text}"
```

### 2.2 在 Agent 配置中注册工具

编辑 `zero-agent/config/agents/default_agent.yaml`：

```yaml
tools:
  - id: echo
    name: echo
    description: 回显输入文本
    parameters:
      type: object
      properties:
        text:
          type: string
      required: [text]
    handler:
      type: function
      module: tools.builtin.echo
      function: echo
      timeout: 5000
    enabled: true
```

### 2.3 验证

- 重启 `zero-agent`
- 调 `GET /api/v1/tools`，确认工具已出现
- 发一条会触发该工具的对话，确认 `tool_calls` 中可见

## 3. 新增 MCP 工具配置

编辑 `zero-agent/config/agents/default_agent.yaml`：

```yaml
mcp_servers:
  - id: filesystem
    name: 文件系统工具
    command: npx
    args:
      - -y
      - "@modelcontextprotocol/server-filesystem"
      - "/tmp"
    enabled: true
    timeout: 10000
```

可选：在 `mcp_tools` 做细粒度开关或描述覆盖。

关键行为（当前实现）：

- MCP 初始化并行执行
- 单个 MCP 失败不阻塞 Agent 启动（降级运行）
- 失败连接会清理，避免资源残留

## 4. Skill 开发与 `load_level`

### 4.1 新建 Skill

在 `zero-agent/skills/examples/your_skill/` 放置 `SKILL.md`。

### 4.2 配置 Skill

在 `default_agent.yaml` 中追加：

```yaml
skills:
  - id: your_skill
    name: 你的技能
    path: skills/examples/your_skill
    enabled: true
    load_level: metadata
    priority: 80
```

### 4.3 `load_level` 选择建议

- `metadata`：只注入名称/描述，token 最省，适合默认上线
- `full`：注入完整 `SKILL.md`，适合功能验证
- `resources`：额外加载资源目录内容，适合重度任务场景

## 5. 本地联调与测试命令

## 5.1 启动服务

终端 A（Agent）：

```bash
cd zero-agent
source ../venv/bin/activate
python -m scripts.start
```

终端 B（Gateway）：

```bash
cd zero-gateway
make run
```

## 5.2 最小联调

```bash
# health
curl http://localhost:8080/health

# 创建会话
curl -X POST http://localhost:8080/api/v1/sessions -H "Content-Type: application/json" -d '{}'

# 非流式对话
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"sess_xxx","message":"计算 1+2","stream":false}'

# 流式对话（SSE）
curl -N -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"sess_xxx","message":"解释一下 LangGraph","stream":true}'
```

## 5.3 测试建议

- Python：在 `zero-agent/` 运行 `pytest`
- Go：在 `zero-gateway/` 运行 `go test ./...`
- 文档改动后，至少人工验证一条 API 示例可跑通

## 6. 常见坑（高频）

- **流式端点写错**：没有 `/api/v1/chat/stream`，统一用 `/api/v1/chat + stream=true`
- **会话不存在**：调用 chat 前请先创建 session
- **工具未生效**：确认 YAML 中 `enabled: true` 且模块路径可导入
- **MCP 启动失败**：不会阻塞服务启动，但对应工具不可用；请看降级日志
- **Skill 不生效**：检查 `path` 与 `load_level`；`metadata` 不会注入全文
- **网关无可用后端**：生产模式下请确认 Redis 服务发现配置正确

---

相关文档：

- `docs/architecture/overview.md`
- `docs/architecture/streaming.md`
- `docs/api/reference.md`
- `docs/api/examples.md`
