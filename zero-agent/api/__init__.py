"""
API网关
"""

# 使用延迟导入避免模块冲突
# 当执行 `python -m api.app` 时，如果 __init__.py 中直接导入 app，
# 会导致 'api.app' 在 sys.modules 中，从而产生警告
# 
# 使用 __getattr__ 实现延迟导入（Python 3.7+）
def __getattr__(name):
    if name == 'app':
        from .app import app
        return app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = ['app']
