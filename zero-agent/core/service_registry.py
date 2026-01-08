"""
服务注册模块 - Agent 启动时注册到 Redis，定期心跳
"""

import asyncio
import logging
import os
import socket
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import redis.asyncio as aioredis
import json

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """服务注册器，用于将 Agent 注册到 Redis"""
    
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        redis_db: int = 0,
        service_name: str = "zero-agent",
        service_id: Optional[str] = None,
        host: Optional[str] = None,
        port: int = 8082,
        ttl: int = 60,  # 服务 TTL（秒）
        heartbeat_interval: int = 15  # 心跳间隔（秒）
    ):
        """
        初始化服务注册器
        
        Args:
            redis_host: Redis 主机地址
            redis_port: Redis 端口
            redis_password: Redis 密码
            redis_db: Redis 数据库编号
            service_name: 服务名称
            service_id: 服务 ID（如果不提供，自动生成）
            host: 服务主机地址（如果不提供，自动检测）
            port: 服务端口
            ttl: 服务 TTL（秒）
            heartbeat_interval: 心跳间隔（秒）
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redis_db = redis_db
        self.service_name = service_name
        self.service_id = service_id or self._generate_service_id()
        self.host = host or self._get_local_ip()
        self.port = port
        self.ttl = ttl
        self.heartbeat_interval = heartbeat_interval
        
        self.redis_client: Optional[aioredis.Redis] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._registered = False
    
    def _generate_service_id(self) -> str:
        """生成服务 ID"""
        hostname = socket.gethostname()
        return f"{hostname}-{uuid.uuid4().hex[:8]}"
    
    def _get_local_ip(self) -> str:
        """获取本地 IP 地址"""
        try:
            # 连接到一个远程地址来获取本地 IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    async def _connect_redis(self):
        """连接 Redis"""
        if self.redis_client is None:
            self.redis_client = await aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}",
                password=self.redis_password,
                db=self.redis_db,
                encoding="utf-8",
                decode_responses=True
            )
            # 测试连接
            await self.redis_client.ping()
            logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
    
    async def _disconnect_redis(self):
        """断开 Redis 连接"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Disconnected from Redis")
    
    def _get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "id": self.service_id,
            "name": self.service_name,
            "address": self.host,
            "port": self.port,
            "protocol": "http",
            "health_check": f"http://{self.host}:{self.port}/health",
            "metadata": {
                "hostname": socket.gethostname(),
                "pid": str(os.getpid()),
            },
            "registered_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat(),
            "ttl": self.ttl
        }
    
    async def register(self) -> bool:
        """注册服务到 Redis"""
        try:
            await self._connect_redis()
            
            service_info = self._get_service_info()
            key = f"service:{self.service_name}:{self.service_id}"
            
            # 注册服务信息，设置 TTL
            await self.redis_client.setex(
                key,
                self.ttl,
                json.dumps(service_info)
            )
            
            self._registered = True
            logger.info(
                f"Service registered: {self.service_name} ({self.service_id}) "
                f"at {self.host}:{self.port}"
            )
            
            # 启动心跳任务
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to register service: {e}", exc_info=True)
            return False
    
    async def unregister(self) -> bool:
        """从 Redis 注销服务"""
        try:
            if not self._registered:
                return True
            
            # 停止心跳任务
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            if self.redis_client:
                key = f"service:{self.service_name}:{self.service_id}"
                await self.redis_client.delete(key)
                logger.info(f"Service unregistered: {self.service_name} ({self.service_id})")
            
            self._registered = False
            await self._disconnect_redis()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister service: {e}", exc_info=True)
            return False
    
    async def _heartbeat_loop(self):
        """心跳循环，定期更新服务信息"""
        try:
            while self._registered:
                await asyncio.sleep(self.heartbeat_interval)
                
                if not self._registered:
                    break
                
                try:
                    service_info = self._get_service_info()
                    service_info["last_seen"] = datetime.utcnow().isoformat()
                    
                    key = f"service:{self.service_name}:{self.service_id}"
                    await self.redis_client.setex(
                        key,
                        self.ttl,
                        json.dumps(service_info)
                    )
                    
                    logger.debug(f"Heartbeat sent for service {self.service_id}")
                    
                except Exception as e:
                    logger.warning(f"Heartbeat failed: {e}")
                    # 如果心跳失败，尝试重新连接
                    try:
                        await self._disconnect_redis()
                        await self._connect_redis()
                    except Exception as reconnect_error:
                        logger.error(f"Failed to reconnect to Redis: {reconnect_error}")
                        
        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}", exc_info=True)


# 全局服务注册器实例
_global_service_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> Optional[ServiceRegistry]:
    """获取全局服务注册器"""
    return _global_service_registry


def create_service_registry(
    redis_host: Optional[str] = None,
    redis_port: Optional[int] = None,
    redis_password: Optional[str] = None,
    service_name: str = "zero-agent",
    port: Optional[int] = None
) -> ServiceRegistry:
    """创建服务注册器"""
    global _global_service_registry
    
    redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
    redis_port = redis_port or int(os.getenv("REDIS_PORT", "6379"))
    redis_password = redis_password or os.getenv("REDIS_PASSWORD", None)
    port = port or int(os.getenv("API_PORT", "8082"))
    
    _global_service_registry = ServiceRegistry(
        redis_host=redis_host,
        redis_port=redis_port,
        redis_password=redis_password,
        service_name=service_name,
        port=port,
        ttl=int(os.getenv("SERVICE_TTL", "60")),
        heartbeat_interval=int(os.getenv("SERVICE_HEARTBEAT_INTERVAL", "15"))
    )
    
    return _global_service_registry
