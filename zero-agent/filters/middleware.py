"""
过滤器中间件
"""

from typing import Callable
import structlog

from .manager import FilterManager
from .types import FilterContext
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware


logger = structlog.get_logger()


class FilterMiddleware(BaseHTTPMiddleware):
    """过滤器中间件"""

    def __init__(self, app: Callable, filter_manager: FilterManager):
        super().__init__(app)
        self.filter_manager = filter_manager

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求和响应"""
        # 创建过滤器上下文
        ctx = self.filter_manager.create_filter_context(request)

        # 执行请求过滤器链
        request_results = await self.filter_manager.execute_request_filters(ctx, request)

        # 如果有请求过滤器失败，停止处理
        for result in request_results:
            if not result.success:
                # 创建错误响应
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Request filter failed: {result.filter_name}"}
                )

        # 处理请求
        response = await call_next(request)

        # 执行响应过滤器链
        response_results = await self.filter_manager.execute_response_filters(ctx, request, response)

        # 将过滤器结果添加到响应头（用于调试）
        if request_results or response_results:
            response.headers["X-Filter-Processed"] = "true"

        # 记录过滤器执行统计
        total_request_filters = len(request_results)
        failed_request_filters = sum(1 for r in request_results if not r.success)
        total_response_filters = len(response_results)
        failed_response_filters = sum(1 for r in response_results if not r.success)

        if failed_request_filters > 0 or failed_response_filters > 0:
            logger.warning(
                "Filter execution completed with failures",
                request_id=ctx.request_id,
                total_request_filters=total_request_filters,
                failed_request_filters=failed_request_filters,
                total_response_filters=total_response_filters,
                failed_response_filters=failed_response_filters
            )
        else:
            logger.debug(
                "Filter execution completed successfully",
                request_id=ctx.request_id,
                request_filters=total_request_filters,
                response_filters=total_response_filters
            )

        return response
