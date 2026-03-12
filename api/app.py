"""
MCPStore API 服务 - 改进版
支持 CLI 启动时的 URL 前缀配置
"""

import logging

from mcpstore import LoggingConfig
# 导入应用工厂
from .api_app import create_app

# 统一日志配置：仅在尚未初始化时进行
if not LoggingConfig._configured:  # type: ignore[attr-defined]
    LoggingConfig.setup_logging(debug="INFO")

logger = logging.getLogger(__name__)

# 🆕 URL 前缀配置（不再使用环境变量）
url_prefix = ""

if url_prefix:
    logger.info(f"Creating app with URL prefix: {url_prefix}")
else:
    logger.info("Creating app without URL prefix")

# 创建应用实例（CLI 启动时使用）
# store=None 表示使用默认配置
app = create_app(store=None, url_prefix=url_prefix)
