# 各层职责详解

## 🧠 LLM层 (LLM Layer)

### 核心职责

LLM层是整个系统的AI能力基础，负责统一管理不同LLM提供商的集成和调用。

### 架构组件

#### 1. LLMProvider (基础接口)

```python
class LLMProvider(ABC):
    """LLM提供商基础接口"""

    def __init__(self, api_key: str, model: str, **kwargs):
        self.api_key = api_key
        self.model = model
        self.config = kwargs

    @abstractmethod
    def create_llm(self) -> Runnable:
        """创建LLM实例"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """获取提供商名称"""
        pass

    def validate_config(self) -> bool:
        """验证配置"""
        return bool(self.api_key and self.model)
```

**职责**:
- 定义统一的LLM创建接口
- 提供配置验证机制
- 封装提供商特定的初始化逻辑

#### 2. LLMFactory (工厂模式)

```python
class LLMFactory:
    """LLM工厂类"""

    _providers = {
        'openai': OpenAIProvider,
        'anthropic': AnthropicProvider,
        'siliconflow': SiliconFlowProvider
    }

    @classmethod
    def create_llm(cls, provider: str, api_key: str, model: str, **config) -> Runnable:
        """创建LLM实例"""
        if provider not in cls._providers:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        provider_class = cls._providers[provider]
        llm_provider = provider_class(api_key=api_key, model=model, **config)

        if not llm_provider.validate_config():
            raise ValueError(f"Invalid configuration for provider: {provider}")

        return llm_provider.create_llm()
```

**职责**:
- 集中管理所有LLM提供商
- 根据配置创建对应的LLM实例
- 支持动态注册新的提供商

#### 3. 具体提供商实现

**OpenAIProvider**:
```python
class OpenAIProvider(LLMProvider):
    def create_llm(self) -> Runnable:
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=self.config.get('temperature', 0.7)
        )
```

**SiliconFlowProvider**:
```python
class SiliconFlowProvider(LLMProvider):
    def create_llm(self) -> Runnable:
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=self.config.get('temperature', 0.7),
            base_url="https://api.siliconflow.cn/v1"  # 自定义端点
        )
```

### 设计优势

1. **统一接口**: 所有LLM提供商使用相同的调用方式
2. **易于扩展**: 添加新提供商只需实现LLMProvider接口
3. **配置集中**: API密钥和参数统一管理
4. **错误隔离**: 提供商特定的错误被抽象层屏蔽

### 使用示例

```python
from llm.factory import LLMFactory

# 创建OpenAI LLM
openai_llm = LLMFactory.create_llm(
    provider="openai",
    api_key="sk-...",
    model="gpt-4"
)

# 创建SiliconFlow LLM
siliconflow_llm = LLMFactory.create_llm(
    provider="siliconflow",
    api_key="sk-...",
    model="deepseek-ai/DeepSeek-V2.5"
)

# 统一的使用方式
response = await llm.invoke([HumanMessage(content="Hello!")])
```

---

## 🔧 工具层 (Tools Layer)

### 核心职责

工具层管理Agent可用的外部能力，包括工具的注册、发现和执行。

### 架构组件

#### 1. Tool (基础接口)

```python
class Tool(ABC):
    """工具基础类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        pass

    def to_langchain_tool(self):
        """转换为LangChain工具"""
        async def tool_func(**kwargs):
            return await self.execute(**kwargs)

        tool_func.__name__ = self.name
        tool_func.__doc__ = self.description

        return tool(tool_func)
```

#### 2. ToolRegistry (注册器)

```python
class ToolRegistry:
    """工具注册器"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def get_langchain_tools(self) -> List[Any]:
        """获取所有LangChain工具"""
        return [tool.langchain_tool for tool in self._tools.values()]
```

#### 3. ToolExecutor (执行器)

```python
class ToolExecutor:
    """工具执行器"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具"""
        tool = self.registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        return await tool.execute(**arguments)
```

### 内置工具示例

```python
class CalculatorTool(Tool):
    """计算器工具"""

    def __init__(self):
        super().__init__(
            name="calculator",
            description="数学计算器，支持四则运算，如 '1 + 2 * 3'"
        )

    async def execute(self, expression: str) -> str:
        """执行计算"""
        try:
            # 安全检查
            if any(char in expression for char in ["__", "import", "exec", "eval"]):
                return "安全错误：不允许的表达式"

            result = eval(expression, {"__builtins__": {}})
            return str(result)
        except Exception as e:
            return f"计算错误: {str(e)}"
```

### 设计优势

1. **插件化架构**: 工具可以独立开发和部署
2. **统一接口**: 所有工具使用相同的调用方式
3. **安全隔离**: 工具执行在受控环境中
4. **异步支持**: 支持并发工具执行

---

## 🎭 编排层 (Orchestration Layer)

### 核心职责

编排层是Agent的"大脑"，负责管理对话流程、状态转换和组件协调。

### 架构组件

#### 1. AgentState (状态定义)

```python
class AgentState(TypedDict):
    """Agent状态"""
    messages: Annotated[Sequence[BaseMessage], "add_messages"]
    session_id: str
    agent_id: str
    tool_calls: List[Dict[str, Any]]
    iteration_count: int
    max_iterations: int
    processing_time: float
    errors: List[str]
    metadata: Dict[str, Any]
```

#### 2. WorkflowManager (工作流管理器)

```python
class WorkflowManager:
    """工作流管理器"""

    def __init__(self, tool_executor: ToolExecutor):
        self.tool_executor = tool_executor
        self.checkpointer = SqliteSaver.from_conn_string(":memory:")
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        """创建LangGraph状态图"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("receive_message", self._receive_message)
        workflow.add_node("call_llm", self._call_llm)
        workflow.add_node("execute_tools", self._execute_tools)
        workflow.add_node("respond", self._respond)

        # 设置流程
        workflow.set_entry_point("receive_message")
        # ... 边和条件定义

        return workflow.compile(checkpointer=self.checkpointer)
```

#### 3. OrchestratorAgent (编排Agent)

```python
class OrchestratorAgent:
    """编排Agent"""

    def __init__(self, config: AgentConfig):
        # 初始化各层组件
        self.llm = LLMFactory.create_llm(...)
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.workflow = WorkflowManager(self.tool_executor)

        # 注册工具
        self._register_builtin_tools()

        # 绑定LLM和工具
        self.llm_with_tools = self.llm.bind_tools(
            self.tool_registry.get_langchain_tools()
        )
        self.workflow.set_llm(self.llm_with_tools)

    async def chat(self, session_id: str, request: ChatRequest) -> ChatResponse:
        """处理对话"""
        # 准备状态
        initial_state = self._prepare_state(session_id, request)

        # 执行工作流
        final_state = await self.workflow.execute(initial_state, config)

        # 格式化响应
        return self._format_response(final_state)
```

### 对话流程

```
接收消息 → 调用LLM → 需要工具？→ 执行工具 → 调用LLM → 响应
    ↓         ↓         是          ↓         ↓        ↓
   状态       分析      ↓          结果      继续     结束
   初始化    消息       否          合并     分析     返回
                        ↓                        响应
                       响应
```

### 设计优势

1. **状态机驱动**: 使用LangGraph清晰管理对话状态
2. **流程编排**: 自动处理工具调用和响应生成
3. **错误处理**: 完善的异常处理和重试机制
4. **可扩展性**: 新的对话模式易于添加

---

## 🎯 核心层 (Core Layer)

### 核心职责

核心层提供统一的外部接口，屏蔽底层复杂性。

### 架构组件

#### UniversalAgent (统一接口)

```python
class UniversalAgent:
    """通用Agent接口"""

    def __init__(self, config: AgentConfig):
        self.orchestrator = OrchestratorAgent(config)

    async def chat(self, session_id: str, request: ChatRequest) -> ChatResponse:
        """对话接口"""
        return await self.orchestrator.chat(session_id, request)

    # 未来可扩展的方法
    # async def create_session(self, metadata: Dict) -> str: ...
    # async def get_history(self, session_id: str) -> List[Message]: ...
    # async def clear_session(self, session_id: str) -> bool: ...
```

### 设计优势

1. **接口稳定**: 底层重构不影响外部调用
2. **简化调用**: 统一的API设计
3. **版本兼容**: 支持向后兼容
4. **扩展空间**: 为未来功能预留接口

---

## 🌐 接口层 (API Layer)

### 核心职责

接口层处理HTTP请求，提供RESTful API。

### 架构组件

#### FastAPI应用

```python
app = FastAPI(
    title="Universal Agent MVP",
    description="基于LangGraph的通用AI Agent",
    version="0.1.0"
)

# 全局变量
agent: Optional[UniversalAgent] = None

@app.on_event("startup")
async def startup_event():
    """启动事件"""
    global agent
    config = get_agent_config()
    agent = UniversalAgent(config)

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """对话接口"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return await agent.chat(request.session_id, request)
```

### API端点

- `POST /sessions` - 创建会话
- `POST /chat` - 发送消息
- `GET /sessions/{session_id}/history` - 获取历史
- `GET /tools` - 列出工具
- `GET /health` - 健康检查

### 设计优势

1. **自动文档**: Swagger UI自动生成
2. **类型安全**: Pydantic请求/响应验证
3. **异步支持**: 高并发处理能力
4. **中间件支持**: 认证、日志、CORS等

---

## ⚙️ 配置层 (Config Layer)

### 核心职责

配置层管理所有配置信息，支持多种配置源。

### 架构组件

#### 配置模型

```python
class AgentConfig(BaseModel):
    """Agent配置"""
    id: str
    name: str
    llm_config: Dict[str, Any]
    tools: List[ToolConfig] = []
    function_call: Dict[str, Any] = {"max_iterations": 5}

class ToolConfig(BaseModel):
    """工具配置"""
    id: str
    name: str
    description: str
    parameters: Dict[str, Any] = {}
    handler: Dict[str, Any]
    enabled: bool = True
```

#### 配置加载器

```python
def get_agent_config() -> AgentConfig:
    """获取Agent配置"""

    # 从环境变量获取LLM配置
    llm_provider = os.getenv("LLM_PROVIDER", "openai")
    llm_api_key = os.getenv(f"{llm_provider.upper()}_API_KEY")
    llm_model = os.getenv("LLM_MODEL", "gpt-4")

    # 构建配置
    config = AgentConfig(
        id="universal-agent",
        name="通用AI助手",
        llm_config={
            "provider": llm_provider,
            "api_key": llm_api_key,
            "model": llm_model
        },
        tools=[
            ToolConfig(
                id="calculator",
                name="calculator",
                description="数学计算器",
                enabled=True,
                handler={"type": "function", "module": "tools.calculator", "function": "calculate"}
            )
        ]
    )

    return config
```

### 配置源

1. **环境变量**: API密钥、模型配置
2. **YAML文件**: 复杂配置结构
3. **默认值**: 内置默认配置

### 设计优势

1. **环境适配**: 支持多环境配置
2. **类型安全**: Pydantic验证配置
3. **热重载**: 支持运行时配置更新
4. **安全**: 敏感信息环境变量管理
