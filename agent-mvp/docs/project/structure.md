# 项目结构

基于分层架构设计，Universal Agent MVP 的项目结构如下：

```
agent-mvp/
├── llm/                    # 🧠 LLM层
│   ├── __init__.py
│   ├── base.py            # LLM提供商基础接口
│   ├── factory.py         # LLM工厂
│   ├── openai_provider.py # OpenAI提供商
│   ├── anthropic_provider.py # Anthropic提供商
│   └── siliconflow_provider.py # SiliconFlow提供商
├── tools/                  # 🔧 工具层
│   ├── __init__.py
│   ├── base.py            # 工具基础接口
│   ├── registry.py        # 工具注册器
│   ├── executor.py        # 工具执行器
│   └── calculator.py      # 计算器工具
├── orchestration/          # 🎭 编排层
│   ├── __init__.py
│   ├── state.py           # 状态管理
│   ├── workflow.py        # LangGraph工作流
│   └── agent.py           # 编排Agent
├── core/                   # 🎯 核心层
│   ├── __init__.py
│   └── agent.py           # UniversalAgent统一接口
├── config/                 # ⚙️ 配置层
│   ├── __init__.py
│   ├── models.py          # 数据模型
│   └── settings.py        # 配置管理
├── api/                    # 🌐 接口层
│   ├── __init__.py
│   └── app.py             # FastAPI应用
├── scripts/                # 🚀 启动脚本
│   ├── __init__.py
│   └── start.py           # 服务启动
├── tests/                  # 🧪 测试
│   └── __init__.py
├── docker/                 # 🐳 容器化
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/                   # 📚 文档
│   ├── README.md
│   ├── features.md
│   ├── tech-stack.md
│   ├── getting-started/
│   │   ├── requirements.md
│   │   ├── installation.md
│   │   ├── configuration.md
│   │   ├── quick-start.md
│   │   └── examples.md
│   ├── architecture/
│   │   ├── overview.md
│   │   └── layers.md
│   ├── api/
│   │   ├── reference.md
│   │   └── examples.md
│   ├── development/
│   │   ├── guide.md
│   │   ├── testing.md
│   │   └── deployment.md
│   └── project/
│       ├── structure.md
│       ├── roadmap.md
│       └── contributing.md
├── demo.py                 # 🎬 演示脚本
├── pyproject.toml          # 📦 项目配置
├── requirements.txt        # 📦 依赖列表
├── pyrightconfig.json      # 🔍 类型检查
├── Makefile                # 🛠️ 项目工具
└── README.md               # 📖 主文档
```

## 目录说明

### 核心代码层

#### `llm/` - LLM层
**职责**: 统一管理不同LLM提供商的集成
- `base.py`: LLM提供商的抽象基类，定义标准接口
- `factory.py`: 工厂模式实现，根据配置创建相应的LLM实例
- `*_provider.py`: 具体LLM提供商的实现类

**设计原则**:
- 插件化架构，支持轻松添加新的LLM提供商
- 统一的接口契约，屏蔽底层实现差异
- 工厂模式解耦创建逻辑

#### `tools/` - 工具层
**职责**: 管理工具的注册、发现和执行
- `base.py`: 工具的抽象基类
- `registry.py`: 工具注册中心，实现工具的注册和发现
- `executor.py`: 工具执行器，负责工具的实际调用
- `calculator.py`: 内置计算器工具的实现

**设计原则**:
- 工具插件化，支持动态加载和卸载
- 统一的工具接口，便于扩展
- 安全的执行环境，防止恶意代码执行

#### `orchestration/` - 编排层
**职责**: 管理对话流程和状态转换
- `state.py`: LangGraph状态定义，管理对话状态
- `workflow.py`: 基于LangGraph的工作流管理器
- `agent.py`: 编排Agent，协调各组件工作

**设计原则**:
- 状态机驱动，对话流程清晰可控
- 组件解耦，各司其职
- 流程编排灵活，支持复杂对话模式

#### `core/` - 核心层
**职责**: 提供统一的外部接口
- `agent.py`: UniversalAgent类，整合所有底层组件

**设计原则**:
- 外观模式，简化外部调用
- 接口稳定，保证向后兼容
- 依赖注入，便于测试

#### `config/` - 配置层
**职责**: 集中管理所有配置信息
- `models.py`: Pydantic数据模型定义
- `settings.py`: 配置加载和管理逻辑

**设计原则**:
- 配置验证，使用Pydantic进行类型检查
- 多环境支持，区分开发/测试/生产环境
- 配置热重载，支持运行时更新

#### `api/` - 接口层
**职责**: 提供REST API接口
- `app.py`: FastAPI应用，定义所有HTTP端点

**设计原则**:
- RESTful设计，标准的HTTP接口
- 自动文档生成，使用Swagger UI
- 中间件支持，添加认证、日志等功能

### 基础设施

#### `scripts/` - 启动脚本
- `start.py`: 应用启动脚本，包含环境检查和服务器启动

#### `tests/` - 测试
- 单元测试、集成测试、API测试和端到端测试
- 使用pytest框架，支持异步测试
- 包含测试fixtures和mock工具

#### `docker/` - 容器化
- `Dockerfile`: 应用容器化配置
- `docker-compose.yml`: 多容器编排配置

### 文档

#### `docs/` - 项目文档
完整的文档体系，包括：
- 用户指南：安装、配置、使用示例
- 架构文档：设计理念、分层说明
- API文档：接口规范、使用示例
- 开发指南：代码规范、测试策略、部署方案
- 项目文档：结构说明、路线图、贡献指南

## 文件命名约定

### Python文件
- 使用蛇形命名法（snake_case）
- 模块文件：`module_name.py`
- 包初始化：`__init__.py`
- 测试文件：`test_module_name.py`

### 配置文件
- Python配置：`pyproject.toml`, `setup.py`
- IDE配置：`.vscode/settings.json`, `pyrightconfig.json`
- Docker配置：`Dockerfile`, `docker-compose.yml`
- CI/CD配置：`.github/workflows/*.yml`

### 文档文件
- 使用连字符命名法（kebab-case）
- 主文档：`README.md`
- 分类文档：`category-name.md`
- 索引文档：`category/README.md`

## 依赖关系

### 内部依赖

```
api/
├── core/
│   ├── orchestration/
│   │   ├── tools/
│   │   ├── llm/
│   │   └── config/
│   └── config/
└── config/
```

### 外部依赖

**核心依赖**:
- `fastapi`: Web框架
- `langchain`: LLM集成
- `langgraph`: 状态管理
- `pydantic`: 数据验证

**工具依赖**:
- `uvicorn`: ASGI服务器
- `httpx`: HTTP客户端
- `python-dotenv`: 环境变量管理

**开发依赖**:
- `pytest`: 测试框架
- `black`: 代码格式化
- `mypy`: 类型检查

## 代码组织原则

### 1. 单一职责
每个模块只负责一个明确的功能，避免大而全的文件。

### 2. 依赖倒置
高层模块不依赖低层模块，通过抽象接口进行交互。

### 3. 开闭原则
对扩展开放，对修改封闭。新增功能不修改现有代码。

### 4. 接口隔离
为不同客户端提供专门的接口，避免接口污染。

### 5. 组合优于继承
优先使用组合和依赖注入，而不是复杂的继承关系。

## 扩展指南

### 添加新LLM提供商

1. 在 `llm/` 目录下创建新的提供商文件
2. 继承 `LLMProvider` 基类
3. 实现 `create_llm()` 和 `get_provider_name()` 方法
4. 在 `factory.py` 中注册新的提供商

### 添加新工具

1. 在 `tools/` 目录下创建新的工具文件
2. 继承 `Tool` 基类
3. 实现 `execute()` 方法
4. 在工具注册器中注册新工具

### 添加新API端点

1. 在 `api/app.py` 中添加新的路由
2. 使用适当的HTTP方法和路径
3. 添加请求/响应模型
4. 实现业务逻辑

### 添加新配置

1. 在 `config/models.py` 中添加新的配置模型
2. 在 `config/settings.py` 中添加加载逻辑
3. 更新环境变量和默认值
4. 在需要的地方注入配置

## 构建和部署

### 本地开发
```bash
# 安装依赖
pip install -e .[dev]

# 运行测试
pytest

# 启动服务
python -m scripts.start
```

### 生产部署
```bash
# 使用Docker
docker-compose -f docker/docker-compose.yml up --build

# 或直接部署
pip install -r requirements.txt
python -m scripts.start
```

## 质量保证

### 代码质量
- **类型检查**: 使用mypy进行静态类型检查
- **代码格式**: 使用black进行自动格式化
- **导入排序**: 使用isort保持导入顺序
- **代码检查**: 使用flake8检查代码质量

### 测试覆盖
- **单元测试**: 测试单个函数和类
- **集成测试**: 测试模块间的交互
- **API测试**: 测试HTTP接口
- **端到端测试**: 测试完整用户流程

### 持续集成
- **GitHub Actions**: 自动化测试和构建
- **代码覆盖率**: 使用codecov统计覆盖率
- **依赖检查**: 确保依赖安全和最新

这个项目结构提供了清晰的代码组织、易于维护的架构，以及支持快速开发和部署的基础设施。
