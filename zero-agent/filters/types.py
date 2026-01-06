"""
过滤器类型定义
"""

from typing import Dict, Any, Optional, Protocol, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from starlette.requests import Request
from starlette.responses import Response


@dataclass
class FilterContext:
    """过滤器上下文，包含请求处理的共享信息"""
    request_id: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    client_ip: str = ""
    user_agent: str = ""
    metadata: Dict[str, Any] = None
    trace_info: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.trace_info is None:
            self.trace_info = {}


class RequestFilter(Protocol):
    """请求过滤器协议"""

    @property
    def name(self) -> str:
        """返回过滤器名称"""
        ...

    @property
    def priority(self) -> int:
        """返回过滤器优先级（数字越小优先级越高）"""
        ...

    def should_filter(self, ctx: FilterContext, request: Request) -> bool:
        """判断是否需要执行此过滤器"""
        ...

    async def process(self, ctx: FilterContext, request: Request) -> bool:
        """过滤器处理逻辑，如果返回False则停止后续处理"""
        ...


class ResponseFilter(Protocol):
    """响应过滤器协议"""

    @property
    def name(self) -> str:
        """返回过滤器名称"""
        ...

    @property
    def priority(self) -> int:
        """返回过滤器优先级（数字越小优先级越高）"""
        ...

    def should_filter(self, ctx: FilterContext, request: Request, response: Response) -> bool:
        """判断是否需要执行此过滤器"""
        ...

    async def process(self, ctx: FilterContext, request: Request, response: Response) -> bool:
        """过滤器处理逻辑，如果返回False则停止后续处理"""
        ...


@dataclass
class FilterResult:
    """过滤器执行结果"""
    filter_name: str
    success: bool
    error: Optional[Exception] = None
    duration_ns: int = 0


class FilterChain:
    """过滤器链"""

    def __init__(self):
        self.request_filters: List[RequestFilter] = []
        self.response_filters: List[ResponseFilter] = []

    def add_request_filter(self, filter_: RequestFilter):
        """添加请求过滤器"""
        self.request_filters.append(filter_)
        self._sort_request_filters()

    def add_response_filter(self, filter_: ResponseFilter):
        """添加响应过滤器"""
        self.response_filters.append(filter_)
        self._sort_response_filters()

    def _sort_request_filters(self):
        """按优先级排序请求过滤器"""
        self.request_filters.sort(key=lambda f: f.priority)

    def _sort_response_filters(self):
        """按优先级排序响应过滤器"""
        self.response_filters.sort(key=lambda f: f.priority)
