"""
MCP客户端实现 - 仅支持 stdio 传输
"""

import asyncio
import json
import logging
import os
import subprocess
import threading
from typing import Dict, Any, List, Optional

from config.models import MCPConfig

logger = logging.getLogger(__name__)

# 预导入 MCP 常量，避免异步环境中的动态导入问题
_MCP_CONSTANTS = {}

def _safe_import_mcp():
    """
    安全地导入 MCP 模块，避免各种导入问题

    返回:
        dict: 包含导入结果的字典
            - success: bool, 是否成功导入
            - LATEST_PROTOCOL_VERSION: str or None
            - error: Exception or None
    """
    result = {
        'success': False,
        'LATEST_PROTOCOL_VERSION': None,
        'error': None
    }

    # 方法1: 直接导入
    try:
        from mcp.types import LATEST_PROTOCOL_VERSION
        result.update({
            'success': True,
            'LATEST_PROTOCOL_VERSION': LATEST_PROTOCOL_VERSION
        })
        logger.debug(f"MCP 直接导入成功: {LATEST_PROTOCOL_VERSION}")
        return result
    except ImportError:
        pass  # 继续尝试其他方法

    # 方法2: 使用 importlib
    try:
        import importlib
        mcp_types = importlib.import_module('mcp.types')
        result.update({
            'success': True,
            'LATEST_PROTOCOL_VERSION': getattr(mcp_types, 'LATEST_PROTOCOL_VERSION', None)
        })
        if result['LATEST_PROTOCOL_VERSION']:
            logger.debug(f"MCP importlib 导入成功: {result['LATEST_PROTOCOL_VERSION']}")
            return result
    except Exception as e:
        result['error'] = e

    # 方法3: 使用 __import__
    try:
        mcp_types = __import__('mcp.types', fromlist=['LATEST_PROTOCOL_VERSION'])
        result.update({
            'success': True,
            'LATEST_PROTOCOL_VERSION': getattr(mcp_types, 'LATEST_PROTOCOL_VERSION', None)
        })
        if result['LATEST_PROTOCOL_VERSION']:
            logger.debug(f"MCP __import__ 导入成功: {result['LATEST_PROTOCOL_VERSION']}")
            return result
    except Exception as e:
        if not result['error']:
            result['error'] = e

    # 方法4: 检查已安装版本
    try:
        import pkg_resources
        version = pkg_resources.get_distribution('mcp').version
        # 根据版本推断协议版本
        if version.startswith('1.'):
            result.update({
                'success': True,
                'LATEST_PROTOCOL_VERSION': '2025-11-25'  # MCP 1.x 的最新版本
            })
            logger.debug(f"MCP 版本推断成功: {result['LATEST_PROTOCOL_VERSION']}")
            return result
    except Exception:
        pass

    # 降级方案：使用已知版本
    result.update({
        'success': True,
        'LATEST_PROTOCOL_VERSION': '2025-11-25'  # 当前最新版本
    })
    logger.warning(f"所有 MCP 导入方法都失败，使用降级版本: {result['LATEST_PROTOCOL_VERSION']}")
    if result['error']:
        logger.warning(f"导入错误详情: {result['error']}")

    return result

def _load_mcp_constants():
    """预加载 MCP 相关常量"""
    global _MCP_CONSTANTS
    result = _safe_import_mcp()

    if result['success']:
        _MCP_CONSTANTS['LATEST_PROTOCOL_VERSION'] = result['LATEST_PROTOCOL_VERSION']
        logger.info(f"MCP 常量加载成功: {result['LATEST_PROTOCOL_VERSION']}")
    else:
        # 最后的降级方案
        _MCP_CONSTANTS['LATEST_PROTOCOL_VERSION'] = '2025-11-25'
        logger.error("MCP 常量加载完全失败，使用硬编码版本")

# 在模块导入时立即加载常量
_load_mcp_constants()

def get_mcp_protocol_version() -> str:
    """获取 MCP 协议版本"""
    return _MCP_CONSTANTS.get('LATEST_PROTOCOL_VERSION', '2025-11-25')


class MCPClient:
    """MCP客户端 - 仅支持 stdio 传输"""

    def __init__(self, config: MCPConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._read_thread: Optional[threading.Thread] = None
        self._stop_reading = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def connect(self):
        """连接到MCP服务器（启动进程）"""
        try:
            # 设置环境变量
            env = os.environ.copy()
            env.update(self.config.env)

            logger.info(f"启动MCP服务器进程 {self.config.id}: {self.config.command} {' '.join(self.config.args)}")

            # 启动MCP服务器进程
            self.process = subprocess.Popen(
                [self.config.command] + self.config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=self.config.working_dir,
                text=True,
                bufsize=1
            )

            # 保存当前事件循环的引用
            self._loop = asyncio.get_event_loop()

            # 启动异步读取线程
            self._stop_reading = False
            self._read_thread = threading.Thread(target=self._read_output_sync)
            self._read_thread.daemon = True
            self._read_thread.start()

            logger.info(f"已启动MCP服务器进程 {self.config.id} (PID: {self.process.pid})")

            # 等待一会儿确保进程启动
            await asyncio.sleep(2)

            # 检查进程是否还在运行
            if self.process.poll() is not None:
                stderr_output = ""
                if self.process.stderr:
                    stderr_output = self.process.stderr.read()
                stdout_output = ""
                if self.process.stdout:
                    stdout_output = self.process.stdout.read()
                logger.error(f"MCP服务器进程已退出 {self.config.id}, 退出码: {self.process.returncode}")
                logger.error(f"stderr: {stderr_output}")
                logger.error(f"stdout: {stdout_output}")
                raise Exception(f"MCP服务器进程启动失败 (退出码: {self.process.returncode}): stderr={stderr_output}")

            # 发送 MCP 初始化请求
            logger.info(f"发送 MCP 初始化请求到 {self.config.id}")
            init_result = await self._send_initialize()
            logger.info(f"MCP服务器 {self.config.id} 初始化完成: {init_result.get('serverInfo', {}).get('name', 'unknown')}")

            logger.info(f"MCP服务器 {self.config.id} 连接和初始化成功")

        except Exception as e:
            logger.error(f"连接MCP服务器失败 {self.config.id}: {str(e)}")
            await self.disconnect()
            raise

    async def disconnect(self):
        """断开连接（终止进程）"""
        self._stop_reading = True

        if self.process:
            try:
                # 取消所有待处理的请求
                for future in self._pending_requests.values():
                    if not future.done():
                        future.cancel()

                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"MCP服务器进程 {self.config.id} 未能正常终止，强制杀死")
                    self.process.kill()
                    self.process.wait()
            except Exception as e:
                logger.warning(f"清理MCP服务器进程时出错 {self.config.id}: {str(e)}")

        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=2)

        self._pending_requests.clear()
        logger.info(f"已断开MCP服务器连接 {self.config.id}")

    def _read_output_sync(self):
        """同步读取输出（在单独线程中运行）"""
        if not self.process or not self.process.stdout:
            return

        while not self._stop_reading:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break

                # 在事件循环中处理响应
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._handle_response(line.strip()),
                        self._loop
                    )
            except Exception as e:
                if not self._stop_reading:
                    logger.error(f"读取MCP输出时出错 {self.config.id}: {str(e)}")
                break

    async def _handle_response(self, line: str):
        """处理响应行"""
        try:
            response = json.loads(line)
            request_id = response.get("id")

            if request_id and request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                if not future.done():
                    if "error" in response:
                        future.set_exception(Exception(response["error"]["message"]))
                    else:
                        future.set_result(response.get("result"))
        except json.JSONDecodeError:
            logger.warning(f"收到无效的JSON响应 {self.config.id}: {line}")
        except Exception as e:
            logger.error(f"处理MCP响应时出错 {self.config.id}: {str(e)}")

    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送MCP请求"""
        if not self.process or not self.process.stdin:
            raise Exception("MCP服务器进程未启动")

        request_id = str(self._request_id)
        self._request_id += 1

        request: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method
        }

        # MCP 规范要求所有请求都包含 params 字段
        if params is not None:
            request["params"] = params
        else:
            request["params"] = {}

        # 创建等待响应的Future
        future: asyncio.Future[Dict[str, Any]] = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # 发送请求
            json_request = json.dumps(request) + "\n"
            self.process.stdin.write(json_request)
            self.process.stdin.flush()

            # 等待响应
            result = await asyncio.wait_for(future, timeout=self.config.timeout / 1000)
            return result

        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise Exception(f"请求超时: {request_id}")
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise

    async def _send_initialize(self) -> Dict[str, Any]:
        """发送 MCP 初始化请求"""
        # 使用预加载的常量，避免异步环境中的动态导入
        protocol_version = get_mcp_protocol_version()

        init_request = {
            "jsonrpc": "2.0",
            "id": str(self._request_id),
            "method": "initialize",
            "params": {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": {
                    "name": "universal-agent-mcp-client",
                    "version": "1.0.0"
                }
            }
        }
        self._request_id += 1

        # 创建等待响应的Future
        future: asyncio.Future[Dict[str, Any]] = asyncio.Future()
        self._pending_requests[init_request["id"]] = future

        try:
            # 发送初始化请求
            json_request = json.dumps(init_request) + "\n"
            self.process.stdin.write(json_request)
            self.process.stdin.flush()

            # 等待响应
            result = await asyncio.wait_for(future, timeout=self.config.timeout / 1000)

            # 发送初始化完成确认
            await self._send_initialized()

            return result

        except asyncio.TimeoutError:
            self._pending_requests.pop(init_request["id"], None)
            raise Exception(f"初始化请求超时")
        except Exception as e:
            self._pending_requests.pop(init_request["id"], None)
            raise

    async def _send_initialized(self):
        """发送 initialized 通知"""
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }

        try:
            json_notification = json.dumps(initialized_notification) + "\n"
            self.process.stdin.write(json_notification)
            self.process.stdin.flush()
            logger.debug(f"发送 initialized 通知到 {self.config.id}")
        except Exception as e:
            logger.warning(f"发送 initialized 通知失败 {self.config.id}: {str(e)}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        logger.info(f"开始获取MCP服务器 {self.config.id} 的工具列表")
        try:
            result = await self._send_request("tools/list")
            tools = result.get("tools", [])
            logger.info(f"成功获取 {len(tools)} 个工具 from {self.config.id}")
            return tools
        except Exception as e:
            logger.error(f"获取MCP工具列表失败 {self.config.id}: {str(e)}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用工具"""
        try:
            result = await self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
            return result
        except Exception as e:
            logger.error(f"MCP工具调用失败 {self.config.id}.{tool_name}: {str(e)}")
            raise

    async def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具信息"""
        tools = await self.list_tools()
        for tool in tools:
            if tool.get("name") == tool_name:
                return tool
        return None
