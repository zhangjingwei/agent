"""
资源管理器 - 全局并发控制和资源限制
"""

import asyncio
import logging
import concurrent.futures
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ResourceManager:
    """全局资源管理器，控制并发和资源使用"""
    
    def __init__(
        self,
        max_concurrent_requests: int = 100,
        max_concurrent_workflows: int = 50,
        max_concurrent_tools: int = 20,
        thread_pool_size: int = 20
    ):
        """
        初始化资源管理器
        
        Args:
            max_concurrent_requests: 最大并发请求数
            max_concurrent_workflows: 最大并发工作流数
            max_concurrent_tools: 全局最大并发工具数
            thread_pool_size: 线程池大小，用于执行同步工具函数
        """
        self._request_semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._workflow_semaphore = asyncio.Semaphore(max_concurrent_workflows)
        self._global_tool_semaphore = asyncio.Semaphore(max_concurrent_tools)
        
        # 创建共享线程池，用于执行同步工具函数
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=thread_pool_size,
            thread_name_prefix="tool-executor"
        )
        
        self.max_concurrent_requests = max_concurrent_requests
        self.max_concurrent_workflows = max_concurrent_workflows
        self.max_concurrent_tools = max_concurrent_tools
        self.thread_pool_size = thread_pool_size
        
        logger.info(
            f"资源管理器初始化: 最大并发请求={max_concurrent_requests}, "
            f"最大并发工作流={max_concurrent_workflows}, "
            f"最大并发工具={max_concurrent_tools}, "
            f"线程池大小={thread_pool_size}"
        )
    
    @property
    def thread_pool(self) -> concurrent.futures.ThreadPoolExecutor:
        """获取共享线程池"""
        return self._thread_pool
    
    def shutdown(self, wait: bool = True):
        """关闭资源管理器，清理线程池"""
        if self._thread_pool:
            self._thread_pool.shutdown(wait=wait)
            logger.info("线程池已关闭")
    
    @asynccontextmanager
    async def acquire_request(self):
        """获取请求资源"""
        async with self._request_semaphore:
            try:
                yield
            finally:
                pass
    
    @asynccontextmanager
    async def acquire_workflow(self):
        """获取工作流资源"""
        async with self._workflow_semaphore:
            try:
                yield
            finally:
                pass
    
    @asynccontextmanager
    async def acquire_tool(self):
        """获取工具执行资源（全局限制）"""
        async with self._global_tool_semaphore:
            try:
                yield
            finally:
                pass
    
    def get_stats(self) -> dict:
        """获取资源使用统计"""
        return {
            "max_concurrent_requests": self.max_concurrent_requests,
            "max_concurrent_workflows": self.max_concurrent_workflows,
            "max_concurrent_tools": self.max_concurrent_tools,
            "thread_pool_size": self.thread_pool_size,
            "available_requests": self._request_semaphore._value,
            "available_workflows": self._workflow_semaphore._value,
            "available_tools": self._global_tool_semaphore._value,
        }


# 全局资源管理器实例
_global_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """获取全局资源管理器"""
    global _global_resource_manager
    if _global_resource_manager is None:
        _global_resource_manager = ResourceManager()
    return _global_resource_manager


def set_resource_manager(manager: ResourceManager):
    """设置全局资源管理器"""
    global _global_resource_manager
    _global_resource_manager = manager
