"""
过滤器性能指标收集
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class FilterStats:
    """单个过滤器的统计信息"""
    name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_duration_ns: int = 0
    min_duration_ns: int = 0
    max_duration_ns: int = 0

    @property
    def avg_duration_ns(self) -> int:
        """平均执行时间（纳秒）"""
        if self.total_executions == 0:
            return 0
        return self.total_duration_ns // self.total_executions

    @property
    def avg_duration_ms(self) -> float:
        """平均执行时间（毫秒）"""
        return self.avg_duration_ns / 1_000_000


@dataclass
class FilterMetrics:
    """过滤器性能指标"""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_duration_ns: int = 0
    min_duration_ns: int = 0
    max_duration_ns: int = 0
    filter_stats: Dict[str, FilterStats] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    @property
    def avg_duration_ns(self) -> int:
        """平均执行时间（纳秒）"""
        if self.total_executions == 0:
            return 0
        return self.total_duration_ns // self.total_executions

    @property
    def avg_duration_ms(self) -> float:
        """平均执行时间（毫秒）"""
        return self.avg_duration_ns / 1_000_000

    def record_execution(self, filter_name: str, success: bool, duration_ns: int):
        """记录过滤器执行"""
        with self._lock:
            # 更新总体统计
            self.total_executions += 1
            if success:
                self.successful_executions += 1
            else:
                self.failed_executions += 1

            self.total_duration_ns += duration_ns
            if self.min_duration_ns == 0 or duration_ns < self.min_duration_ns:
                self.min_duration_ns = duration_ns
            if duration_ns > self.max_duration_ns:
                self.max_duration_ns = duration_ns

            # 更新单个过滤器统计
            if filter_name not in self.filter_stats:
                self.filter_stats[filter_name] = FilterStats(name=filter_name)

            stats = self.filter_stats[filter_name]
            stats.total_executions += 1
            if success:
                stats.successful_executions += 1
            else:
                stats.failed_executions += 1

            stats.total_duration_ns += duration_ns
            if stats.min_duration_ns == 0 or duration_ns < stats.min_duration_ns:
                stats.min_duration_ns = duration_ns
            if duration_ns > stats.max_duration_ns:
                stats.max_duration_ns = duration_ns

    def get_metrics(self) -> Dict:
        """获取指标快照"""
        with self._lock:
            return {
                "total_executions": self.total_executions,
                "successful_executions": self.successful_executions,
                "failed_executions": self.failed_executions,
                "avg_duration_ms": self.avg_duration_ms,
                "min_duration_ms": self.min_duration_ns / 1_000_000,
                "max_duration_ms": self.max_duration_ns / 1_000_000,
                "filter_stats": {
                    name: {
                        "name": stats.name,
                        "total_executions": stats.total_executions,
                        "successful_executions": stats.successful_executions,
                        "failed_executions": stats.failed_executions,
                        "avg_duration_ms": stats.avg_duration_ms,
                        "min_duration_ms": stats.min_duration_ns / 1_000_000,
                        "max_duration_ms": stats.max_duration_ns / 1_000_000,
                    }
                    for name, stats in self.filter_stats.items()
                }
            }

    def reset(self):
        """重置指标"""
        with self._lock:
            self.total_executions = 0
            self.successful_executions = 0
            self.failed_executions = 0
            self.total_duration_ns = 0
            self.min_duration_ns = 0
            self.max_duration_ns = 0
            self.filter_stats.clear()
