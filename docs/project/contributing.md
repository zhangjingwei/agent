# 贡献指南

欢迎参与Universal Agent项目的贡献！我们非常感谢社区成员为项目的发展做出的任何贡献。

## 快速开始

### 开发环境设置

1. **Fork项目**
   ```bash
   git clone https://github.com/your-username/nexus-agent.git
   cd nexus-agent
   ```

2. **创建虚拟环境**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/macOS
   # 或
   venv\Scripts\activate     # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -e .[dev]
   ```

4. **运行测试**
   ```bash
   pytest
   ```

5. **启动开发服务器**
   ```bash
   python -m scripts.start
   ```

### 代码风格

我们使用以下工具确保代码质量：

- **Black**: 代码格式化
- **isort**: 导入排序
- **flake8**: 代码检查
- **mypy**: 类型检查

```bash
# 格式化代码
black .

# 排序导入
isort .

# 代码检查
flake8 .

# 类型检查
mypy .
```

## 贡献类型

### 🐛 错误修复
- 修复bug和问题
- 改进错误处理
- 修复安全漏洞

### ✨ 新功能
- 添加新功能
- 扩展现有功能
- 改进用户体验

### 📚 文档
- 改进文档
- 添加使用示例
- 翻译文档

### 🧪 测试
- 添加单元测试
- 改进测试覆盖率
- 添加集成测试

### 🔧 工具和基础设施
- 改进构建脚本
- 更新CI/CD配置
- 改进开发工具

## 开发流程

### 1. 选择任务

首先查看[GitHub Issues](https://github.com/your-repo/nexus-agent/issues)找到适合你的任务：

- **good first issue**: 适合新手的简单任务
- **help wanted**: 需要帮助的任务
- **bug**: 错误修复
- **enhancement**: 功能增强

### 2. 创建分支

```bash
# 从main分支创建新分支
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# 或修复bug
git checkout -b fix/issue-number-description
```

### 3. 编写代码

遵循以下原则：

#### 代码规范
- 使用类型注解
- 编写清晰的文档字符串
- 保持函数简短（<50行）
- 使用描述性的变量名

#### 示例代码
```python
from typing import Optional, Dict, Any
from config.models import ChatRequest, ChatResponse

class ExampleService:
    """示例服务类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    async def process_request(
        self,
        request: ChatRequest,
        context: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """
        处理聊天请求

        Args:
            request: 聊天请求对象
            context: 可选的上下文信息

        Returns:
            聊天响应对象

        Raises:
            ValueError: 当请求无效时
        """
        if not request.message:
            raise ValueError("消息不能为空")

        # 处理逻辑
        response_message = f"收到消息: {request.message}"

        return ChatResponse(
            message=response_message,
            tool_calls=[],
            processing_time=0.1,
            session_id=request.session_id
        )
```

### 4. 编写测试

为你的代码编写测试：

```python
# tests/test_example_service.py
import pytest
from unittest.mock import AsyncMock
from your_module import ExampleService

class TestExampleService:
    @pytest.fixture
    def service(self):
        config = {"example_setting": "test"}
        return ExampleService(config)

    @pytest.fixture
    def sample_request(self):
        from config.models import ChatRequest
        return ChatRequest(
            session_id="test-session",
            message="Hello, world!",
            metadata={"test": True}
        )

    def test_initialization(self, service):
        """测试服务初始化"""
        assert service.config["example_setting"] == "test"

    @pytest.mark.asyncio
    async def test_process_valid_request(self, service, sample_request):
        """测试处理有效请求"""
        response = await service.process_request(sample_request)

        assert response.message == "收到消息: Hello, world!"
        assert response.session_id == "test-session"
        assert response.processing_time == 0.1

    @pytest.mark.asyncio
    async def test_process_empty_message(self, service):
        """测试处理空消息"""
        from config.models import ChatRequest

        request = ChatRequest(
            session_id="test-session",
            message=""
        )

        with pytest.raises(ValueError, match="消息不能为空"):
            await service.process_request(request)

    @pytest.mark.asyncio
    async def test_process_with_context(self, service, sample_request):
        """测试带上下文的处理"""
        context = {"user_preference": "verbose"}
        response = await service.process_request(sample_request, context)

        assert "Hello, world!" in response.message
```

### 5. 运行测试

确保所有测试通过：

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_example_service.py

# 运行带覆盖率的测试
pytest --cov=agent_mvp --cov-report=html

# 生成覆盖率报告
open htmlcov/index.html
```

### 6. 更新文档

如果添加了新功能，请更新相关文档：

- 更新 `docs/` 中的相关文档
- 添加使用示例
- 更新API文档（如果有API变更）

### 7. 提交代码

```bash
# 添加更改的文件
git add .

# 提交更改
git commit -m "feat: 添加新功能

- 添加了ExampleService类
- 支持异步请求处理
- 添加了完整的单元测试
- 更新了相关文档

Closes #123"

# 推送分支
git push origin feature/your-feature-name
```

### 8. 创建Pull Request

1. 访问GitHub上的项目页面
2. 点击"Pull Request"标签
3. 点击"New pull request"
4. 选择你的分支作为compare分支
5. 填写PR描述：
   - 清楚描述变更内容
   - 解释为什么需要这些变更
   - 引用相关的Issue编号
   - 添加测试和文档的截图（如适用）

## 提交信息规范

我们使用[Conventional Commits](https://conventionalcommits.org/)规范：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### 类型
- **feat**: 新功能
- **fix**: 错误修复
- **docs**: 文档变更
- **style**: 代码风格调整
- **refactor**: 代码重构
- **test**: 测试相关
- **chore**: 构建工具或辅助工具的变动

### 示例
```bash
feat: 添加用户认证功能
fix: 修复计算器工具的除零错误
docs: 更新API文档
refactor: 重构工具注册器以提高性能
test: 添加新的集成测试
```

## 代码审查

### 审查清单

在提交PR之前，请确保：

- [ ] 代码通过所有测试（`pytest`）
- [ ] 代码格式正确（`black .`）
- [ ] 导入已排序（`isort .`）
- [ ] 无代码检查错误（`flake8 .`）
- [ ] 类型检查通过（`mypy .`）
- [ ] 文档已更新
- [ ] 提交信息符合规范

### 审查标准

代码审查将检查：

1. **功能正确性**
   - 代码实现了预期的功能
   - 处理了边界情况和错误情况

2. **代码质量**
   - 遵循了项目的代码规范
   - 代码可读性和可维护性好
   - 适当的抽象和封装

3. **测试覆盖**
   - 有足够的单元测试
   - 测试覆盖了主要代码路径
   - 包含了错误情况的测试

4. **文档完整性**
   - 代码有适当的文档字符串
   - API变更已记录
   - 使用示例已提供

5. **性能考虑**
   - 无明显的性能问题
   - 适当的异步处理
   - 资源使用合理

## 行为准则

### 我们的承诺

在Universal Agent项目的贡献者和维护者承诺，无论在项目空间还是公共空间，都提供一个无骚扰的环境。

### 标准

贡献者行为准则的示例包括：

- 使用欢迎和包容性的语言
- 尊重不同的观点和经验
- 优雅地接受建设性批评
- 专注于对社区最有利的事情
- 对其他社区成员表示同情

### 责任

项目维护者有权并有责任删除、编辑或拒绝评论、提交、代码、wiki编辑、问题和其他不符合本行为准则的贡献。

## 获得帮助

### 沟通渠道

- **GitHub Issues**: 技术问题和功能请求
- **GitHub Discussions**: 一般讨论和想法交流
- **Discord/Slack**: 实时社区交流（如果有）

### 寻求帮助

如果你需要帮助：

1. 查看[文档](README.md)
2. 搜索现有的GitHub Issues
3. 在Discussions中提问
4. 联系维护者

### 新手友好

我们欢迎新贡献者！如果你是第一次贡献：

1. 从 `good first issue` 标签的任务开始
2. 阅读项目的[架构文档](architecture/overview.md)
3. 加入社区讨论
4. 不要害怕提问

## 奖励和认可

### 贡献者认可

我们重视所有形式的贡献：

- **代码贡献**: 功能开发、bug修复、重构
- **文档贡献**: 编写、翻译、改进文档
- **测试贡献**: 编写和维护测试
- **社区贡献**: 回答问题、帮助新人、分享经验

### 贡献者墙

显著贡献者将被添加到项目的贡献者列表中。

### 合作机会

积极的贡献者可能会被邀请参与：
- 核心开发团队
- 技术决策讨论
- 社区活动组织

## 许可证

通过提交贡献，你同意你的贡献将根据项目的许可证进行许可。

---

感谢你对Universal Agent项目的贡献！你的努力帮助我们构建更好的AI Agent平台。
