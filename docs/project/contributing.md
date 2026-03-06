# 贡献指南

本文档是 Zero Agent 的**唯一贡献规范源**。  
详细开发实践请配合 `docs/development/guide.md` 使用。

## 1. 贡献范围

欢迎以下贡献：

- Bug 修复
- 新功能与重构
- 文档改进
- 测试补充与稳定性提升

## 2. 分支策略（默认 `master`）

- 默认分支：`master`
- 功能分支：`feature/<short-name>`
- 修复分支：`fix/<short-name>`
- 文档分支：`docs/<short-name>`

创建分支示例：

```bash
git checkout master
git pull origin master
git checkout -b feature/your-feature
```

## 3. 标准提交流程（Fork / Branch / PR）

1. Fork 仓库并克隆到本地
2. 基于 `master` 创建分支
3. 完成代码与文档改动
4. 本地通过最小检查（见下文）
5. 提交并推送分支
6. 发起 Pull Request

PR 描述建议包含：

- 变更内容（做了什么）
- 变更原因（为什么做）
- 验证方式（怎么测）
- 风险与回滚点（如有）

## 4. 提交规范（Conventional Commits）

提交信息格式：

```text
<type>(optional-scope): <description>
```

常用 `type`：

- `feat`：新功能
- `fix`：问题修复
- `docs`：文档变更
- `refactor`：重构（无行为变化）
- `test`：测试相关
- `chore`：构建或杂项维护

示例：

```text
feat(agent): add MCP degraded startup handling
fix(gateway): normalize chat error response
docs(api): update streaming examples
```

## 5. 最小检查清单（提交前）

至少确保：

- [ ] 代码能正常运行（本地启动通过）
- [ ] 相关测试通过（Python/Go 受影响部分）
- [ ] 新增或变更能力已更新文档
- [ ] 无明显调试残留（临时日志、无用注释、硬编码密钥）

推荐命令（按改动范围执行）：

```bash
# Python
cd zero-agent && pytest

# Go
cd zero-gateway && go test ./...
```

## 6. 文档变更约定

- 文档必须与当前实现一致，避免“未来态描述”
- API 变更需同时更新：
  - `docs/api/reference.md`
  - `docs/api/examples.md`
- 架构相关变更需同步：
  - `docs/architecture/overview.md`
  - `docs/architecture/streaming.md`（若涉及流式）

## 7. 行为准则（简版）

我们承诺维护友好、尊重、包容的协作环境：

- 尊重不同背景与观点
- 聚焦问题本身，避免人身攻击
- 以建设性方式给出反馈

维护者可对不当内容进行编辑、隐藏或拒绝合并。

## 8. 沟通与支持

- 技术问题与缺陷：GitHub Issues
- 方案讨论与提案：Pull Request / Discussions

若不确定改动方向，建议先开 Issue 或 Draft PR 对齐方案。

---

感谢你的贡献，欢迎持续改进 Zero Agent。
