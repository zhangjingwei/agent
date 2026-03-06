# Test Agent Baseline

用于 Zero Agent 的基准测试命令集。

## 启动前必做（代码扫描 + 文档增量更新）

每次启动前先做一次代码扫描，若发现新增能力或行为变更，必须补充基准测试并更新本文件。

推荐最小扫描命令（在项目根目录执行）：

```bash
cd /mnt/d/workspace/prodject/zero-agent
rg -n "@app\\.(get|post)|/agents|/health|/tools|stream|StreamChunk|function_call|message_history" api orchestration config filters
```

扫描后按以下规则更新：
- 新增接口：补充对应 curl 用例（成功 + 至少 1 个错误分支）
- 新增响应结构字段：补充字段断言（尤其是 `tools`、SSE chunk、OpenAI 兼容结构）
- 新增可降级能力（如 MCP/外部依赖）：补充“失败不阻断”验证
- 现有行为变更：更新“当前已知行为”和“通过标准（Checklist）”

## 0. 当前能力扫描（基于代码）

### API 能力
- `GET /`（版本/服务信息）
- `GET /health`
- `GET /agents`
- `GET /agents/{agent_id}/tools`
- `POST /agents/{agent_id}/chat`（支持 `?stream=true`）

### 核心 Agent 能力
- 多 Agent 配置加载（目录方式）
- LLM 调用 + 工具调用（LangGraph 工作流）
- 并发工具执行（可控并发）
- 超时控制（LLM/Tool/Workflow）
- 熔断与限流重试（429 退避）
- Skill 系统（metadata/full/resources）
- MCP 工具集成（失败可降级）

### 当前已知行为（用于测试时解释）
- Skill 上下文注入已在流式与非流式链路保持一致（均可验证）
- MCP 下线/超时不应阻断服务启动
- MCP 初始化按“单服务超时 + 总体降级”处理，失败服务会输出汇总告警日志
- 输入过滤器存在“GET 请求直接放行”的逻辑分支
- 流式输出为 SSE，自定义 chunk，`type` 可能为 `content/tool_call_start/tool_call_end/error/done`
- `session_id` 为必需字段（流式与非流式均适用，缺失应返回 400）
- `/agents/{agent_id}/tools` 会返回 `type/parameters`，MCP 工具额外包含 `server_id/server_name`

## 1. 测试目标

- 验证服务可用性
- 验证 Agent/Tool/Skill 是否按配置加载
- 验证非流式与流式能力
- 验证 MCP 失败容错
- 作为每次改造后的回归基线

## 2. 前置条件

1. 服务已启动（默认 `http://localhost:8082`）
2. 默认 Agent 为 `zero`
3. `default_agent.yaml` 中启用 Skill（如 `test_skill`、`data_analysis`）
4. 推荐安装 `jq`（可选）

## 3. 快速冒烟（Smoke）

### 3.0 根路径
```bash
curl -s http://localhost:8082/
```

期望：
- 返回 JSON
- 包含 `message`、`version`

### 3.1 健康检查
```bash
curl -s http://localhost:8082/health
```

期望：
- 返回 JSON
- `status = healthy`

### 3.2 Agent 列表
```bash
curl -s http://localhost:8082/agents
```

期望：
- 包含 `zero`

### 3.3 工具列表
```bash
curl -s http://localhost:8082/agents/zero/tools
```

期望：
- 至少包含 `calculator`
- `calculator.type = builtin`
- 每个工具包含 `parameters`
- MCP 失败时允许无 MCP 工具

## 4. Skill 链路测试（重点）

### 4.1 Skill 生效（流式）
```bash
curl -N -X POST "http://localhost:8082/agents/zero/chat?stream=true" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "skill-baseline-001",
    "message": "根据测试技能，我应该如何验证 Skill 系统是否正常？请给我分步骤检查清单。",
    "metadata": {}
  }'
```

期望：
- SSE 输出（`data: ...`）
- 内容明显体现 Skill 语义（测试步骤、检查点、加载级别、上下文注入）

### 4.2 Skill + Tool 联合
```bash
curl -N -X POST "http://localhost:8082/agents/zero/chat?stream=true" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "skill-baseline-002",
    "message": "请按测试技能流程，先说明检查点，再调用计算器算 2+2。",
    "metadata": {}
  }'
```

期望：
- 先输出 Skill 指导
- 然后给出计算结果 `4`

### 4.3 带历史消息的 Skill 连续对话
```bash
curl -N -X POST "http://localhost:8082/agents/zero/chat?stream=true" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "skill-baseline-003",
    "message": "继续，给我最终验收标准。",
    "metadata": {},
    "message_history": [
      {"role":"user","content":"我们在做 Skill 系统测试"},
      {"role":"assistant","content":"好的，我会按测试技能给你步骤"}
    ]
  }'
```

期望：
- 能连续理解上下文
- 输出仍带 Skill 语义

### 4.4 流式错误分支（缺少 session_id）
```bash
curl -s -X POST "http://localhost:8082/agents/zero/chat?stream=true" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "metadata": {}
  }'
```

期望：
- HTTP `400` 或 `422`
- 返回错误信息包含 `session_id`

## 5. 非流式功能回归

### 5.1 基础计算
```bash
curl -s -X POST "http://localhost:8082/agents/zero/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "skill-baseline-004",
    "message": "计算 123 * 456",
    "metadata": {}
  }'
```

期望：
- 返回 JSON（OpenAI 兼容结构）
- 内容包含 `56088`
- 包含 `choices[0].message.role = assistant`
- 无工具调用时 `choices[0].finish_reason = stop`

### 5.4 非流式 Skill 生效
```bash
curl -s -X POST "http://localhost:8082/agents/zero/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "skill-baseline-006",
    "message": "根据测试技能，给我一份 Skill 系统验收清单（非流式回答）。",
    "metadata": {}
  }'
```

期望：
- 返回 JSON（OpenAI 兼容结构）
- 回答体现 Skill 语义（如测试步骤、检查点、验收标准）
- 可与 4.1 流式结果形成一致语义（非逐字一致）

### 5.2 错误请求（缺少 session_id）
```bash
curl -s -X POST "http://localhost:8082/agents/zero/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "metadata": {}
  }'
```

期望：
- 400 或 422（请求校验失败）

### 5.3 不存在的 Agent
```bash
curl -s -X POST "http://localhost:8082/agents/not-exists/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "skill-baseline-005",
    "message": "hello",
    "metadata": {}
  }'
```

期望：
- 404，错误信息包含 agent not found

## 6. MCP 容错测试（下线场景）

观察启动日志关键点：
- 允许：`连接MCP服务器失败 ...`
- 允许：`连接MCP服务器失败 ... 初始化超时（>...s）`
- 允许：`MCP服务器 ... 的工具将不可用`
- 允许：`MCP降级运行，以下服务器不可用: ...`
- 必须：`Agent zero 初始化完成`
- 必须：`Running on http://0.0.0.0:8082`

补充验证：
```bash
curl -s http://localhost:8082/agents/zero/tools
```

期望：
- 即使 MCP 失败，`calculator` 仍可用

继续验证服务可对话（MCP 下线不阻断核心链路）：
```bash
curl -s -X POST "http://localhost:8082/agents/zero/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "mcp-fallback-chat-001",
    "message": "在 MCP 下线时，使用内置计算器计算 9*9。",
    "metadata": {}
  }'
```

期望：
- 返回 200
- 返回 JSON（OpenAI 兼容结构）
- 内容包含 `81`

## 7. 并发与稳定性（轻量）

### 7.1 并发 5 请求
```bash
for i in 1 2 3 4 5; do
  curl -s -X POST "http://localhost:8082/agents/zero/chat" \
    -H "Content-Type: application/json" \
    -d "{\"session_id\":\"skill-concurrent-$i\",\"message\":\"计算 $i * $i\",\"metadata\":{}}" &
done
wait
```

期望：
- 无明显报错
- 请求能返回结果

## 8. 日志断言（建议）

启动日志中建议检查：
- `成功加载 Skill: test_skill`
- `成功加载 Skill: data_analysis`
- `开始并行初始化 ... MCP 服务器`
- `MCP 服务器初始化完成: ...`

对话日志中建议检查：
- `消息总数 ... Skill上下文 ...`（流式）
- 工具调用日志（如 calculator）
- MCP 降级摘要日志（如 `MCP 以降级模式运行...` / `MCP降级运行...`）

## 9. 通过标准（Checklist）

- [ ] `/` 正常（3.0）
- [ ] `/health` 正常
- [ ] `/agents` 返回 `zero`
- [ ] `/agents/zero/tools` 至少有 `calculator` 且结构字段完整
- [ ] Skill 流式测试通过（4.1）
- [ ] Skill+Tool 联合测试通过（4.2）
- [ ] 历史消息测试通过（4.3）
- [ ] 流式缺少 `session_id` 返回 400/422（4.4）
- [ ] 非流式基础计算通过（5.1）
- [ ] 非流式 Skill 生效通过（5.4）
- [ ] 错误请求返回正确状态码（5.2/5.3）
- [ ] MCP 失败时服务仍可启动并可对话（6）
- [ ] MCP 失败时日志包含超时/降级摘要关键字（6/8）
- [ ] 轻量并发测试通过（7.1）

## 10. 常见问题

1. `{"detail":"Not Found"}`
- 路径写错了（本项目无 `/api/v1` 前缀）
- 正确路径：`/agents/{agent_id}/chat`

2. Skill 看起来没生效
- 确认启动日志中有 `成功加载 Skill`
- 优先使用 `stream=true` 验证

3. MCP 超时卡住
- 检查 `default_agent.yaml` 的 `timeout`（建议 10000ms）
- MCP 下线可临时 `enabled: false`

4. curl 在 PowerShell 报管道错误
- 建议在 WSL/bash 执行
- 或改用 `Invoke-WebRequest`

