"""
熔断器 - 用于保护上游服务，避免持续失败导致资源浪费
"""

import time
import logging
from enum import Enum
from typing import Optional
from threading import Lock

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"  # 关闭：正常状态，允许请求通过
    OPEN = "open"  # 打开：熔断状态，拒绝请求
    HALF_OPEN = "half_open"  # 半开：尝试恢复，允许少量请求通过


class CircuitBreaker:
    """熔断器实现
    
    使用滑动窗口统计失败率，当失败率超过阈值时触发熔断。
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,  # 连续失败次数阈值
        success_threshold: int = 2,  # 半开状态下成功次数阈值（用于恢复）
        timeout: float = 60.0,  # 熔断持续时间（秒）
        name: str = "default"
    ):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 触发熔断的连续失败次数
            success_threshold: 半开状态下需要连续成功的次数才能恢复
            timeout: 熔断持续时间，超过此时间后进入半开状态
            name: 熔断器名称，用于日志
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.name = name
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()
        
        logger.info(
            f"熔断器 [{name}] 初始化: "
            f"失败阈值={failure_threshold}, "
            f"成功阈值={success_threshold}, "
            f"超时={timeout}秒"
        )
    
    def call(self, func, *args, **kwargs):
        """同步调用，带熔断保护"""
        if not self._allow_request():
            raise CircuitBreakerOpenError(
                f"熔断器 [{self.name}] 处于打开状态，请求被拒绝"
            )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    async def call_async(self, func, *args, **kwargs):
        """异步调用，带熔断保护"""
        if not self._allow_request():
            raise CircuitBreakerOpenError(
                f"熔断器 [{self.name}] 处于打开状态，请求被拒绝"
            )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _allow_request(self) -> bool:
        """检查是否允许请求通过"""
        with self._lock:
            now = time.time()
            
            # 如果处于打开状态，检查是否超时
            if self._state == CircuitState.OPEN:
                if self._last_failure_time and (now - self._last_failure_time) >= self.timeout:
                    # 超时，进入半开状态
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info(f"熔断器 [{self.name}] 超时，进入半开状态，允许测试请求")
                    return True
                else:
                    # 仍在熔断期内，拒绝请求
                    return False
            
            # 关闭或半开状态，允许请求
            return True
    
    def _on_success(self):
        """记录成功"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    # 连续成功达到阈值，恢复关闭状态
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"熔断器 [{self.name}] 恢复，进入关闭状态")
            else:
                # 关闭状态下，重置失败计数
                self._failure_count = 0
    
    def _on_failure(self):
        """记录失败"""
        with self._lock:
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # 半开状态下失败，立即重新打开
                self._state = CircuitState.OPEN
                self._success_count = 0
                logger.warning(f"熔断器 [{self.name}] 半开状态下失败，重新打开")
            else:
                # 关闭状态下，增加失败计数
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    # 达到失败阈值，打开熔断器
                    self._state = CircuitState.OPEN
                    logger.warning(
                        f"熔断器 [{self.name}] 触发熔断，"
                        f"连续失败 {self._failure_count} 次"
                    )
    
    def get_state(self) -> CircuitState:
        """获取当前状态"""
        with self._lock:
            return self._state
    
    def reset(self):
        """手动重置熔断器"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            logger.info(f"熔断器 [{self.name}] 已手动重置")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
                "failure_threshold": self.failure_threshold,
                "success_threshold": self.success_threshold,
                "timeout": self.timeout
            }


class CircuitBreakerOpenError(Exception):
    """熔断器打开时抛出的异常"""
    pass
