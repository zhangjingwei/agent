"""
MCP客户端实现 - 支持 stdio 传输和 gRPC 传输
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

def _load_mcp_protocol_version():
    """
    加载 MCP 协议版本
    
    Returns:
        str: MCP 协议版本
        
    Raises:
        ImportError: 如果 mcp 包未安装
    """
    try:
        from mcp.types import LATEST_PROTOCOL_VERSION
        logger.debug(f"MCP 协议版本: {LATEST_PROTOCOL_VERSION}")
        return LATEST_PROTOCOL_VERSION
    except ImportError as e:
        error_msg = "MCP 包未安装，请运行: pip install mcp"
        logger.error(error_msg)
        raise ImportError(error_msg) from e

def get_mcp_protocol_version() -> str:
    """
    获取 MCP 协议版本
    
    Returns:
        str: MCP 协议版本
        
    Raises:
        ImportError: 如果 mcp 包未安装
    """
    if 'LATEST_PROTOCOL_VERSION' not in _MCP_CONSTANTS:
        _MCP_CONSTANTS['LATEST_PROTOCOL_VERSION'] = _load_mcp_protocol_version()
        logger.info(f"MCP 协议版本: {_MCP_CONSTANTS['LATEST_PROTOCOL_VERSION']}")
    return _MCP_CONSTANTS['LATEST_PROTOCOL_VERSION']


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
            # 确保在异常情况下也清理资源
            try:
                await self.disconnect()
            except Exception as cleanup_error:
                logger.warning(f"清理失败连接时出错 {self.config.id}: {str(cleanup_error)}")
            raise

    async def disconnect(self):
        """断开连接（终止进程）"""
        # 设置停止标志，让读取线程退出
        self._stop_reading = True

        # 取消所有待处理的请求，避免资源泄漏
        for request_id, future in list(self._pending_requests.items()):
            if not future.done():
                try:
                    future.cancel()
                    # 设置超时异常，避免 Future 永远等待
                    if not future.done():
                        future.set_exception(asyncio.CancelledError(f"连接断开，请求 {request_id} 已取消"))
                except Exception as e:
                    logger.warning(f"取消待处理请求失败 {request_id}: {str(e)}")
        self._pending_requests.clear()

        # 等待读取线程退出
        if self._read_thread and self._read_thread.is_alive():
            try:
                self._read_thread.join(timeout=2)
                if self._read_thread.is_alive():
                    logger.warning(f"读取线程未能及时退出 {self.config.id}")
            except Exception as e:
                logger.warning(f"等待读取线程退出时出错 {self.config.id}: {str(e)}")

        # 清理进程资源
        if self.process:
            try:
                # 关闭标准输入，通知进程退出
                if self.process.stdin:
                    try:
                        self.process.stdin.close()
                    except Exception as e:
                        logger.debug(f"关闭 stdin 时出错 {self.config.id}: {str(e)}")

                # 终止进程
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"MCP服务器进程 {self.config.id} 未能正常终止，强制杀死")
                    try:
                        self.process.kill()
                        self.process.wait()
                    except Exception as e:
                        logger.warning(f"强制杀死进程时出错 {self.config.id}: {str(e)}")

                # 确保所有文件描述符都已关闭
                if self.process.stdout:
                    try:
                        self.process.stdout.close()
                    except Exception:
                        pass
                if self.process.stderr:
                    try:
                        self.process.stderr.close()
                    except Exception:
                        pass

            except Exception as e:
                logger.warning(f"清理MCP服务器进程时出错 {self.config.id}: {str(e)}")
            finally:
                # 确保进程对象被清理
                self.process = None

        # 清理事件循环引用
        self._loop = None

        logger.info(f"已断开MCP服务器连接 {self.config.id}")

    def _read_output_sync(self):
        """同步读取输出（在单独线程中运行）"""
        if not self.process or not self.process.stdout:
            return

        try:
            while not self._stop_reading:
                try:
                    line = self.process.stdout.readline()
                    if not line:
                        # EOF 或进程已退出
                        if not self._stop_reading:
                            logger.warning(f"MCP服务器 {self.config.id} 输出流已关闭")
                        break

                    # 在事件循环中处理响应
                    if self._loop and not self._loop.is_closed():
                        try:
                            asyncio.run_coroutine_threadsafe(
                                self._handle_response(line.strip()),
                                self._loop
                            )
                        except RuntimeError as e:
                            # 事件循环可能已关闭
                            if "Event loop is closed" in str(e) or "Event loop is running" in str(e):
                                logger.debug(f"事件循环不可用，停止读取 {self.config.id}")
                                break
                            raise
                except (ValueError, OSError) as e:
                    # 文件描述符已关闭或其他 I/O 错误
                    if not self._stop_reading:
                        logger.debug(f"读取MCP输出时出错（可能是正常关闭） {self.config.id}: {str(e)}")
                    break
                except Exception as e:
                    if not self._stop_reading:
                        logger.error(f"读取MCP输出时出错 {self.config.id}: {str(e)}")
                    break
        finally:
            # 确保线程退出时清理
            logger.debug(f"读取线程退出 {self.config.id}")

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
