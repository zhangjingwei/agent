"""
过滤器管理器
"""

import asyncio
import time
from typing import List, Optional
import structlog

from .types import FilterContext, FilterResult, FilterChain, RequestFilter, ResponseFilter
from .metrics import FilterMetrics
from starlette.requests import Request
from starlette.responses import Response


logger = structlog.get_logger()


class FilterManager:
    """过滤器管理器"""

    def __init__(self, logger_instance=None):
        self.chain = FilterChain()
        self.logger = logger_instance or logger
        self.enabled = True
        self.metrics = FilterMetrics()

    def enable(self):
        """启用过滤器"""
        self.enabled = True
        self.logger.info("Filter manager enabled")

    def disable(self):
        """禁用过滤器"""
        self.enabled = False
        self.logger.info("Filter manager disabled")

    def is_enabled(self) -> bool:
        """检查过滤器是否启用"""
        return self.enabled

    def register_request_filter(self, filter_: RequestFilter):
        """注册请求过滤器"""
        self.chain.add_request_filter(filter_)
        self.logger.info(
            "Registered request filter",
            filter_name=filter_.name,
            priority=filter_.priority
        )

    def register_response_filter(self, filter_: ResponseFilter):
        """注册响应过滤器"""
        self.chain.add_response_filter(filter_)
        self.logger.info(
            "Registered response filter",
            filter_name=filter_.name,
            priority=filter_.priority
        )

    async def execute_request_filters(self, ctx: FilterContext, request: Request) -> List[FilterResult]:
        """执行请求过滤器链"""
        if not self.enabled:
            return []

        results = []

        for filter_ in self.chain.request_filters:
            if not filter_.should_filter(ctx, request):
                continue

            start_time = time.perf_counter_ns()
            try:
                success = await filter_.process(ctx, request)
                duration = time.perf_counter_ns() - start_time

                result = FilterResult(
                    filter_name=filter_.name,
                    success=success,
                    duration_ns=duration
                )

                # 记录指标
                self.metrics.record_execution(filter_.name, success, duration)

                if not success:
                    result.error = Exception("Filter processing failed")
                    self.logger.warn(
                        "Request filter failed",
                        filter_name=filter_.name,
                        duration_ns=duration,
                        error=result.error
                    )
                else:
                    self.logger.debug(
                        "Request filter executed",
                        filter_name=filter_.name,
                        duration_ns=duration
                    )

                results.append(result)

                # 如果过滤器返回False，停止执行后续过滤器
                if not success:
                    break

            except Exception as e:
                duration = time.perf_counter_ns() - start_time
                result = FilterResult(
                    filter_name=filter_.name,
                    success=False,
                    error=e,
                    duration_ns=duration
                )
                results.append(result)
                self.logger.error(
                    "Request filter exception",
                    filter_name=filter_.name,
                    duration_ns=duration,
                    error=str(e),
                    exc_info=True
                )
                break

        return results

    async def execute_response_filters(self, ctx: FilterContext, request: Request, response: Response) -> List[FilterResult]:
        """执行响应过滤器链"""
        if not self.enabled:
            return []

        results = []

        for filter_ in self.chain.response_filters:
            if not filter_.should_filter(ctx, request, response):
                continue

            start_time = time.perf_counter_ns()
            try:
                success = await filter_.process(ctx, request, response)
                duration = time.perf_counter_ns() - start_time

                result = FilterResult(
                    filter_name=filter_.name,
                    success=success,
                    duration_ns=duration
                )

                # 记录指标
                self.metrics.record_execution(filter_.name, success, duration)

                if not success:
                    result.error = Exception("Filter processing failed")
                    self.logger.warn(
                        "Response filter failed",
                        filter_name=filter_.name,
                        duration_ns=duration,
                        error=result.error
                    )
                else:
                    self.logger.debug(
                        "Response filter executed",
                        filter_name=filter_.name,
                        duration_ns=duration
                    )

                results.append(result)

                # 如果过滤器返回False，停止执行后续过滤器
                if not success:
                    break

            except Exception as e:
                duration = time.perf_counter_ns() - start_time
                result = FilterResult(
                    filter_name=filter_.name,
                    success=False,
                    error=e,
                    duration_ns=duration
                )
                results.append(result)
                self.logger.error(
                    "Response filter exception",
                    filter_name=filter_.name,
                    duration_ns=duration,
                    error=str(e),
                    exc_info=True
                )
                break

        return results

    def get_filter_chain(self) -> FilterChain:
        """返回过滤器链的副本"""
        chain = FilterChain()
        chain.request_filters = self.chain.request_filters.copy()
        chain.response_filters = self.chain.response_filters.copy()
        return chain

    def create_filter_context(self, request: Request) -> FilterContext:
        """创建过滤器上下文"""
        # 从请求头获取信息
        request_id = request.headers.get("x-request-id", "")
        session_id = request.headers.get("x-session-id")
        user_id = request.headers.get("x-user-id")

        # 获取客户端IP
        client_ip = request.client.host if request.client else ""

        # 获取User-Agent
        user_agent = request.headers.get("user-agent", "")

        return FilterContext(
            request_id=request_id,
            session_id=session_id,
            user_id=user_id,
            client_ip=client_ip,
            user_agent=user_agent,
            metadata={},
            trace_info={}
        )

    def get_metrics(self) -> dict:
        """获取过滤器性能指标"""
        return self.metrics.get_metrics()

    def reset_metrics(self):
        """重置指标"""
        self.metrics.reset()