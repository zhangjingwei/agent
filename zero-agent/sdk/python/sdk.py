"""
Universal Agent Python SDK
"""

from typing import Dict, List, Optional, Any, Iterator
import json
import httpx


class SDKConfig:
    """SDK配置"""

    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout


class ZeroAgentEngineSDK:
    """
    Universal Agent Python SDK

    通用Agent框架的Python客户端SDK
    """

    def __init__(self, config: SDKConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=config.timeout,
            headers=self._get_headers()
        )

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            'Content-Type': 'application/json'
        }
        if self.config.api_key:
            headers['Authorization'] = f'Bearer {self.config.api_key}'
        return headers

    async def create_session(
        self,
        agent_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        创建会话

        Args:
            agent_id: Agent ID
            metadata: 可选的元数据

        Returns:
            会话ID

        Raises:
            RuntimeError: 创建失败时抛出
        """
        url = f"{self.config.api_url}/sessions"
        data = {"agent_id": agent_id}
        if metadata:
            data["metadata"] = metadata

        response = await self.client.post(url, json=data)
        response.raise_for_status()

        result = response.json()
        return result["session_id"]

    async def chat(
        self,
        session_id: str,
        message: str,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送消息（阻塞模式）

        Args:
            session_id: 会话ID
            message: 消息内容
            stream: 是否使用流式响应（MVP版本暂不支持）
            **kwargs: 其他参数

        Returns:
            响应字典

        Raises:
            RuntimeError: 请求失败时抛出
        """
        if stream:
            raise NotImplementedError("Streaming not implemented in MVP")

        url = f"{self.config.api_url}/sessions/{session_id}/chat"
        data = {
            "message": message,
            "stream": False,
            **kwargs
        }

        response = await self.client.post(url, json=data)
        response.raise_for_status()

        return response.json()

    async def chat_stream(
        self,
        session_id: str,
        message: str,
        **kwargs
    ) -> Iterator[str]:
        """
        发送消息（流式模式）- MVP版本暂不支持

        Args:
            session_id: 会话ID
            message: 消息内容
            **kwargs: 其他参数

        Yields:
            响应数据块

        Raises:
            NotImplementedError: MVP版本不支持流式
        """
        raise NotImplementedError("Streaming not implemented in MVP")

    async def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取会话历史

        Args:
            session_id: 会话ID
            limit: 限制返回的消息数量

        Returns:
            消息列表

        Raises:
            RuntimeError: 请求失败时抛出
        """
        url = f"{self.config.api_url}/sessions/{session_id}/history"
        params = {}
        if limit:
            params["limit"] = limit

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        result = response.json()
        return result["messages"]

    async def clear_session(self, session_id: str) -> bool:
        """
        清除会话

        Args:
            session_id: 会话ID

        Returns:
            是否成功

        Raises:
            RuntimeError: 请求失败时抛出
        """
        url = f"{self.config.api_url}/sessions/{session_id}"

        response = await self.client.delete(url)
        response.raise_for_status()

        result = response.json()
        return result.get("success", False)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        列出可用工具

        Returns:
            工具列表

        Raises:
            RuntimeError: 请求失败时抛出
        """
        url = f"{self.config.api_url}/tools"

        response = await self.client.get(url)
        response.raise_for_status()

        result = response.json()
        return result["tools"]

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态信息

        Raises:
            RuntimeError: 请求失败时抛出
        """
        url = f"{self.config.api_url}/health"

        response = await self.client.get(url)
        response.raise_for_status()

        return response.json()

    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# 便捷函数
def create_sdk(
    api_url: str,
    api_key: Optional[str] = None,
    timeout: int = 30
) -> ZeroAgentEngineSDK:
    """
    创建SDK实例的便捷函数

    Args:
        api_url: API服务器URL
        api_key: API密钥（可选）
        timeout: 请求超时时间（秒）

    Returns:
        SDK实例
    """
    config = SDKConfig(api_url, api_key, timeout)
    return ZeroAgentEngineSDK(config)


# 使用示例
async def example_usage():
    """使用示例"""
    # 创建SDK实例
    sdk = create_sdk("http://localhost:8080")

    try:
        # 创建会话
        session_id = await sdk.create_session("demo-agent")
        print(f"Created session: {session_id}")

        # 发送消息
        response = await sdk.chat(session_id, "计算 123 + 456 的结果")
        print(f"Response: {response['message']}")

        # 获取历史
        history = await sdk.get_history(session_id)
        print(f"History: {len(history)} messages")

        # 列出工具
        tools = await sdk.list_tools()
        print(f"Available tools: {len(tools)}")

    finally:
        await sdk.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
