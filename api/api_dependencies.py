"""
MCPStore API Dependencies - 改进版
使用 contextvars 实现线程安全的 Store 管理
"""

from contextvars import ContextVar
from typing import Optional

from mcpstore import MCPStore

# 使用 contextvars（Python 3.7+ 标准库，线程安全）
_store_context: ContextVar[Optional[MCPStore]] = ContextVar('store', default=None)


def get_store() -> MCPStore:
    """
    获取当前请求的 Store 实例（线程安全）

    这个函数会从请求上下文中获取 store 实例。
    上下文由中间件自动设置，确保每个请求都有独立的上下文。

    Returns:
        MCPStore: 当前请求的 store 实例

    Raises:
        RuntimeError: 如果 store 未初始化

    Note:
        - 用户代码无需修改，函数签名保持不变
        - 支持多 worker 部署（线程安全）
        - 每个请求有独立的上下文（互不干扰）
    """
    store = _store_context.get()
    if store is None:
        raise RuntimeError(
            "Store not initialized in request context. "
            "This should not happen if the middleware is properly configured."
        )
    return store


def set_request_store(store: MCPStore) -> None:
    """
    为当前请求设置 Store 实例

    此函数由中间件调用，用户代码不需要直接调用。

    Args:
        store: MCPStore 实例
    """
    _store_context.set(store)


def has_store_context() -> bool:
    """
    检查当前上下文是否已设置 store 实例

    Returns:
        bool: 如果已设置返回 True，否则返回 False
    """
    return _store_context.get() is not None
