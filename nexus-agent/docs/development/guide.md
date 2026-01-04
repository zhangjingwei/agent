# 开发指南

## 项目结构

```
agent-mvp/
├── llm/                    # 🧠 LLM层
│   ├── base.py            # LLM提供商接口
│   ├── factory.py         # LLM工厂
│   └── providers/         # 提供商实现
│       ├── openai.py
│       ├── anthropic.py
│       └── siliconflow.py
├── tools/                  # 🔧 工具层
│   ├── base.py            # 工具接口
│   ├── registry.py        # 工具注册器
│   ├── executor.py        # 工具执行器
│   └── builtin/           # 内置工具
├── orchestration/         # 🎭 编排层
│   ├── state.py           # 状态管理
│   ├── workflow.py        # LangGraph工作流
│   └── agent.py           # 编排Agent
├── core/                   # 🎯 核心层
│   └── agent.py           # UniversalAgent
├── config/                 # ⚙️ 配置层
│   ├── models.py          # 配置模型
│   └── settings.py        # 配置管理
├── api/                    # 🌐 接口层
│   └── app.py             # FastAPI应用
└── tests/                  # 🧪 测试
```

## 添加新LLM提供商

### 1. 实现提供商类

```python
# llm/providers/new_provider.py
from ..base import LLMProvider
from langchain_core.runnables import Runnable

class NewProvider(LLMProvider):
    """新LLM提供商实现"""

    def create_llm(self) -> Runnable:
        # 创建LLM实例的逻辑
        return CustomLLM(
            api_key=self.api_key,
            model=self.model,
            base_url=self.config.get('base_url'),
            **self.config.get('extra_params', {})
        )

    def get_provider_name(self) -> str:
        return "new_provider"
```

### 2. 注册提供商

```python
# llm/factory.py
from .providers.new_provider import NewProvider

class LLMFactory:
    _providers = {
        'openai': OpenAIProvider,
        'anthropic': AnthropicProvider,
        'siliconflow': SiliconFlowProvider,
        'new_provider': NewProvider  # 添加新提供商
    }
```

### 3. 使用新提供商

```python
# 配置中使用
llm_config = {
    "provider": "new_provider",
    "api_key": "your-api-key",
    "model": "model-name",
    "extra_params": {
        "temperature": 0.7
    }
}
```

## 添加新工具

### 方法1：内置工具

#### 1. 创建工具类

```python
# tools/builtin/weather.py
from ..base import Tool

class WeatherTool(Tool):
    """天气查询工具"""

    def __init__(self):
        super().__init__(
            name="weather",
            description="查询天气信息，支持城市名称"
        )

    async def execute(self, city: str) -> str:
        """查询天气"""
        # 实现天气查询逻辑
        # 这里使用示例API
        api_key = os.getenv("WEATHER_API_KEY")
        if not api_key:
            return "未配置天气API密钥"

        try:
            # 调用天气API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://api.weatherapi.com/v1/current.json",
                    params={
                        "key": api_key,
                        "q": city,
                        "aqi": "no"
                    }
                )

            if response.status_code == 200:
                data = response.json()
                temp = data["current"]["temp_c"]
                condition = data["current"]["condition"]["text"]
                return f"{city}当前天气：{condition}，温度：{temp}°C"
            else:
                return f"天气查询失败：{response.status_code}"

        except Exception as e:
            return f"天气查询错误：{str(e)}"
```

#### 2. 注册工具

```python
# tools/builtin/__init__.py
from .calculator import CalculatorTool
from .weather import WeatherTool

__all__ = ['CalculatorTool', 'WeatherTool']
```

#### 3. 在编排Agent中添加

```python
# orchestration/agent.py
from tools.builtin import CalculatorTool, WeatherTool

class OrchestratorAgent:
    def _register_builtin_tools(self):
        """注册内置工具"""
        calculator = CalculatorTool()
        self.tool_registry.register(calculator)

        # 添加天气工具
        weather = WeatherTool()
        self.tool_registry.register(weather)
```

### 方法2：动态工具

#### 1. HTTP工具配置

```yaml
# config/agent.yaml
tools:
  - id: "weather"
    name: "weather"
    description: "查询天气信息"
    enabled: true
    parameters:
      type: object
      properties:
        city:
          type: string
          description: 城市名称
      required: ["city"]
    handler:
      type: "http"
      method: "GET"
      url: "http://api.weatherapi.com/v1/current.json"
      params_mapping:
        city: "q"
      headers:
        key: "${WEATHER_API_KEY}"
      response_mapping:
        temperature: "current.temp_c"
        condition: "current.condition.text"
        city: "location.name"
```

#### 2. 实现HTTP工具执行器

```python
# tools/executor.py
async def execute_http_tool(self, handler: Dict[str, Any], arguments: Dict[str, Any]) -> Any:
    """执行HTTP工具"""
    import httpx

    method = handler.get("method", "GET").upper()
    url = handler["url"]
    timeout = handler.get("timeout", 10000) / 1000

    # 参数映射
    params_mapping = handler.get("params_mapping", {})
    params = {}
    for arg_key, param_key in params_mapping.items():
        if arg_key in arguments:
            params[param_key] = arguments[arg_key]

    # 请求头
    headers = handler.get("headers", {}).copy()
    for key, value in headers.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            headers[key] = os.getenv(env_var, value)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            response = await client.get(url, params=params, headers=headers)
        elif method == "POST":
            json_data = arguments.get("body", arguments)
            response = await client.post(url, json=json_data, params=params, headers=headers)
        # ... 其他HTTP方法

        response.raise_for_status()

        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            response_mapping = handler.get("response_mapping", {})
            if response_mapping:
                # 映射响应数据
                result = {}
                for key, path in response_mapping.items():
                    value = self._extract_value_by_path(data, path)
                    result[key] = value
                return result
            return data
        return response.text

def _extract_value_by_path(self, data: Dict, path: str) -> Any:
    """按路径提取值"""
    if "." not in path:
        return data.get(path)

    parts = path.split(".")
    current = data

    for part in parts:
        if "[" in part and "]" in part:
            # 处理数组访问，如 "items[0]"
            array_name, index_part = part.split("[")
            index = int(index_part.rstrip("]"))
            current = current[array_name][index]
        else:
            current = current[part]

    return current
```

## 扩展Agent能力

### 添加新的对话模式

#### 1. 自定义状态

```python
# orchestration/state.py
class ConversationState(TypedDict):
    """对话状态"""
    topic: str
    sentiment: str
    complexity: int
    tags: List[str]

class ExtendedAgentState(AgentState):
    """扩展的状态"""
    conversation: ConversationState
    memory: List[str]  # 记忆
    preferences: Dict[str, Any]  # 用户偏好
```

#### 2. 记忆管理

```python
# orchestration/memory.py
class MemoryManager:
    """记忆管理器"""

    def __init__(self, max_memories=100):
        self.memories = []
        self.max_memories = max_memories

    def add_memory(self, content: str, importance: float = 0.5):
        """添加记忆"""
        memory = {
            "content": content,
            "importance": importance,
            "timestamp": datetime.now(),
            "access_count": 0
        }
        self.memories.append(memory)

        # 保持记忆数量在限制内
        if len(self.memories) > self.max_memories:
            # 移除最不重要的记忆
            self.memories.sort(key=lambda x: x["importance"])
            self.memories = self.memories[-self.max_memories:]

    def get_relevant_memories(self, query: str, limit=5) -> List[str]:
        """获取相关记忆"""
        # 简单的关键词匹配
        relevant = []
        query_words = set(query.lower().split())

        for memory in self.memories:
            content_words = set(memory["content"].lower().split())
            similarity = len(query_words & content_words) / len(query_words | content_words)

            if similarity > 0.1:  # 相似度阈值
                relevant.append((memory, similarity))

        # 按相似度排序
        relevant.sort(key=lambda x: x[1], reverse=True)

        return [mem["content"] for mem, _ in relevant[:limit]]

    def update_memory_access(self, memory_content: str):
        """更新记忆访问计数"""
        for memory in self.memories:
            if memory["content"] == memory_content:
                memory["access_count"] += 1
                break
```

#### 3. 上下文感知

```python
# orchestration/context.py
class ContextAnalyzer:
    """上下文分析器"""

    def __init__(self):
        self.nlp_model = None  # 可以加载NLP模型

    def analyze_message(self, message: str) -> Dict[str, Any]:
        """分析消息"""
        return {
            "sentiment": self._analyze_sentiment(message),
            "intent": self._classify_intent(message),
            "entities": self._extract_entities(message),
            "complexity": self._calculate_complexity(message),
            "topics": self._identify_topics(message)
        }

    def _analyze_sentiment(self, text: str) -> str:
        """情感分析"""
        # 简单的关键词分析
        positive_words = ["好", "不错", "喜欢", "满意", "棒"]
        negative_words = ["差", "不好", "讨厌", "失望", "糟糕"]

        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    def _classify_intent(self, text: str) -> str:
        """意图分类"""
        if any(word in text for word in ["计算", "算", "compute"]):
            return "calculation"
        elif any(word in text for word in ["天气", "weather"]):
            return "weather_query"
        elif any(word in text for word in ["帮助", "help"]):
            return "help_request"
        else:
            return "general_chat"

    def _extract_entities(self, text: str) -> List[str]:
        """实体提取"""
        # 简单的城市名称提取
        cities = ["北京", "上海", "广州", "深圳", "杭州"]
        found_cities = [city for city in cities if city in text]
        return found_cities

    def _calculate_complexity(self, text: str) -> int:
        """计算复杂度"""
        length = len(text)
        if length < 10:
            return 1
        elif length < 50:
            return 2
        elif length < 200:
            return 3
        else:
            return 4

    def _identify_topics(self, text: str) -> List[str]:
        """主题识别"""
        topics = []
        if any(word in text for word in ["数学", "计算", "算术"]):
            topics.append("mathematics")
        if any(word in text for word in ["天气", "气候", "气象"]):
            topics.append("weather")
        if any(word in text for word in ["编程", "代码", "开发"]):
            topics.append("programming")

        return topics
```

### 4. 个性化响应

```python
# orchestration/personalization.py
class PersonalizationEngine:
    """个性化引擎"""

    def __init__(self):
        self.user_profiles = {}  # 用户画像

    def update_profile(self, user_id: str, message: str, response: str):
        """更新用户画像"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                "interaction_count": 0,
                "preferred_topics": {},
                "response_style": "neutral",
                "expertise_level": "beginner"
            }

        profile = self.user_profiles[user_id]
        profile["interaction_count"] += 1

        # 分析偏好主题
        topics = self._extract_topics(message)
        for topic in topics:
            profile["preferred_topics"][topic] = profile["preferred_topics"].get(topic, 0) + 1

    def get_personalized_response(self, user_id: str, base_response: str) -> str:
        """生成个性化响应"""
        if user_id not in self.user_profiles:
            return base_response

        profile = self.user_profiles[user_id]

        # 根据交互次数调整详细程度
        interaction_count = profile["interaction_count"]
        if interaction_count < 5:
            # 新用户，提供更多解释
            return base_response + "\n\n如果你有任何疑问，请随时问我！"
        elif interaction_count > 50:
            # 老用户，保持简洁
            return base_response

        return base_response

    def _extract_topics(self, text: str) -> List[str]:
        """提取主题（简化实现）"""
        topics = []
        topic_keywords = {
            "mathematics": ["数学", "计算", "算术", "代数"],
            "programming": ["编程", "代码", "开发", "软件"],
            "weather": ["天气", "气候", "气象", "温度"]
        }

        for topic, keywords in topic_keywords.items():
            if any(keyword in text for keyword in keywords):
                topics.append(topic)

        return topics
```

## 自定义中间件

### 请求日志中间件

```python
# api/middleware.py
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 记录请求信息
        logger.info(f"Request: {request.method} {request.url}")
        logger.info(f"Client: {request.client.host if request.client else 'unknown'}")

        try:
            response = await call_next(request)

            process_time = time.time() - start_time
            logger.info(".2f"
            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(".2f"            raise
```

### 认证中间件

```python
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证JWT token"""
    token = credentials.credentials

    try:
        # 验证token逻辑
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        return user_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### 使用中间件

```python
# api/app.py
from .middleware import RequestLoggingMiddleware

app = FastAPI()

# 添加中间件
app.add_middleware(RequestLoggingMiddleware)

# 受保护的路由
@app.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    user_id: str = Depends(verify_token)
):
    # user_id 已通过认证验证
    return await agent.chat(request.session_id, request)
```

## 插件系统

### 插件接口

```python
# plugins/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class Plugin(ABC):
    """插件基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件"""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """清理插件"""
        pass

    def get_capabilities(self) -> List[str]:
        """获取插件能力"""
        return []
```

### 插件管理器

```python
# plugins/manager.py
import importlib
from typing import Dict, Any
from .base import Plugin

class PluginManager:
    """插件管理器"""

    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.plugin_configs = {}

    async def load_plugin(self, plugin_path: str, config: Dict[str, Any] = None):
        """加载插件"""
        try:
            # 动态导入插件
            module = importlib.import_module(plugin_path)
            plugin_class = getattr(module, 'Plugin')

            # 创建插件实例
            plugin = plugin_class()
            await plugin.initialize(config or {})

            self.plugins[plugin.name] = plugin
            self.plugin_configs[plugin.name] = config or {}

            print(f"Plugin {plugin.name} v{plugin.version} loaded")

        except Exception as e:
            print(f"Failed to load plugin {plugin_path}: {e}")

    async def unload_plugin(self, name: str):
        """卸载插件"""
        if name in self.plugins:
            await self.plugins[name].cleanup()
            del self.plugins[name]
            del self.plugin_configs[name]
            print(f"Plugin {name} unloaded")

    def get_plugin(self, name: str) -> Plugin:
        """获取插件"""
        return self.plugins.get(name)

    def list_plugins(self) -> Dict[str, str]:
        """列出所有插件"""
        return {
            name: plugin.version
            for name, plugin in self.plugins.items()
        }

    async def cleanup_all(self):
        """清理所有插件"""
        for plugin in self.plugins.values():
            await plugin.cleanup()
        self.plugins.clear()
        self.plugin_configs.clear()
```

### 创建自定义插件

```python
# plugins/custom_monitor.py
from .base import Plugin

class CustomMonitorPlugin(Plugin):
    """自定义监控插件"""

    @property
    def name(self) -> str:
        return "custom_monitor"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件"""
        self.monitor_endpoint = config.get('endpoint', 'http://localhost:9090')
        self.api_key = config.get('api_key', '')
        print(f"Custom monitor initialized with endpoint: {self.monitor_endpoint}")

    async def cleanup(self) -> None:
        """清理插件"""
        print("Custom monitor cleaned up")

    def get_capabilities(self) -> List[str]:
        """获取插件能力"""
        return ["monitoring", "metrics", "alerting"]

    async def send_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """发送指标"""
        # 实现指标发送逻辑
        pass
```

### 在应用中使用插件

```python
# api/app.py
from plugins.manager import PluginManager

# 全局插件管理器
plugin_manager = PluginManager()

@app.on_event("startup")
async def startup_event():
    """启动事件"""
    # 加载插件
    await plugin_manager.load_plugin(
        'plugins.custom_monitor',
        config={
            'endpoint': 'http://monitoring.example.com',
            'api_key': os.getenv('MONITOR_API_KEY')
        }
    )

@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件"""
    await plugin_manager.cleanup_all()
```

## 测试驱动开发

### 单元测试

```python
# tests/test_calculator_tool.py
import pytest
from tools.calculator import CalculatorTool

class TestCalculatorTool:
    def setup_method(self):
        self.tool = CalculatorTool()

    def test_simple_addition(self):
        import asyncio
        result = asyncio.run(self.tool.execute("1 + 1"))
        assert result == "2"

    def test_complex_expression(self):
        import asyncio
        result = asyncio.run(self.tool.execute("(2 + 3) * 4"))
        assert result == "20"

    def test_security_check(self):
        import asyncio
        result = asyncio.run(self.tool.execute("__import__('os').system('ls')"))
        assert "安全错误" in result

    def test_error_handling(self):
        import asyncio
        result = asyncio.run(self.tool.execute("1 / 0"))
        assert "计算错误" in result
```

### 集成测试

```python
# tests/test_agent_integration.py
import pytest
from core import UniversalAgent
from config.models import AgentConfig

class TestAgentIntegration:
    @pytest.fixture
    def agent_config(self):
        return AgentConfig(
            id="test-agent",
            name="Test Agent",
            llm_config={
                "provider": "openai",  # 使用mock或测试key
                "api_key": "test-key",
                "model": "gpt-3.5-turbo"
            }
        )

    def test_agent_initialization(self, agent_config):
        agent = UniversalAgent(agent_config)
        assert agent.orchestrator is not None
        assert len(agent.orchestrator.tool_registry.get_all_tools()) > 0

    @pytest.mark.asyncio
    async def test_chat_workflow(self, agent_config):
        agent = UniversalAgent(agent_config)

        # 这里需要mock LLM调用
        # 或者使用测试LLM提供商
        pass
```

### API测试

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from api.app import app

class TestAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_create_session(self, client):
        response = client.post("/sessions")
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data

    def test_chat_requires_session(self, client):
        response = client.post("/chat", json={
            "message": "Hello"
        })
        assert response.status_code == 422  # 验证错误

    def test_list_tools(self, client):
        response = client.get("/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) > 0
```

## 性能优化

### 异步优化

```python
# orchestration/workflow.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

class OptimizedWorkflowManager(WorkflowManager):
    """优化的工作流管理器"""

    def __init__(self, tool_executor: ToolExecutor, max_workers=4):
        super().__init__(tool_executor)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def _execute_tools_parallel(self, state: AgentState) -> AgentState:
        """并行执行工具"""
        if not state["tool_calls"]:
            return state

        # 创建并行任务
        tasks = []
        for tool_call in state["tool_calls"]:
            task = asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._execute_single_tool_sync,
                tool_call
            )
            tasks.append(task)

        # 等待所有任务完成
        results = await asyncio.gather(*tasks)

        # 处理结果
        tool_messages = []
        for result in results:
            tool_messages.append(ToolMessage(
                content=str(result),
                tool_call_id=result["tool_call_id"]
            ))

        state["messages"] = state["messages"] + tool_messages
        return state

    def _execute_single_tool_sync(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """同步执行单个工具（在线程池中运行）"""
        import asyncio

        async def async_execute():
            try:
                result = await self.tool_executor.execute(
                    tool_call["name"],
                    tool_call["arguments"]
                )
                return {
                    "result": result,
                    "tool_call_id": tool_call["id"],
                    "success": True
                }
            except Exception as e:
                return {
                    "result": str(e),
                    "tool_call_id": tool_call["id"],
                    "success": False
                }

        # 在新的事件循环中运行
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(async_execute())
        finally:
            loop.close()
```

### 缓存优化

```python
# core/cache.py
import asyncio
from typing import Dict, Any, Optional
import time

class LRUCache:
    """LRU缓存实现"""

    def __init__(self, capacity: int = 100, ttl: int = 3600):
        self.capacity = capacity
        self.ttl = ttl  # time to live in seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_order: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        """获取缓存项"""
        if key in self.cache:
            item = self.cache[key]
            if time.time() - item["timestamp"] > self.ttl:
                # 过期了，删除
                del self.cache[key]
                del self.access_order[key]
                return None

            # 更新访问时间
            self.access_order[key] = time.time()
            return item["value"]

        return None

    def put(self, key: str, value: Any) -> None:
        """设置缓存项"""
        current_time = time.time()

        if key in self.cache:
            # 更新现有项
            self.cache[key] = {
                "value": value,
                "timestamp": current_time
            }
            self.access_order[key] = current_time
        else:
            # 添加新项
            if len(self.cache) >= self.capacity:
                # 移除最少使用的项
                lru_key = min(self.access_order, key=self.access_order.get)
                del self.cache[lru_key]
                del self.access_order[lru_key]

            self.cache[key] = {
                "value": value,
                "timestamp": current_time
            }
            self.access_order[key] = current_time

    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
        self.access_order.clear()

# 在Agent中使用缓存
class CachedAgent:
    """带缓存的Agent"""

    def __init__(self, agent: UniversalAgent, cache_capacity=100):
        self.agent = agent
        self.cache = LRUCache(capacity=cache_capacity)

    async def chat(self, session_id: str, request: ChatRequest) -> ChatResponse:
        # 生成缓存键
        cache_key = f"{session_id}:{hash(request.message)}"

        # 尝试从缓存获取
        cached_response = self.cache.get(cache_key)
        if cached_response:
            return cached_response

        # 调用实际的Agent
        response = await self.agent.chat(session_id, request)

        # 缓存结果（只缓存简单的响应）
        if len(response.message) < 1000 and not response.tool_calls:
            self.cache.put(cache_key, response)

        return response
```
