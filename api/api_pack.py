"""
API 入口打包（便捷导出）

用途：
- 从单个文件导入常用对象，名称直观，减少多处导入。
- 支持主路由/子路由、依赖注入函数、应用工厂。
"""

# 主路由（聚合 store/agent/cache）
from .api import router as api_main_router
from .api_agent import agent_router as api_agent_router
# 应用工厂
from .api_app import create_app as api_create_app
from .api_cache import router as api_cache_router
# 依赖注入
from .api_dependencies import get_store as api_get_store
from .api_dependencies import set_request_store as api_set_store
# 子路由
from .api_store import store_router as api_store_router

__all__ = [
    "api_main_router",   # 总路由
    "api_store_router",  # Store 路由
    "api_agent_router",  # Agent 路由
    "api_cache_router",  # Cache 路由
    "api_get_store",     # 获取 MCPStore 的依赖函数
    "api_set_store",     # 设置 MCPStore 到请求上下文
    "api_create_app",    # FastAPI 应用工厂
]
