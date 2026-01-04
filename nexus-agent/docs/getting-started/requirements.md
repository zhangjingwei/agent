# 环境要求

## 系统要求

### 操作系统
- **Linux**: Ubuntu 20.04+, CentOS 7+, 或其他现代Linux发行版
- **macOS**: 10.15+ (Catalina或更高版本)
- **Windows**: Windows 10+ (通过WSL或原生支持)

### 硬件要求
- **CPU**: x86_64架构，建议2核心以上
- **内存**: 最低2GB，建议4GB以上
- **存储**: 最低1GB可用空间
- **网络**: 稳定的互联网连接（用于API调用）

## Python环境

### Python版本
- **最低版本**: Python 3.9.0
- **推荐版本**: Python 3.11+
- **支持版本**: Python 3.9, 3.10, 3.11, 3.12

### 包管理器
- **pip**: 20.0+ (通常随Python安装)
- **venv**: Python内置虚拟环境工具

### 环境管理工具（可选）
- **pyenv**: Python版本管理
- **conda**: Anaconda/Miniconda环境管理
- **poetry**: 现代Python依赖管理

## LLM API密钥

### 必需的API密钥
选择以下之一：

#### OpenAI
```bash
export OPENAI_API_KEY="sk-your-openai-api-key-here"
```
- 获取地址: [OpenAI API Keys](https://platform.openai.com/api-keys)
- 费用: 按使用量计费

#### Anthropic
```bash
export ANTHROPIC_API_KEY="sk-ant-your-anthropic-api-key-here"
```
- 获取地址: [Anthropic Console](https://console.anthropic.com/)
- 费用: 按使用量计费

#### SiliconFlow (推荐)
```bash
export SILICONFLOW_API_KEY="your-siliconflow-api-key-here"
```
- 获取地址: [SiliconFlow](https://siliconflow.cn/)
- 优势: 成本低，OpenAI兼容API
- 支持模型: DeepSeek, Qwen等

### API密钥验证
系统启动时会自动验证API密钥的有效性。

## 网络要求

### 出站连接
- **OpenAI**: `api.openai.com`
- **Anthropic**: `api.anthropic.com`
- **SiliconFlow**: `api.siliconflow.cn`

### 端口要求
- **开发模式**: 8080 (可配置)
- **生产模式**: 80/443 (通过反向代理)

## 开发环境工具（可选）

### IDE推荐
- **VS Code**: 最佳Python开发体验
- **PyCharm**: 专业Python IDE
- **Cursor**: AI辅助编程

### 版本控制
- **Git**: 2.0+
- **GitHub**: 代码托管和协作

### 容器化（可选）
- **Docker**: 20.0+
- **Docker Compose**: 2.0+

## 验证环境

### 检查Python版本
```bash
python3 --version
# 应该显示 3.9.0 或更高版本
```

### 检查pip版本
```bash
pip --version
# 应该显示 20.0+ 版本
```

### 测试API连接（可选）
```bash
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" | head -20
```

## 故障排除

### Python版本问题
```bash
# 使用pyenv安装特定Python版本
pyenv install 3.11.0
pyenv global 3.11.0
```

### 网络连接问题
```bash
# 测试网络连接
ping api.openai.com
curl -I https://api.openai.com
```

### API密钥问题
```bash
# 验证环境变量设置
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
echo $SILICONFLOW_API_KEY
```

## 下一步

环境准备完成后，请继续阅读：
- [安装指南](installation.md)
- [快速配置](configuration.md)
- [运行服务](quick-start.md)
