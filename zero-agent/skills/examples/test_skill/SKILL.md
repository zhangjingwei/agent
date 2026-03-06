---
name: 测试技能
description: 这是一个用于测试和调试 Skill 系统的示例技能，展示 Skill 的基本功能和用法
version: 1.0.0
author: Zero Agent Team
tags: [test, debug, example, skill-system]
required_tools: [calculator]
examples:
  - "测试 Skill 系统是否正常工作"
  - "验证渐进式加载机制"
  - "检查 Skill 上下文注入功能"
---

# 测试技能

这是一个用于测试和调试 Skill 系统的示例技能。

## 功能说明

本技能主要用于：
1. **系统测试**：验证 Skill 系统是否正常工作
2. **调试辅助**：帮助开发者理解 Skill 系统的工作机制
3. **示例参考**：作为创建新 Skill 的参考模板

## 使用场景

当你需要：
- 测试 Skill 加载功能
- 验证 Skill 上下文是否正确注入到 LLM
- 调试渐进式加载机制
- 查看 Skill 系统的工作流程

可以使用本技能进行测试。

## 测试步骤

### 1. 基础测试
- 检查 Skill 是否能够正确加载
- 验证元数据解析是否正常
- 确认 Skill 注册到系统中

### 2. 加载级别测试
- **Level 1 (metadata)**：仅加载名称和描述，Token 消耗最小
- **Level 2 (full)**：加载完整 Markdown 内容
- **Level 3 (resources)**：加载所有资源文件

### 3. 上下文注入测试
- 验证 Skill 上下文是否正确注入到 LLM
- 检查不同加载级别下的上下文内容
- 确认多个 Skill 的合并注入

## 工具使用

本技能依赖以下工具：
- **calculator**：用于执行测试计算，验证工具调用功能

## 测试用例

### 用例 1：基础功能测试
```
用户：请使用测试技能进行基础功能测试
期望：Agent 能够识别并使用本技能
```

### 用例 2：工具调用测试
```
用户：使用计算器计算 2 + 2
期望：Agent 能够调用 calculator 工具并返回结果
```

### 用例 3：上下文理解测试
```
用户：根据测试技能，我应该如何验证系统？
期望：Agent 能够根据技能内容提供指导
```

## 调试信息

### 日志检查点
- Skill 加载日志：`logger.info(f"成功加载 Skill: {config.id}")`
- 上下文注入日志：`logger.debug(f"消息总数: ... Skill上下文: {len(skill_messages)})`
- 元数据解析日志：`logger.debug(f"加载 Skill 元数据: {skill_path}")`

### 常见问题

1. **Skill 未加载**
   - 检查配置文件中的路径是否正确
   - 确认 SKILL.md 文件存在
   - 验证 YAML frontmatter 格式是否正确

2. **上下文未注入**
   - 检查 Skill 是否启用（enabled: true）
   - 确认 load_level 配置正确
   - 查看日志中的 Skill 加载信息

3. **元数据解析失败**
   - 验证 YAML 格式是否正确
   - 检查必需字段（name, description）是否存在
   - 确认文件编码为 UTF-8

## 最佳实践

1. **开发阶段**：使用 `load_level: metadata` 降低 Token 消耗
2. **测试阶段**：使用 `load_level: full` 查看完整内容
3. **生产环境**：根据实际需求选择合适的加载级别

## 版本历史

- **v1.0.0** (2024-03-07): 初始版本，用于系统测试和调试
