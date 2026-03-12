"""
Core Registry Module - 服务注册管理模块

本模块提供服务注册管理的核心功能。
旧管理器（StateManager, PersistenceManager, CacheManager）已废弃，
功能已迁移到 core/cache/ 目录。

模块结构：
- main_registry: ServiceRegistry 主类（门面模式）
- base: 基础类和接口定义
- service_manager: 服务生命周期管理
- tool_manager: 工具信息处理和管理
- session_manager: 会话管理
- mapping_manager: 映射管理
- utils: 工具函数和辅助方法
"""

from .base import (
    BaseManager,
    ServiceManagerInterface,
    ToolManagerInterface,
    SessionManagerInterface,
)
from .main_registry import ServiceRegistry
from .mapping_manager import MappingManager
from .service_manager import ServiceManager
from .session_manager import SessionManager
from .tool_manager import ToolManager
# 导出工具类
from .utils import (
    JSONSchemaUtils,
    ConfigUtils,
    ServiceUtils,
    DataUtils,
    ValidationUtils,
    extract_description_from_schema,
    extract_type_from_schema
)

__all__ = [
    # 主要导出
    'ServiceRegistry',

    # 管理器类
    'SessionManager',
    'ToolManager',
    'ServiceManager',
    'MappingManager',

    # 基础接口
    'BaseManager',
    'ServiceManagerInterface',
    'ToolManagerInterface',
    'SessionManagerInterface',

    # 工具类
    'JSONSchemaUtils',
    'ConfigUtils',
    'ServiceUtils',
    'DataUtils',
    'ValidationUtils',
    'extract_description_from_schema',
    'extract_type_from_schema'
]

# 模块版本和状态
__version__ = "2.1.0"
__status__ = "已清理旧接口代码"

# 模块信息
__author__ = "Core Registry Refactoring Team"
__description__ = "服务注册管理模块（已清理旧接口代码）"
__all_managers__ = [
    'SessionManager',
    'ToolManager',
    'ServiceManager',
    'MappingManager'
]

def get_module_info():
    """获取模块信息"""
    return {
        "version": __version__,
        "status": __status__,
        "active_managers": len(__all_managers__) + 1,
        "available_managers": __all_managers__ + ["ServiceRegistry"],
        "removed_managers": ["StateManager", "PersistenceManager", "CacheManager", "ManagerFactory", "ManagerCoordinator"],
        "migration_note": "旧管理器功能已迁移到 core/cache/ 目录"
    }
