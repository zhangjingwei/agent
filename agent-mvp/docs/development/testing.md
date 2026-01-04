# 测试指南

## 测试策略

### 测试金字塔

```
           /\
          /  \
   E2E Tests  API Tests
        /      \
       / Unit  \
      /  Tests  \
     /__________\
    Integration Tests
```

### 测试类型

1. **单元测试** - 测试单个函数/方法
2. **集成测试** - 测试模块间的交互
3. **API测试** - 测试HTTP接口
4. **端到端测试** - 测试完整用户流程

## 项目结构

```
tests/
├── __init__.py
├── conftest.py           # pytest配置和fixtures
├── unit/                 # 单元测试
│   ├── test_llm.py      # LLM层测试
│   ├── test_tools.py    # 工具层测试
│   └── test_config.py   # 配置层测试
├── integration/         # 集成测试
│   ├── test_agent.py    # Agent集成测试
│   └── test_workflow.py # 工作流测试
├── api/                 # API测试
│   └── test_api.py      # FastAPI测试
└── e2e/                 # 端到端测试
    └── test_user_flow.py # 用户流程测试
```

## 环境准备

### 安装测试依赖

```bash
# 安装测试依赖
pip install -e .[dev]

# 或单独安装
pip install pytest pytest-asyncio pytest-cov httpx
```

### 测试环境变量

```bash
# 创建测试环境文件
cp .env .env.test

# 编辑测试配置
nano .env.test
```

```bash
# .env.test
# 测试环境配置
ENVIRONMENT=test

# 测试用的API密钥（可以使用测试key或mock）
OPENAI_API_KEY=test-key
LLM_MODEL=gpt-3.5-turbo

# 数据库配置（使用内存数据库）
DATABASE_URL=sqlite:///:memory:

# 日志配置
LOG_LEVEL=WARNING
```

## 运行测试

### 基本测试命令

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/unit/test_tools.py

# 运行特定测试类
pytest tests/unit/test_tools.py::TestCalculatorTool

# 运行特定测试方法
pytest tests/unit/test_tools.py::TestCalculatorTool::test_simple_addition

# 运行带覆盖率的测试
pytest --cov=agent_mvp --cov-report=html

# 运行带详细输出的测试
pytest -v

# 运行失败时停止
pytest -x
```

### 并行测试

```bash
# 安装pytest-xdist
pip install pytest-xdist

# 使用4个进程并行运行
pytest -n 4
```

### 测试特定标记

```bash
# 标记测试
@pytest.mark.slow
def test_slow_operation():
    pass

# 只运行慢速测试
pytest -m slow

# 跳过慢速测试
pytest -m "not slow"
```

## 编写测试

### 单元测试

#### LLM层测试

```python
# tests/unit/test_llm.py
import pytest
from unittest.mock import Mock, patch
from llm.factory import LLMFactory
from llm.providers.openai_provider import OpenAIProvider

class TestLLMFactory:
    def test_create_openai_llm(self):
        """测试创建OpenAI LLM"""
        llm = LLMFactory.create_llm(
            provider="openai",
            api_key="test-key",
            model="gpt-3.5-turbo"
        )

        assert llm is not None
        # 这里可以添加更多断言

    def test_invalid_provider(self):
        """测试无效的提供商"""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMFactory.create_llm(
                provider="invalid",
                api_key="test-key",
                model="test-model"
            )

class TestOpenAIProvider:
    def test_provider_creation(self):
        """测试提供商创建"""
        provider = OpenAIProvider(
            api_key="test-key",
            model="gpt-3.5-turbo"
        )

        assert provider.api_key == "test-key"
        assert provider.model == "gpt-3.5-turbo"
        assert provider.get_provider_name() == "openai"

    def test_config_validation(self):
        """测试配置验证"""
        # 有效的配置
        provider = OpenAIProvider(api_key="key", model="model")
        assert provider.validate_config() == True

        # 无效的配置
        provider = OpenAIProvider(api_key="", model="model")
        assert provider.validate_config() == False

    @patch('llm.providers.openai_provider.ChatOpenAI')
    def test_create_llm(self, mock_chat_openai):
        """测试LLM创建"""
        mock_instance = Mock()
        mock_chat_openai.return_value = mock_instance

        provider = OpenAIProvider(
            api_key="test-key",
            model="gpt-3.5-turbo",
            temperature=0.7
        )

        llm = provider.create_llm()

        mock_chat_openai.assert_called_once_with(
            model="gpt-3.5-turbo",
            api_key="test-key",
            temperature=0.7,
            extra_params={}
        )
        assert llm == mock_instance
```

#### 工具层测试

```python
# tests/unit/test_tools.py
import pytest
from tools.calculator import CalculatorTool
from tools.registry import ToolRegistry

class TestCalculatorTool:
    @pytest.fixture
    def calculator(self):
        return CalculatorTool()

    @pytest.mark.asyncio
    async def test_simple_addition(self, calculator):
        """测试简单加法"""
        result = await calculator.execute("1 + 1")
        assert result == "2"

    @pytest.mark.asyncio
    async def test_complex_expression(self, calculator):
        """测试复杂表达式"""
        result = await calculator.execute("(2 + 3) * 4 - 1")
        assert result == "19"

    @pytest.mark.asyncio
    async def test_security_check(self, calculator):
        """测试安全检查"""
        result = await calculator.execute("__import__('os').system('ls')")
        assert "安全错误" in result

    @pytest.mark.asyncio
    async def test_error_handling(self, calculator):
        """测试错误处理"""
        result = await calculator.execute("1 / 0")
        assert "计算错误" in result

    def test_tool_properties(self, calculator):
        """测试工具属性"""
        assert calculator.name == "calculator"
        assert "数学计算器" in calculator.description

class TestToolRegistry:
    def test_registry_creation(self):
        """测试注册器创建"""
        registry = ToolRegistry()
        assert len(registry.get_all_tools()) == 0

    def test_register_tool(self):
        """测试工具注册"""
        registry = ToolRegistry()
        calculator = CalculatorTool()

        registry.register(calculator)

        assert registry.has_tool("calculator")
        assert len(registry.get_all_tools()) == 1
        assert registry.get_tool("calculator") == calculator

    def test_unregister_tool(self):
        """测试工具注销"""
        registry = ToolRegistry()
        calculator = CalculatorTool()

        registry.register(calculator)
        assert registry.has_tool("calculator")

        registry.unregister("calculator")
        assert not registry.has_tool("calculator")

    def test_get_langchain_tools(self):
        """测试获取LangChain工具"""
        registry = ToolRegistry()
        calculator = CalculatorTool()
        registry.register(calculator)

        langchain_tools = registry.get_langchain_tools()
        assert len(langchain_tools) == 1
        assert langchain_tools[0].name == "calculator"
```

### 集成测试

#### Agent集成测试

```python
# tests/integration/test_agent.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from core import UniversalAgent
from config.models import AgentConfig

class TestUniversalAgent:
    @pytest.fixture
    def agent_config(self):
        """测试用的Agent配置"""
        return AgentConfig(
            id="test-agent",
            name="Test Agent",
            llm_config={
                "provider": "openai",
                "api_key": "test-key",
                "model": "gpt-3.5-turbo"
            }
        )

    @pytest.fixture
    def mock_llm(self):
        """模拟LLM"""
        mock = Mock()
        mock.invoke = AsyncMock()
        mock.bind_tools = Mock(return_value=mock)
        return mock

    @patch('llm.factory.LLMFactory.create_llm')
    def test_agent_initialization(self, mock_create_llm, agent_config, mock_llm):
        """测试Agent初始化"""
        mock_create_llm.return_value = mock_llm

        agent = UniversalAgent(agent_config)

        # 验证LLM工厂被正确调用
        mock_create_llm.assert_called_once_with(
            provider="openai",
            api_key="test-key",
            model="gpt-3.5-turbo"
        )

        # 验证Agent结构
        assert agent.orchestrator is not None
        assert agent.orchestrator.llm == mock_llm

    @pytest.mark.asyncio
    @patch('llm.factory.LLMFactory.create_llm')
    async def test_chat_method(self, mock_create_llm, agent_config, mock_llm):
        """测试chat方法"""
        from langchain_core.messages import AIMessage

        # 设置模拟LLM响应
        mock_response = AIMessage(content="Hello, I can help you!")
        mock_llm.invoke = AsyncMock(return_value=mock_response)
        mock_create_llm.return_value = mock_llm

        agent = UniversalAgent(agent_config)

        # 调用chat方法
        response = await agent.chat("session-123", Mock(message="Hi"))

        # 验证响应
        assert response.message == "Hello, I can help you!"
        assert response.session_id == "session-123"

        # 验证LLM被调用
        mock_llm.invoke.assert_called_once()
```

#### 工作流测试

```python
# tests/integration/test_workflow.py
import pytest
from unittest.mock import AsyncMock
from orchestration.workflow import WorkflowManager
from orchestration.state import AgentState
from tools.registry import ToolRegistry
from tools.executor import ToolExecutor

class TestWorkflowManager:
    @pytest.fixture
    def tool_registry(self):
        """测试用的工具注册器"""
        registry = ToolRegistry()
        return registry

    @pytest.fixture
    def tool_executor(self, tool_registry):
        """测试用的工具执行器"""
        return ToolExecutor(tool_registry)

    @pytest.fixture
    def workflow_manager(self, tool_executor):
        """测试用的工作流管理器"""
        return WorkflowManager(tool_executor)

    @pytest.mark.asyncio
    async def test_workflow_execution(self, workflow_manager):
        """测试工作流执行"""
        initial_state: AgentState = {
            "messages": [],
            "session_id": "test-session",
            "agent_id": "test-agent",
            "tool_calls": [],
            "iteration_count": 0,
            "max_iterations": 5,
            "processing_time": 0.0,
            "errors": [],
            "metadata": {}
        }

        # 设置模拟LLM
        mock_llm = AsyncMock()
        from langchain_core.messages import AIMessage
        mock_llm.invoke.return_value = AIMessage(content="Test response")
        workflow_manager.set_llm(mock_llm)

        # 执行工作流
        config = {"configurable": {"thread_id": "test-session"}}
        final_state = await workflow_manager.execute(initial_state, config)

        # 验证结果
        assert final_state["session_id"] == "test-session"
        assert len(final_state["messages"]) > 0
        assert isinstance(final_state["messages"][0], AIMessage)

    def test_graph_compilation(self, workflow_manager):
        """测试图编译"""
        assert workflow_manager.graph is not None

        # 验证图结构
        graph_dict = workflow_manager.graph.get_graph().dict()
        assert "nodes" in graph_dict
        assert "edges" in graph_dict

        # 应该有4个节点：receive_message, call_llm, execute_tools, respond
        assert len(graph_dict["nodes"]) == 4
```

### API测试

```python
# tests/api/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from api.app import app

class TestAPI:
    @pytest.fixture
    def client(self):
        """测试客户端"""
        return TestClient(app)

    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "agent_id" in data
        assert "tools_count" in data
        assert "timestamp" in data

    def test_create_session(self, client):
        """测试创建会话"""
        response = client.post("/sessions")

        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert "created_at" in data
        assert "metadata" in data

    def test_create_session_with_metadata(self, client):
        """测试创建带元数据的会话"""
        metadata = {
            "user_id": "test-user",
            "session_type": "demo"
        }

        response = client.post("/sessions", json={"metadata": metadata})

        assert response.status_code == 201
        data = response.json()
        assert data["metadata"]["user_id"] == "test-user"
        assert data["metadata"]["session_type"] == "demo"

    @patch('api.app.agent')
    def test_chat_endpoint(self, mock_agent, client):
        """测试聊天端点"""
        # 模拟Agent响应
        mock_response = Mock()
        mock_response.message = "Hello from AI!"
        mock_response.tool_calls = []
        mock_response.processing_time = 1.23
        mock_response.session_id = "test-session"

        mock_agent.chat = AsyncMock(return_value=mock_response)

        request_data = {
            "session_id": "test-session",
            "message": "Hello AI!"
        }

        response = client.post("/chat", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Hello from AI!"
        assert data["processing_time"] == 1.23
        assert data["session_id"] == "test-session"

    def test_chat_missing_session_id(self, client):
        """测试聊天缺少session_id"""
        request_data = {
            "message": "Hello AI!"
        }

        response = client.post("/chat", json=request_data)

        assert response.status_code == 422  # 验证错误

    def test_chat_invalid_session(self, client):
        """测试无效会话"""
        request_data = {
            "session_id": "nonexistent-session",
            "message": "Hello AI!"
        }

        response = client.post("/chat", json=request_data)

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_list_tools(self, client):
        """测试列出工具"""
        response = client.get("/tools")

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)

        # 验证工具结构
        if data["tools"]:
            tool = data["tools"][0]
            assert "id" in tool
            assert "name" in tool
            assert "description" in tool

    def test_get_session_history(self, client):
        """测试获取会话历史"""
        # 先创建会话
        create_response = client.post("/sessions")
        session_id = create_response.json()["session_id"]

        # 获取历史
        response = client.get(f"/sessions/{session_id}/history")

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "messages" in data
        assert isinstance(data["messages"], list)

    def test_delete_session(self, client):
        """测试删除会话"""
        # 先创建会话
        create_response = client.post("/sessions")
        session_id = create_response.json()["session_id"]

        # 删除会话
        response = client.delete(f"/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "会话已删除"
        assert data["session_id"] == session_id

    def test_delete_nonexistent_session(self, client):
        """测试删除不存在的会话"""
        response = client.delete("/sessions/nonexistent-session")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
```

## 测试工具和实用程序

### 测试配置

```python
# tests/conftest.py
import pytest
import os
from pathlib import Path

@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """设置测试环境"""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["LOG_LEVEL"] = "WARNING"

@pytest.fixture
def test_data_dir():
    """测试数据目录"""
    return Path(__file__).parent / "data"

@pytest.fixture
def sample_agent_config():
    """示例Agent配置"""
    from config.models import AgentConfig
    return AgentConfig(
        id="test-agent",
        name="Test Agent",
        llm_config={
            "provider": "openai",
            "api_key": "test-key",
            "model": "gpt-3.5-turbo"
        }
    )
```

### Mock和Stub

```python
# tests/mocks.py
from unittest.mock import Mock, AsyncMock
from langchain_core.messages import AIMessage

def create_mock_llm_response(content="Mock response"):
    """创建模拟LLM响应"""
    return AIMessage(content=content)

def create_mock_tool_call(name="calculator", arguments={"expression": "1+1"}):
    """创建模拟工具调用"""
    return {
        "id": "call_123",
        "name": name,
        "arguments": arguments
    }

class MockLLM:
    """模拟LLM类"""
    def __init__(self, responses=None):
        self.responses = responses or [create_mock_llm_response()]
        self.call_count = 0

    def invoke(self, messages):
        """模拟invoke方法"""
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return response

    def bind_tools(self, tools):
        """模拟bind_tools方法"""
        return self

class AsyncMockLLM:
    """异步模拟LLM类"""
    def __init__(self, responses=None):
        self.responses = responses or [create_mock_llm_response()]
        self.call_count = 0

    async def invoke(self, messages):
        """异步模拟invoke方法"""
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return response

    def bind_tools(self, tools):
        """模拟bind_tools方法"""
        return self
```

### 测试数据工厂

```python
# tests/factories.py
from config.models import AgentConfig, ChatRequest, ChatResponse
from langchain_core.messages import HumanMessage, AIMessage

def create_agent_config(**overrides):
    """创建Agent配置"""
    config = AgentConfig(
        id="test-agent",
        name="Test Agent",
        llm_config={
            "provider": "openai",
            "api_key": "test-key",
            "model": "gpt-3.5-turbo"
        },
        tools=[]
    )

    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config

def create_chat_request(message="Test message", session_id="test-session", **kwargs):
    """创建聊天请求"""
    return ChatRequest(
        session_id=session_id,
        message=message,
        metadata=kwargs.get("metadata", {})
    )

def create_chat_response(message="Test response", **kwargs):
    """创建聊天响应"""
    return ChatResponse(
        message=message,
        tool_calls=kwargs.get("tool_calls", []),
        processing_time=kwargs.get("processing_time", 1.0),
        session_id=kwargs.get("session_id", "test-session")
    )

def create_conversation_messages(count=2):
    """创建对话消息列表"""
    messages = []
    for i in range(count):
        if i % 2 == 0:
            messages.append(HumanMessage(content=f"User message {i//2 + 1}"))
        else:
            messages.append(AIMessage(content=f"AI response {i//2 + 1}"))

    return messages
```

### 性能测试

```python
# tests/performance/test_performance.py
import pytest
import time
import asyncio
from statistics import mean, median
from core import UniversalAgent
from tests.factories import create_agent_config, create_chat_request

class TestPerformance:
    @pytest.fixture
    def agent(self):
        """性能测试用的Agent"""
        config = create_agent_config()
        return UniversalAgent(config)

    def test_response_time(self, agent):
        """测试响应时间"""
        request = create_chat_request(message="Calculate 1+1")

        # 测量多次调用
        times = []
        for _ in range(10):
            start_time = time.time()

            # 这里需要mock LLM响应，因为真实的API调用会很慢
            # response = await agent.chat("perf-test", request)
            # 模拟处理时间
            time.sleep(0.01)  # 10ms

            end_time = time.time()
            times.append(end_time - start_time)

        avg_time = mean(times)
        max_time = max(times)
        min_time = min(times)

        # 断言性能要求
        assert avg_time < 0.1  # 平均响应时间小于100ms
        assert max_time < 0.5  # 最大响应时间小于500ms

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, agent):
        """测试并发请求"""
        async def single_request(i):
            request = create_chat_request(
                message=f"Calculate {i}+{i}",
                session_id=f"concurrency-test-{i}"
            )
            # 这里也需要mock
            # return await agent.chat(request.session_id, request)
            await asyncio.sleep(0.01)  # 模拟处理
            return f"Result for {i}"

        # 并发执行10个请求
        start_time = time.time()
        tasks = [single_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        total_time = end_time - start_time

        # 验证结果
        assert len(results) == 10
        # 并发执行应该比串行执行快
        assert total_time < 0.5  # 总时间应该小于500ms

    def test_memory_usage(self, agent):
        """测试内存使用"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # 执行一些操作
        for i in range(100):
            request = create_chat_request(message=f"Test {i}")
            # 模拟处理
            pass

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # 内存增长应该在合理范围内
        assert memory_increase < 50  # 假设最多增加50MB
```

## CI/CD集成

### GitHub Actions配置

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .[dev]

    - name: Run tests
      run: |
        pytest --cov=agent_mvp --cov-report=xml

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### 测试覆盖率

```ini
# .coveragerc
[run]
source = agent_mvp
omit =
    */tests/*
    */venv/*
    setup.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
```

## 调试技巧

### 调试失败的测试

```bash
# 运行失败的测试并显示详细信息
pytest -v --tb=long --lf

# 使用pdb调试
pytest --pdb -k "test_specific_function"

# 显示print语句输出
pytest -s -k "test_specific_function"
```

### 测试数据和Mock

```python
# 使用responses库mock HTTP请求
import responses

@responses.activate
def test_external_api_call():
    responses.add(
        responses.GET,
        'http://api.weather.com/weather',
        json={'temperature': 25, 'condition': 'sunny'},
        status=200
    )

    # 测试代码
    result = get_weather('beijing')
    assert result['temperature'] == 25
```

### 异步测试技巧

```python
@pytest.mark.asyncio
async def test_async_function():
    # 使用asyncio.sleep模拟异步操作
    await asyncio.sleep(0.1)

    # 使用AsyncMock
    mock_func = AsyncMock(return_value="mocked")
    result = await mock_func()
    assert result == "mocked"

# 测试异常
@pytest.mark.asyncio
async def test_async_exception():
    with pytest.raises(ValueError):
        await async_function_that_raises()
```

## 最佳实践

### 1. 测试命名
- `test_function_name` - 功能测试
- `test_function_name_with_condition` - 条件测试
- `test_function_name_error_case` - 错误情况测试

### 2. 测试结构
```python
class TestFeature:
    @pytest.fixture
    def setup_data(self):
        # 测试数据准备
        return TestData()

    def test_normal_case(self, setup_data):
        # 正常情况测试
        pass

    def test_edge_case(self, setup_data):
        # 边界情况测试
        pass

    def test_error_case(self, setup_data):
        # 错误情况测试
        pass
```

### 3. Mock策略
- 只mock外部依赖
- 使用真实对象测试内部逻辑
- 验证mock的调用

### 4. 覆盖率目标
- 单元测试: >80%
- 集成测试: >70%
- 整体覆盖率: >75%

### 5. 性能基准
- 响应时间: <100ms (简单查询)
- 并发处理: 100+ 请求/秒
- 内存使用: <100MB (基础配置)
