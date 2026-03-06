# Zero Agent - AI Agent 核心实现

基于 Python 和 LangGraph 的高性能 AI Agent 实现，提供完整的 Agent 推理、工具调用、技能管理和工作流编排能力。

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)

## 🚀 快速开始

- [环境要求](getting-started/requirements.md) - Python 3.9+、依赖包安装要求
- [安装指南](getting-started/installation.md) - 详细的安装步骤和环境配置
- [快速配置](getting-started/configuration.md) - LLM API密钥、Agent配置等
- [运行服务](getting-started/quick-start.md) - 启动Agent服务的多种方式（注意：文档中部分路径可能需要更新为 `zero-agent`）
- [使用示例](getting-started/examples.md) - API调用示例和代码片段

## 📚 文档目录

### 🏗️ 架构设计
- [整体架构](architecture/overview.md) - Agent系统架构设计和分层说明（注意：文档中包含Gateway相关内容，请关注Agent部分）
- [各层职责](architecture/layers.md) - 详细的层级职责说明，包括Core、Orchestration、Tools、Skills等各层
- [流式响应](architecture/streaming.md) - SSE流式输出的实现机制

### 🔌 API接口
- [API参考](api/reference.md) - 完整的REST API接口文档，包括请求/响应格式
- [API示例](api/examples.md) - 实际API调用示例代码

### 💻 开发指南
- [开发指南](development/guide.md) - 如何添加工具、Skill和扩展Agent能力（注意：文档中部分路径可能需要更新）
- [测试](development/testing.md) - 单元测试和集成测试指南
- [部署](development/deployment.md) - Agent服务的部署方式

### 📋 项目信息
- [项目结构](project/structure.md) - 代码组织结构和目录说明
- [贡献指南](project/contributing.md) - 如何贡献代码和参与开发

### 📖 其他文档
- [功能特性](features.md) - **需要更新**：部分内容已过时，实际已支持MCP、Skill系统等功能
- [技术栈](tech-stack.md) - 使用的核心技术栈和依赖库说明
- [MCP集成](mcp-integration.md) - MCP协议集成的详细说明

## ✨ 核心特性

### AI 推理引擎
- 🧠 **LangGraph 工作流**: 基于状态图的 Agent 编排引擎，支持复杂的多步骤推理流程
- 🌐 **多 LLM 支持**: 支持 OpenAI、Anthropic、SiliconFlow 等多种 LLM 提供商
- 📡 **流式响应**: 支持 Server-Sent Events (SSE) 流式输出，实时返回推理结果
- ⚡ **异步处理**: 基于 FastAPI 和 Hypercorn，支持高并发异步请求处理

### 工具系统
- 🔧 **内置工具**: 支持自定义 Python 工具（函数/类），灵活扩展能力
- 🔌 **MCP 集成**: 支持 Model Context Protocol，可集成丰富的 MCP 工具生态
- ⚙️ **工具执行器**: 支持并发工具执行，自动错误处理和结果格式化
- 📦 **工具管理**: 统一的工具注册、发现和管理机制

### Skill 系统
- 🎯 **渐进式加载**: 三层加载机制（metadata/full/resources），优化 Token 消耗
- 📝 **SKILL.md 格式**: 支持 YAML frontmatter + Markdown 正文的标准格式
- 🔄 **上下文注入**: 自动将 Skill 上下文注入到 LLM，提供任务级指导
- 🗂️ **资源管理**: 支持 scripts/、references/、assets/ 等资源文件

### 工作流编排
- 🔄 **状态管理**: 基于 LangGraph 的状态图，支持复杂对话流程
- 🔁 **迭代控制**: 支持最大迭代次数限制，防止无限循环
- ⚡ **并发执行**: 支持多个工具的并发执行，提升响应速度
- 🛡️ **错误处理**: 完善的错误处理和重试机制

### 企业级特性
- 🛡️ **熔断器**: LLM 调用的自动故障检测和恢复机制
- 📊 **可观测性**: 结构化日志、性能监控、健康检查
- 🔒 **过滤器系统**: 输入验证、输出处理、审计日志等中间件
- 💾 **资源管理**: 全局资源管理器，控制并发和资源使用

## 🎯 支持的LLM

- **OpenAI**: GPT-4, GPT-4o, GPT-3.5-turbo 等
- **Anthropic**: Claude 3 (Opus, Sonnet, Haiku)
- **SiliconFlow**: 兼容OpenAI API的国内LLM服务

## 🏗️ Agent 实现架构

Zero Agent 采用分层架构设计，各层职责清晰，易于扩展和维护：

```
┌─────────────────────────────────────────┐
│         API 层 (FastAPI)                │
│  • RESTful API 接口                     │
│  • 流式响应 (SSE)                       │
│  • 会话管理                             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     核心层 (Core)                        │
│  • ZeroAgentEngine: Agent 核心接口      │
│  • AgentFactory: 工厂模式管理            │
│  • CircuitBreaker: LLM 熔断保护         │
│  • ResourceManager: 全局资源管理         │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     编排层 (Orchestration)              │
│  • OrchestratorAgent: 编排协调          │
│  • WorkflowManager: LangGraph 工作流    │
│  • AgentState: 状态管理                 │
└──────┬───────────────────┬──────────────┘
       │                   │
┌──────▼──────────┐  ┌─────▼─────────────┐
│   工具层        │  │   技能层           │
│  (Tools)        │  │  (Skills)          │
│                 │  │                    │
│ • ToolRegistry  │  │ • SkillRegistry    │
│ • ToolManager   │  │ • SkillManager     │
│ • ToolExecutor  │  │ • SkillLoader      │
│ • MCP Client    │  │ • SkillParser      │
└─────────────────┘  └────────────────────┘
       │                   │
       └──────────┬─────────┘
                  │
       ┌──────────▼──────────┐
       │    LLM 层          │
       │  • OpenAI Provider │
       │  • Anthropic       │
       │  • SiliconFlow     │
       └────────────────────┘
```

### 核心层（Core）

**ZeroAgentEngine**: Agent 核心接口
- 统一管理 Agent 生命周期
- 提供对话和流式对话接口
- 封装 OrchestratorAgent

**AgentFactory**: Agent 工厂
- 支持多 Agent 实例管理
- 从配置创建 Agent 实例

**CircuitBreaker**: 熔断器
- 保护 LLM 调用，防止级联故障
- 自动故障检测和恢复

**ResourceManager**: 资源管理器
- 全局线程池管理
- 并发控制（工具执行、LLM 调用）

### 编排层（Orchestration）

**OrchestratorAgent**: 编排 Agent
- 协调 LLM、工具、Skill 等组件
- 管理 Agent 初始化流程
- 处理对话请求和响应

**WorkflowManager**: 工作流管理器
- 基于 LangGraph 的状态图
- 节点：接收消息 → 调用 LLM → 执行工具 → 响应
- 支持迭代控制和错误处理

**AgentState**: 状态管理
- 维护消息历史
- 跟踪工具调用
- 管理迭代计数和错误信息

### 工具层（Tools）

**ToolRegistry**: 工具注册器
- 注册和查询工具
- 转换为 LangChain 工具格式

**ToolManager**: 工具管理器
- 从配置创建工具实例
- 支持函数工具和类工具
- 管理 MCP 工具集成

**ToolExecutor**: 工具执行器
- 执行工具调用
- 支持并发执行
- 错误处理和结果格式化

**MCP Client**: MCP 协议客户端
- 连接 MCP 服务器
- 发现和调用 MCP 工具
- 管理 MCP 连接生命周期

### 技能层（Skills）

**SkillRegistry**: Skill 注册器
- 注册和查询 Skill
- 按优先级排序

**SkillManager**: Skill 管理器
- 从配置加载 Skill
- 管理 Skill 生命周期
- 设置 Skill 基础路径

**SkillLoader**: 渐进式加载器
- Level 1: 仅加载元数据（< 100 tokens）
- Level 2: 加载完整内容（< 1000 tokens）
- Level 3: 加载所有资源文件
- 实现缓存机制

**SkillParser**: SKILL.md 解析器
- 解析 YAML frontmatter
- 提取 Markdown 正文
- 扫描资源文件

### LLM 层

**BaseLLMProvider**: LLM 提供商基类
- 统一的 LLM 接口
- 支持异步调用

**OpenAI Provider**: OpenAI 集成
- GPT-4, GPT-4o, GPT-3.5-turbo 等

**Anthropic Provider**: Anthropic 集成
- Claude 3 (Opus, Sonnet, Haiku)

**SiliconFlow Provider**: SiliconFlow 集成
- 兼容 OpenAI API 的国内服务

### 配置层（Config）

**Config Loader**: 配置加载器
- 加载 YAML 配置文件
- 支持环境变量替换

**Config Models**: 数据模型
- 使用 Pydantic 定义
- 类型验证和默认值

**Config Validator**: 配置验证器
- 验证配置完整性
- 检查必需字段

### API 层（API）

**FastAPI 应用**: RESTful API
- 标准 HTTP 接口
- 自动 API 文档生成

**流式响应**: SSE 支持
- 实时返回推理结果
- 支持工具调用事件流

**会话管理**: 会话接口
- 创建和管理会话
- 维护会话状态

## 📖 关键实现细节

### 工作流执行流程

1. **接收消息** → 转换消息历史为LangChain格式
2. **注入Skill上下文** → 根据加载级别注入Skill指导
3. **调用LLM** → 使用绑定了工具的LLM进行推理
4. **执行工具** → 并发执行LLM返回的工具调用
5. **迭代判断** → 根据结果决定是否继续迭代
6. **返回响应** → 提取最终响应和工具调用结果

### Skill上下文注入机制

- **Level 1 (metadata)**: 仅注入Skill名称和描述，Token消耗最小（< 100 tokens）
- **Level 2 (full)**: 注入完整的SKILL.md内容，提供详细指导（< 1000 tokens）
- **Level 3 (resources)**: 注入所有资源文件，包含脚本和参考资料

### 工具执行机制

- **并发执行**: 支持多个工具同时执行，提升响应速度
- **错误处理**: 工具执行失败不影响其他工具，错误信息返回给LLM
- **超时控制**: 每个工具执行都有超时限制，防止阻塞

### 熔断器保护

- **自动熔断**: LLM调用连续失败5次后自动熔断
- **自动恢复**: 熔断60秒后尝试恢复，半开状态下2次成功即恢复
- **速率限制**: 自动处理429错误，支持指数退避重试

详细架构说明请参考 [架构设计文档](architecture/overview.md)（注意：该文档包含Gateway相关内容，请关注Agent部分）。

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](../LICENSE) 文件了解详情。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！请查看[贡献指南](project/contributing.md)了解详细信息。

---

⭐ 如果这个项目对你有帮助，请给我们一个star！
