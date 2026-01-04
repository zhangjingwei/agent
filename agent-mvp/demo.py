#!/usr/bin/env python3
"""
Universal Agent MVP 演示脚本

基于LangGraph的状态管理Agent演示
展示LangGraph驱动的对话和工具调用功能
"""

import asyncio
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
import sys
sys.path.insert(0, str(project_root))

from sdk.python import UniversalAgentSDK, SDKConfig

async def demo():
    """演示Agent功能"""
    print("Universal Agent MVP 演示")
    print("=" * 50)

    if not UniversalAgentSDK:
        print("SDK依赖未安装，请先运行:")
        print("   pip install httpx")
        return

    # 检查环境变量
    has_llm_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("SILICONFLOW_API_KEY")
    if not has_llm_key:
        print("请设置 OPENAI_API_KEY, ANTHROPIC_API_KEY 或 SILICONFLOW_API_KEY 环境变量")
        print("当前配置使用硅基流动deepseek模型，推荐设置:")
        print("   export SILICONFLOW_API_KEY='your-api-key'")
        print("   export LLM_PROVIDER='siliconflow'")
        print("   export LLM_MODEL='deepseek-chat'")
        return

    # 创建SDK实例
    config = SDKConfig(
        api_url="http://localhost:8080",
        timeout=30
    )

    async with UniversalAgentSDK(config) as sdk:
        try:
            # 1. 健康检查
            print(" 健康检查...")
            health = await sdk.health_check()
            print(f" Agent状态: {health.get('status', 'unknown')}")
            print(f" Agent ID: {health.get('agent_id', 'unknown')}")
            print(f" 工具数量: {health.get('tools_count', 0)}")
            print()

            # 2. 列出可用工具
            print("🛠️  可用工具:")
            tools = await sdk.list_tools()
            for tool in tools:
                print(f"  • {tool['name']}: {tool['description']}")
            print()

            # 3. 创建会话
            print(" 创建会话...")
            session_id = await sdk.create_session("demo-agent")
            print(f" 会话ID: {session_id}")
            print()

            # 4. 测试计算器工具
            print("🔢 测试计算器工具...")
            response = await sdk.chat(session_id, "计算 123 + 456 的结果")
            print(f" Agent: {response['message']}")

            if response['tool_calls']:
                print(" 工具调用:")
                for call in response['tool_calls']:
                    print(f"  • {call['name']}({call['arguments']}) -> {call.get('result', '执行中')}")
            print()

            # 5. 测试天气查询（如果有API密钥）
            if os.getenv("WEATHER_API_KEY"):
                print("🌤️  测试天气查询...")
                response = await sdk.chat(session_id, "查询北京的天气")
                print(f" Agent: {response['message']}")

                if response['tool_calls']:
                    print(" 工具调用:")
                    for call in response['tool_calls']:
                        print(f"  • {call['name']}({call['arguments']})")
                        if call.get('result'):
                            result = call['result']
                            print(f"    📍 城市: {result.get('city', 'N/A')}")
                            print(f"    🌡️ 温度: {result.get('temperature', 'N/A')}°C")
                            print(f"    🌤️ 天气: {result.get('condition', 'N/A')}")
            else:
                print("  跳过天气查询（未设置 WEATHER_API_KEY）")
            print()

            # 6. 查看会话历史
            print(" 会话历史:")
            history = await sdk.get_history(session_id)
            for i, msg in enumerate(history, 1):
                role = "" if msg['role'] == 'user' else ""
                print(f"  {i}. {role} {msg['content'][:50]}{'...' if len(msg['content']) > 50 else ''}")
            print()

            # 7. 清理会话
            print("🧹 清理会话...")
            await sdk.clear_session(session_id)
            print(" 会话已清理")

        except Exception as e:
            print(f" 演示失败: {e}")
            import traceback
            traceback.print_exc()


async def test_api_endpoints():
    """测试API端点（不需要真实LLM）"""
    print(" 测试API端点...")
    print("=" * 50)

    if not UniversalAgentSDK:
        print(" SDK依赖未安装，请先运行:")
        print("   pip install httpx")
        return

    config = SDKConfig(
        api_url="http://localhost:8080",
        timeout=30
    )

    async with UniversalAgentSDK(config) as sdk:
        try:
            # 1. 健康检查
            print(" 健康检查...")
            health = await sdk.health_check()
            print(f" Agent状态: {health.get('status', 'unknown')}")
            print(f" Agent ID: {health.get('agent_id', 'unknown')}")
            print()

            # 2. 列出工具
            print("🛠️  可用工具:")
            tools = await sdk.list_tools()
            for tool in tools:
                print(f"  • {tool['name']}: {tool['description']}")
            print()

            # 3. 创建会话
            print(" 创建会话...")
            session_id = await sdk.create_session("demo-agent")
            print(f" 会话ID: {session_id}")
            print()

            # 4. 测试会话历史（空的历史）
            print(" 会话历史 (空):")
            history = await sdk.get_history(session_id)
            print(f"  消息数量: {len(history)}")
            print()

            print(" API端点测试完成！配置正确。")

        except Exception as e:
            print(f" API测试失败: {e}")
            print(" 请确保:")
            print("   1. 服务器已启动: python -m scripts.start")
            print("   2. 设置了有效的API密钥")


def test_curl_commands():
    """显示正确的curl测试命令"""
    print("🔗 正确的API调用示例:")
    print("=" * 50)
    print()
    print("# 1. 创建会话")
    print('curl -X POST http://localhost:8080/sessions \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"metadata": {"user_id": "test-user"}}\'')
    print()
    print("# 2. 发送消息 (替换SESSION_ID)")
    print('curl -X POST http://localhost:8080/sessions/SESSION_ID/chat \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"message": "你好！请介绍一下你自己"}\'')
    print()
    print("# 3. 获取会话历史")
    print('curl -X GET http://localhost:8080/sessions/SESSION_ID/history')
    print()
    print("# 4. 健康检查")
    print('curl -X GET http://localhost:8080/health')
    print()
    print(" 注意: 端点是 /sessions/{session_id}/chat 而不是 /chat")


def print_setup_instructions():
    """打印设置说明"""
    print(" 设置说明:")
    print("1. 确保已启动Agent服务:")
    print("   python -m scripts.start")
    print()
    print("2. 设置环境变量:")
    print("   # 推荐使用硅基流动deepseek模型:")
    print("   export SILICONFLOW_API_KEY='your-siliconflow-key'")
    print("   export LLM_PROVIDER='siliconflow'")
    print("   export LLM_MODEL='deepseek-chat'")
    print()
    print("   # 其他选项:")
    print("   export OPENAI_API_KEY='your-openai-key'")
    print("   export ANTHROPIC_API_KEY='your-anthropic-key'")
    print("   export WEATHER_API_KEY='your-weather-key'  # 可选")
    print()
    print("3. 查看curl命令示例:")
    print("   python demo.py --curl")
    print()
    print("4. 测试API端点:")
    print("   python demo.py --test-api")
    print()
    print("5. 运行完整演示:")
    print("   python demo.py")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print_setup_instructions()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test-api":
        asyncio.run(test_api_endpoints())
    elif len(sys.argv) > 1 and sys.argv[1] == "--curl":
        test_curl_commands()
    else:
        asyncio.run(demo())
