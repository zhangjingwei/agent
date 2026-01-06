"""
输出处理过滤器
"""

import json
import time
from typing import Optional, Dict, Any
import structlog

from ..types import FilterContext, ResponseFilter
from starlette.requests import Request
from starlette.responses import Response


logger = structlog.get_logger()


class OutputProcessingConfig:
    """输出处理配置"""

    def __init__(
        self,
        sanitize_output: bool = True,
        max_response_size: int = 10 * 1024 * 1024,  # 10MB
        add_response_headers: bool = True,
        response_timeout: int = 30,
        compression_enabled: bool = False,
        cache_control_header: str = "no-cache",
        cors_headers: bool = True
    ):
        self.sanitize_output = sanitize_output
        self.max_response_size = max_response_size
        self.add_response_headers = add_response_headers
        self.response_timeout = response_timeout
        self.compression_enabled = compression_enabled
        self.cache_control_header = cache_control_header
        self.cors_headers = cors_headers


class OutputProcessingFilter(ResponseFilter):
    """输出处理过滤器"""

    def __init__(self, logger_instance=None, config: Optional[OutputProcessingConfig] = None):
        self.logger = logger_instance or logger
        self.config = config or OutputProcessingConfig()

    @property
    def name(self) -> str:
        return "output_processing"

    @property
    def priority(self) -> int:
        return 200  # 中等优先级，在请求过滤器之后执行

    def should_filter(self, ctx: FilterContext, request: Request, response: Response) -> bool:
        # 对所有响应都执行输出处理
        return True

    async def process(self, ctx: FilterContext, request: Request, response: Response) -> bool:
        try:
            # 添加响应头
            if self.config.add_response_headers:
                self._add_response_headers(response, ctx)

            # 检查响应大小
            if self.config.max_response_size > 0:
                if not await self._check_response_size(response):
                    self.logger.warn("Response size check failed")
                    # 注意：在FastAPI中，我们不能直接修改响应状态码
                    # 应该在更早的阶段处理这个问题
                    pass

            # 清理响应内容
            if self.config.sanitize_output:
                await self._sanitize_response(response)

            # 添加处理时间戳
            ctx.metadata["response_processed_at"] = time.time()

            self.logger.debug(
                "Output processing completed",
                request_id=ctx.request_id
            )
            return True

        except Exception as e:
            self.logger.error("Output processing error", error=str(e), exc_info=True)
            return False

    def _add_response_headers(self, response: Response, ctx: FilterContext):
        """添加响应头"""
        # 添加标准头
        response.headers["X-Request-ID"] = ctx.request_id
        response.headers["X-Processed-At"] = str(int(time.time()))

        # 添加缓存控制
        if self.config.cache_control_header:
            response.headers["Cache-Control"] = self.config.cache_control_header

        # 添加CORS头
        if self.config.cors_headers:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID"

        # 添加安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

    async def _check_response_size(self, response: Response) -> bool:
        """检查响应大小"""
        # 对于流式响应或大响应，这里只是简单检查Content-Length
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.config.max_response_size:
                    return False
            except ValueError:
                pass
        return True

    async def _sanitize_response(self, response: Response):
        """清理响应内容"""
        # 只处理JSON响应
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            return

        # 对于FastAPI Response，我们需要检查响应体的类型
        # 这里只是一个简化实现，实际应用中可能需要更复杂的处理
        try:
            # 如果响应体是dict或可序列化对象，尝试清理
            if hasattr(response, 'body') and isinstance(response.body, dict):
                self._sanitize_json_data(response.body)
        except Exception:
            # 如果清理失败，继续处理
            pass

    def _sanitize_json_data(self, data: Dict[str, Any]):
        """清理JSON数据中的敏感信息"""
        if not isinstance(data, dict):
            return

        # 清理敏感字段
        sensitive_fields = ["password", "token", "secret", "key", "authorization"]
        for field in sensitive_fields:
            if field in data:
                data[field] = "***REDACTED***"

        # 递归处理嵌套对象
        for key, value in data.items():
            if isinstance(value, dict):
                self._sanitize_json_data(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._sanitize_json_data(item)