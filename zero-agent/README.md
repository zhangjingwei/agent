# Zero Agent

一个面向生产演进的通用 Agent 核心服务，提供对话编排、工具调用（含 MCP）与 Skill 能力扩展。

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)

## 🔍 项目特点

- **编排驱动**: 基于 LangGraph 的状态流编排，支持多步骤任务执行
- **工具生态集成**: 统一接入内置工具与 MCP 工具，便于能力扩展
- **MCP 降级容错**: 外部 MCP 服务异常时不阻塞核心启动，可降级运行
- **Skill 分级加载**: 支持 `metadata/full/resources`，按成本与效果灵活配置
- **流式交互**: 支持 SSE 流式响应，便于前端实时展示推理过程
- **可运维性**: 结构化日志、健康检查与服务注册机制，便于生产部署

## 🚀 快速开始

- [环境要求](docs/getting-started/requirements.md)
- [安装指南](docs/getting-started/installation.md)
- [快速配置](docs/getting-started/configuration.md)
- [运行服务](docs/getting-started/quick-start.md)
- [使用示例](docs/getting-started/examples.md)

## 📚 完整文档

### 🏗️ 架构设计
- [整体架构](docs/architecture/overview.md) - 系统架构设计和分层说明
- [各层职责](docs/architecture/layers.md) - 详细的层级职责说明

### 🔌 API接口
- [API参考](docs/api/reference.md) - REST API接口文档
- [API示例](docs/api/examples.md) - API调用示例

### 💻 开发指南
- [开发指南](docs/development/guide.md) - 添加工具和扩展能力
- [测试](docs/development/testing.md) - 测试指南
- [部署](docs/development/deployment.md) - 部署方式

### 📋 项目信息
- [项目结构](docs/project/structure.md) - 代码组织结构
- [贡献指南](docs/project/contributing.md) - 如何贡献代码

### 📖 其他文档
- [功能特性](docs/features.md) - 核心能力说明
- [技术栈](docs/tech-stack.md) - 使用的技术和工具

## ✨ 核心特性

- 🧠 **LangGraph驱动**: 基于状态图的Agent编排引擎
- 🔧 **工具集成**: 支持LangChain和自定义工具
- 🧩 **MCP容错**: MCP服务不可用时自动降级，保证核心服务可用
- 🌐 **REST API**: 标准HTTP接口，支持多语言客户端
- 📦 **模块化设计**: 分层架构，易于扩展和维护
- 🐳 **容器化**: Docker原生支持
- 📊 **可观测性**: 结构化日志和监控


## 🎯 支持的LLM

- OpenAI GPT-4 / GPT-3.5
- Anthropic Claude
- SiliconFlow (兼容OpenAI API)

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](../LICENSE) 文件了解详情。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！请查看[贡献指南](docs/project/contributing.md)了解详细信息。

---

⭐ 如果这个项目对你有帮助，请给我们一个star！
