# 安装指南

## 方式一：使用pip安装（推荐）

### 1. 克隆项目
```bash
git clone https://github.com/your-repo/zero-agent.git
cd zero-agent
```

### 2. 创建虚拟环境
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows
```

### 3. 安装依赖
```bash
# 安装项目依赖
pip install -r requirements.txt

# 或安装开发版本（包含测试工具）
pip install -e .[dev]
```

### 4. 验证安装
```bash
# 检查安装是否成功
python -c "import api, tools, llm; print('安装成功！')"
```

## 方式二：使用Docker安装

### 使用Docker Compose（推荐）
```bash
# 克隆项目
git clone https://github.com/your-repo/zero-agent.git
cd zero-agent

# 启动服务
docker-compose -f docker/docker-compose.yml up --build
```

### 使用纯Docker
```bash
# 构建镜像
docker build -f docker/Dockerfile -t zero-agent .

# 运行容器
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="your-api-key" \
  zero-agent
```

## 方式三：开发环境安装

### 使用poetry（可选）
```bash
# 安装poetry
curl -sSL https://install.python-poetry.org | python3 -

# 安装依赖
poetry install

# 激活环境
poetry shell
```

### 使用conda
```bash
# 创建conda环境
conda create -n agent-mvp python=3.11
conda activate agent-mvp

# 安装依赖
pip install -r requirements.txt
```

## 依赖说明

### 核心依赖
- **fastapi**: Web框架
- **uvicorn**: ASGI服务器
- **pydantic**: 数据验证
- **langchain**: LLM集成
- **langgraph**: 状态管理
- **httpx**: HTTP客户端

### 可选依赖
- **pytest**: 测试框架
- **black**: 代码格式化
- **mypy**: 类型检查
- **structlog**: 结构化日志

## 环境变量配置

### 创建环境文件
```bash
# 复制环境模板
cp env.example .env

# 编辑环境变量
nano .env  # 或使用其他编辑器
```

### 必需的环境变量
```bash
# 选择一个LLM提供商
OPENAI_API_KEY=sk-your-key
# 或
ANTHROPIC_API_KEY=sk-ant-your-key
# 或
SILICONFLOW_API_KEY=your-key

# API配置
API_HOST=0.0.0.0
API_PORT=8080
```

## 验证安装

### 1. 检查Python包
```bash
python -c "
import fastapi
import langchain
import langgraph
print('所有核心依赖已安装')
"
```

### 2. 检查环境变量
```bash
# 验证API密钥设置
python -c "
import os
keys = ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'SILICONFLOW_API_KEY']
found = [k for k in keys if os.getenv(k)]
if found:
    print(f'找到API密钥: {found[0]}')
else:
    print('警告: 未找到任何API密钥')
"
```

### 3. 启动测试
```bash
# 尝试启动服务（会自动停止）
timeout 5 python -m scripts.start || echo "启动测试完成"
```

## 常见安装问题

### 网络问题
```bash
# 使用国内镜像
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

### 权限问题
```bash
# 使用用户级安装
pip install --user -r requirements.txt
```

### 依赖冲突
```bash
# 清理并重新安装
pip uninstall -y langchain langchain-core
pip install -r requirements.txt
```

### Docker问题
```bash
# 检查Docker版本
docker --version
docker-compose --version

# 清理Docker缓存
docker system prune -a
```

## 下一步

安装完成后，请继续：
- [配置指南](configuration.md)
- [快速开始](quick-start.md)
- [使用示例](examples.md)
