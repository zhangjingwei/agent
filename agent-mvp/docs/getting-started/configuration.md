# 配置指南

## 环境变量配置

### LLM配置

#### OpenAI配置
```bash
# OpenAI API密钥
OPENAI_API_KEY=sk-your-openai-api-key-here

# 模型配置（可选）
LLM_MODEL=gpt-4
```

#### Anthropic配置
```bash
# Anthropic API密钥
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here

# 模型配置（可选）
LLM_MODEL=claude-3-sonnet-20240229
```

#### SiliconFlow配置（推荐）
```bash
# SiliconFlow API密钥
SILICONFLOW_API_KEY=your-siliconflow-api-key-here

# 模型配置
LLM_MODEL=deepseek-ai/DeepSeek-V2.5
```

### API服务器配置

```bash
# 服务器主机
API_HOST=0.0.0.0

# 服务器端口
API_PORT=8080

# 环境模式
ENVIRONMENT=development  # development/production
```

### 工具配置

```bash
# 天气API（可选）
WEATHER_API_KEY=your-weather-api-key

# 其他工具API密钥
# 根据需要添加
```

### 日志配置

```bash
# 日志级别
LOG_LEVEL=INFO  # DEBUG/INFO/WARNING/ERROR

# 日志格式
LOG_FORMAT=json  # json/text
```

### 会话配置

```bash
# 会话超时时间（小时）
SESSION_TIMEOUT_HOURS=24

# 最大会话数量
MAX_SESSIONS=1000
```

### 环境变量未生效
```bash
# 检查当前环境变量
env | grep -E "(API_KEY|LLM|API_)" | sort

# 重新加载环境
source .env
```

### Docker配置问题
```bash
# 检查容器日志
docker logs universal-agent-mvp

# 验证环境变量传递
docker exec universal-agent-mvp env | grep API_KEY
```

## 下一步

配置完成后，请继续：
- [快速开始](quick-start.md)
- [使用示例](examples.md)
- [API文档](../api/reference.md)
