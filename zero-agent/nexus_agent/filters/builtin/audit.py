"""
审计过滤器
"""

import time
from typing import Optional, List, Dict, Any
import structlog

from ..types import FilterContext, RequestFilter, ResponseFilter
from starlette.requests import Request
from starlette.responses import Response


logger = structlog.get_logger()


class AuditConfig:
    """审计配置"""

    def __init__(
        self,
        enable_request_logging: bool = True,
        enable_response_logging: bool = True,
        log_sensitive_data: bool = False,
        sensitive_fields: Optional[List[str]] = None,
        max_log_size: int = 1024,
        log_level: str = "info"
    ):
        self.enable_request_logging = enable_request_logging
        self.enable_response_logging = enable_response_logging
        self.log_sensitive_data = log_sensitive_data
        self.sensitive_fields = sensitive_fields or ["password", "token", "secret", "key", "authorization"]
        self.max_log_size = max_log_size
        self.log_level = log_level


class AuditRequestFilter(RequestFilter):
    """审计请求过滤器"""

    def __init__(self, logger_instance=None, config: Optional[AuditConfig] = None):
        self.logger = logger_instance or logger
        self.config = config or AuditConfig()

    @property
    def name(self) -> str:
        return "audit_request"

    @property
    def priority(self) -> int:
        return 10  # 最高优先级，最先执行

    def should_filter(self, ctx: FilterContext, request: Request) -> bool:
        # 对所有请求都执行审计
        return True

    async def process(self, ctx: FilterContext, request: Request) -> bool:
        """处理请求审计"""
        if self.config.enable_request_logging:
            await self._log_request(ctx, request)

        # 记录审计开始时间
        ctx.metadata["audit_start_time"] = time.time()

        return True


class AuditResponseFilter(ResponseFilter):
    """审计响应过滤器"""

    def __init__(self, logger_instance=None, config: Optional[AuditConfig] = None):
        self.logger = logger_instance or logger
        self.config = config or AuditConfig()

    @property
    def name(self) -> str:
        return "audit_response"

    @property
    def priority(self) -> int:
        return 10  # 最高优先级，最先执行

    def should_filter(self, ctx: FilterContext, request: Request, response: Response) -> bool:
        """响应过滤器：判断是否需要执行"""
        return True

    async def process(self, ctx: FilterContext, request: Request, response: Response) -> bool:
        """响应过滤器：处理响应审计"""
        if not self.config.enable_response_logging:
            return True

        start_time = ctx.metadata.get("audit_start_time", time.time())
        duration = time.time() - start_time

        await self._log_response(ctx, request, response, duration)
        return True

    async def _log_request(self, ctx: FilterContext, request: Request):
        """记录请求日志"""
        # 过滤敏感头信息
        headers = self._filter_sensitive_headers(dict(request.headers))

        # 请求体日志（如果启用且大小合适）
        body_data = None
        if self.config.log_sensitive_data:
            try:
                # 读取请求体（注意：这可能会消耗请求体）
                body_bytes = await request.body()
                if len(body_bytes) <= self.config.max_log_size:
                    body_data = body_bytes.decode('utf-8', errors='ignore')
            except Exception:
                pass

        log_data = {
            "request_id": ctx.request_id,
            "session_id": ctx.session_id,
            "user_id": ctx.user_id,
            "client_ip": ctx.client_ip,
            "user_agent": ctx.user_agent,
            "method": request.method,
            "url": str(request.url),
            "headers": headers,
        }

        if body_data:
            log_data["body"] = body_data

        self.logger.info("Request audit", **log_data)

    async def _log_response(self, ctx: FilterContext, request: Request, response: Response, duration: float):
        """记录响应日志"""
        # 过滤敏感头信息
        headers = self._filter_sensitive_headers(dict(response.headers))

        # 响应体日志（如果启用且大小合适）
        body_data = None
        if self.config.log_sensitive_data:
            try:
                # 对于FastAPI Response，获取响应体
                if hasattr(response, 'body'):
                    body_bytes = response.body
                    if isinstance(body_bytes, bytes) and len(body_bytes) <= self.config.max_log_size:
                        body_data = body_bytes.decode('utf-8', errors='ignore')
            except Exception:
                pass

        log_data = {
            "request_id": ctx.request_id,
            "session_id": ctx.session_id,
            "user_id": ctx.user_id,
            "status_code": response.status_code,
            "duration": f"{duration:.3f}s",
            "headers": headers,
        }

        if body_data:
            log_data["response_body"] = body_data

        self.logger.info("Response audit", **log_data)

    def _filter_sensitive_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """过滤敏感头信息"""
        filtered = {}

        for key, value in headers.items():
            lower_key = key.lower()
            is_sensitive = False

            for sensitive in self.config.sensitive_fields:
                if sensitive.lower() in lower_key:
                    is_sensitive = True
                    break

            if not is_sensitive:
                filtered[key] = value

        return filtered