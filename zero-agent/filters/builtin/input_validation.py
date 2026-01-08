"""
输入验证过滤器
"""

import json
from typing import List, Optional, Dict, Any
import structlog

from ..types import FilterContext, RequestFilter
from starlette.requests import Request
from starlette.responses import JSONResponse


logger = structlog.get_logger()


class InputValidationConfig:
    """输入验证配置"""

    def __init__(
        self,
        max_message_length: int = 10000,
        max_metadata_size: int = 1024,
        blocked_words: Optional[List[str]] = None,
        required_fields: Optional[List[str]] = None,
        allowed_content_types: Optional[List[str]] = None
    ):
        self.max_message_length = max_message_length
        self.max_metadata_size = max_metadata_size
        self.blocked_words = blocked_words or []
        self.required_fields = required_fields or []
        self.allowed_content_types = allowed_content_types or ["application/json"]


class InputValidationFilter(RequestFilter):
    """输入验证过滤器"""

    def __init__(self, logger_instance=None, config: Optional[InputValidationConfig] = None):
        self.logger = logger_instance or logger
        self.config = config or InputValidationConfig()

    @property
    def name(self) -> str:
        return "input_validation"

    @property
    def priority(self) -> int:
        return 100  # 高优先级，在其他过滤器之前执行

    def should_filter(self, ctx: FilterContext, request: Request) -> bool:
        if request.url.path == "/health":
            return False
        # 对其他请求都执行输入验证
        return True

    async def process(self, ctx: FilterContext, request: Request) -> bool:
        try:
            # 对于 GET 请求或没有请求体的请求，跳过 Content-Type 检查
            if request.method == "GET" or request.method == "HEAD":
                self.logger.debug("Skipping content-type validation for GET/HEAD request")
            return True

            # 检查Content-Type
            content_type = request.headers.get("content-type", "")
            if not self._is_allowed_content_type(content_type):
                self.logger.warning(
                    "Invalid content type",
                    content_type=content_type,
                    allowed_types=self.config.allowed_content_types
                )
                # 注意：FastAPI中间件中不能直接返回响应，需要通过异常或修改请求来处理
                ctx.metadata["validation_error"] = "Unsupported content type"
                return False

            # 对于JSON请求，验证请求体
            if self._is_json_content_type(content_type):
                try:
                    body = await request.json()
                except json.JSONDecodeError:
                    self.logger.warning("Invalid JSON format")
                    ctx.metadata["validation_error"] = "Invalid JSON format"
                    return False

                # 验证必需字段
                if not self._validate_required_fields(body):
                    self.logger.warning(
                        "Missing required fields",
                        required_fields=self.config.required_fields
                    )
                    ctx.metadata["validation_error"] = "Missing required fields"
                    return False

                # 验证消息长度
                if "message" in body and isinstance(body["message"], str):
                    message = body["message"]
                    if len(message) > self.config.max_message_length:
                        self.logger.warning(
                            "Message too long",
                            length=len(message),
                            max_length=self.config.max_message_length
                        )
                        ctx.metadata["validation_error"] = "Message too long"
                        return False

                    # 检查屏蔽词
                    if self._contains_blocked_words(message):
                        self.logger.warning(
                            "Message contains blocked words",
                            client_ip=ctx.client_ip
                        )
                        ctx.metadata["validation_error"] = "Message contains inappropriate content"
                        return False

                # 验证元数据大小
                if "metadata" in body:
                    metadata_size = self._calculate_size(body["metadata"])
                    if metadata_size > self.config.max_metadata_size:
                        self.logger.warning(
                            "Metadata too large",
                            size=metadata_size,
                            max_size=self.config.max_metadata_size
                        )
                        ctx.metadata["validation_error"] = "Metadata too large"
                        return False

                # 将验证后的数据存储在上下文中
                ctx.metadata["validated_body"] = body

            self.logger.debug("Input validation passed", request_id=ctx.request_id)
            return True

        except Exception as e:
            self.logger.error("Input validation error", error=str(e), exc_info=True)
            ctx.metadata["validation_error"] = f"Validation error: {str(e)}"
            return False

    def _is_allowed_content_type(self, content_type: str) -> bool:
        """检查是否为允许的内容类型"""
        if not self.config.allowed_content_types:
            return True  # 如果没有配置，则允许所有

        for allowed in self.config.allowed_content_types:
            if allowed.lower() in content_type.lower():
                return True
        return False

    def _is_json_content_type(self, content_type: str) -> bool:
        """检查是否为JSON内容类型"""
        return "application/json" in content_type.lower()

    def _validate_required_fields(self, body: Dict[str, Any]) -> bool:
        """验证必需字段"""
        for field in self.config.required_fields:
            if field not in body:
                return False
        return True

    def _contains_blocked_words(self, text: str) -> bool:
        """检查是否包含屏蔽词"""
        lower_text = text.lower()
        for word in self.config.blocked_words:
            if word.lower() in lower_text:
                return True
        return False

    def _calculate_size(self, obj: Any) -> int:
        """计算对象的大致大小"""
        # 简单估算：将对象序列化为字符串并计算长度
        try:
            size = len(json.dumps(obj))
            return size
        except (TypeError, ValueError):
            return 0
