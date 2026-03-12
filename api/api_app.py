"""
MCPStore API Application Factory - 改进版
支持自定义 URL 前缀和两种启动方式
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Request, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from mcpstore import MCPStore
from .api_dependencies import set_request_store, get_store
from .api_exceptions import (
    mcpstore_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler
)

logger = logging.getLogger(__name__)


def create_app(
    store: Optional[MCPStore] = None,
    url_prefix: str = ""
) -> FastAPI:
    """
    创建 FastAPI 应用实例（改进版）

    Args:
        store: MCPStore 实例。如果为 None，将使用默认配置创建。
        url_prefix: URL 前缀，如 "/api/v1"。默认为空字符串（无前缀）。

    Returns:
        FastAPI: 配置好的应用实例

    Example:
        # 无前缀（默认）
        app = create_app()
        # URL: /for_store/list_services

        # 带前缀
        app = create_app(url_prefix="/api/v1")
        # URL: /api/v1/for_store/list_services

        # 使用指定的 store
        my_store = MCPStore.setup_store()
        app = create_app(store=my_store, url_prefix="/api")
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """应用生命周期管理"""
        # 确定使用的 store 实例
        if store is None:
            # CLI 启动：创建默认 store
            logger.info("No store provided, creating default store")
            app_store = MCPStore.setup_store()
        else:
            # 代码启动：使用传入的 store
            logger.info("Using provided store instance")
            app_store = store

        # 保存到应用状态
        app.state.store = app_store
        app.state.url_prefix = url_prefix  # 保存 URL 前缀配置

        logger.info("Initializing MCPStore API service...")

        if app_store.is_using_data_space():
            workspace_dir = app_store.get_workspace_dir()
            logger.info(f"Using data space: {workspace_dir}")
        else:
            logger.info("Using default configuration")

        # 初始化编排器
        try:
            logger.info("Initializing orchestrator...")
            await app_store.orchestrator.setup()

            logger.info("MCPStore API service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to setup orchestrator: {e}")
            raise

        yield  # 应用运行期间

        # 应用关闭时的清理
        logger.info("Shutting down MCPStore API service...")

        try:
            await app_store.orchestrator.cleanup()
            logger.info("MCPStore API service shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    # 创建应用实例
    logger.info(f"Creating FastAPI app with URL prefix: '{url_prefix or '(none)'}'")

    app = FastAPI(
        title="MCPStore API",
        description="MCPStore HTTP API Service",
        version="1.0.0",
        lifespan=lifespan
    )

    # 记录应用启动时间（用于 health check）
    app._start_time = time.time()

    # 添加中间件：为每个请求设置 store 上下文（线程安全）
    @app.middleware("http")
    async def store_context_middleware(request: Request, call_next):
        """
        将 store 注入到请求上下文

        这个中间件确保每个请求都有独立的 store 上下文，
        解决了全局单例的线程安全问题。
        """
        store_instance = request.app.state.store
        set_request_store(store_instance)  # 设置到当前请求上下文

        response = await call_next(request)
        return response

    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 导入并注册路由（应用 URL 前缀）
    from .api import router

    if url_prefix:
        # 如果有前缀，创建一个带前缀的路由器
        logger.info(f"Applying URL prefix: {url_prefix}")
        app.include_router(router, prefix=url_prefix)
    else:
        # 无前缀，直接注册
        app.include_router(router)

    # 注册统一的异常处理器
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    from .api_exceptions import MCPStoreException
    app.add_exception_handler(MCPStoreException, mcpstore_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # 添加请求日志和性能监控中间件
    @app.middleware("http")
    async def log_requests_and_monitor(request: Request, call_next):
        """记录请求日志并监控性能"""
        start_time = time.time()

        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000

            # 添加响应头
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

            # 只记录错误和较慢的请求
            if response.status_code >= 400 or process_time > 1000:
                logger.info(
                    f"{request.method} {request.url.path} - "
                    f"Status: {response.status_code}, Duration: {process_time:.2f}ms"
                )
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"{request.method} {request.url.path} - "
                f"Error: {e}, Duration: {process_time:.2f}ms"
            )
            raise

    # 添加 API 文档入口（根路径或带前缀）
    @app.get("/doc" if not url_prefix else f"{url_prefix}/doc")
    async def api_documentation():
        """
        API 文档入口

        返回所有可用的 API 文档链接
        """
        from mcpstore import ResponseBuilder

        doc_prefix = url_prefix or ""

        return ResponseBuilder.success(
            message="MCPStore API Documentation",
            data={
                "documentation": {
                    "swagger_ui": {
                        "url": f"{doc_prefix}/docs",
                        "description": "Swagger UI - 交互式 API 文档，可以直接测试接口"
                    },
                    "redoc": {
                        "url": f"{doc_prefix}/redoc",
                        "description": "ReDoc - 更美观的 API 文档展示"
                    },
                    "openapi_json": {
                        "url": f"{doc_prefix}/openapi.json",
                        "description": "OpenAPI 规范文件（JSON 格式）"
                    }
                },
                "quick_links": {
                    "api_root": doc_prefix or "/",
                    "health_check": f"{doc_prefix}/health",
                    "example_service_list": f"{doc_prefix}/for_store/list_services"
                },
                "url_prefix": url_prefix if url_prefix else "(none)"
            }
        )

    # 添加健康检查端点（根路径或带前缀）
    @app.get("/health" if not url_prefix else f"{url_prefix}/health")
    async def health_check():
        """健康检查端点"""
        from mcpstore import ResponseBuilder, ErrorCode

        try:
            current_store = get_store()

            # 统计服务数量
            try:
                context = current_store.for_store()
                services = context.list_services()
                services_count = len(services)
                agents_count = len(current_store.list_all_agents()) if hasattr(current_store, 'list_all_agents') else 0
            except:
                services_count = 0
                agents_count = 0

            # 计算运行时间
            uptime_seconds = int(time.time() - getattr(app, '_start_time', time.time()))

            return ResponseBuilder.success(
                message="System is healthy",
                data={
                    "status": "healthy",
                    "uptime_seconds": uptime_seconds,
                    "services_count": services_count,
                    "agents_count": agents_count,
                    "url_prefix": url_prefix if url_prefix else "(none)"
                }
            )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            response = ResponseBuilder.error(
                code=ErrorCode.INTERNAL_ERROR,
                message="Health check failed",
                details={"error": str(e)}
            )
            return JSONResponse(
                status_code=503,
                content=response.dict(exclude_none=True)
            )

    logger.info("FastAPI app created successfully")
    return app


# 为了向后兼容，保留无参数版本
def create_default_app() -> FastAPI:
    """
    创建默认应用（向后兼容）

    这个函数保持与旧版本的兼容性。
    """
    return create_app()


# 为了向后兼容，在模块级别创建默认app实例
# 注意：这个实例用于 CLI 启动（mcpstore run api）
app = create_app()
