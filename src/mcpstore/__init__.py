"""
MCPStore - Model Context Protocol Service Management SDK
A composable, ready-to-use MCP toolkit for AI Agents and rapid integration.
"""
 
__version__ = "1.5.18"


# ===== Lazy loading implementation =====
def __getattr__(name: str):
    """Lazy-load public objects on first access to reduce import overhead."""

    # Core classes
    if name in ("LoggingConfig", "MCPStore"):
        from mcpstore.config.config import LoggingConfig
        from mcpstore.core.store import MCPStore

        globals().update({
            "LoggingConfig": LoggingConfig,
            "MCPStore": MCPStore,
        })
        return globals()[name]

    # Cache config classes
    if name in ("MemoryConfig", "RedisConfig"):
        from mcpstore.config import MemoryConfig, RedisConfig

        globals().update({
            "MemoryConfig": MemoryConfig,
            "RedisConfig": RedisConfig,
        })
        return globals()[name]

    # Core model classes
    if name in ("ServiceInfo", "ServiceConnectionState", "ToolInfo", "ToolExecutionRequest"):
        from mcpstore.core.models.service import ServiceInfo, ServiceConnectionState
        from mcpstore.core.models.tool import ToolInfo, ToolExecutionRequest

        globals().update({
            "ServiceInfo": ServiceInfo,
            "ServiceConnectionState": ServiceConnectionState,
            "ToolInfo": ToolInfo,
            "ToolExecutionRequest": ToolExecutionRequest,
        })
        return globals()[name]

    if name in ("APIResponse", "ErrorDetail", "ResponseMeta", "Pagination", "ResponseBuilder", "timed_response"):
        from mcpstore.core.models.response import APIResponse, ErrorDetail, ResponseMeta, Pagination
        from mcpstore.core.models.response_builder import ResponseBuilder
        from mcpstore.core.models.response_decorators import timed_response

        globals().update({
            "APIResponse": APIResponse,
            "ErrorDetail": ErrorDetail,
            "ResponseMeta": ResponseMeta,
            "Pagination": Pagination,
            "ResponseBuilder": ResponseBuilder,
            "timed_response": timed_response,
        })
        return globals()[name]

    if name == "ErrorCode":
        from mcpstore.core.models.error_codes import ErrorCode

        globals()["ErrorCode"] = ErrorCode
        return ErrorCode

    if name == "ClientIDGenerator":
        from mcpstore.core.utils.id_generator import ClientIDGenerator

        globals()["ClientIDGenerator"] = ClientIDGenerator
        return ClientIDGenerator

    if name == "PerspectiveResolver":
        from mcpstore.utils.perspective_resolver import PerspectiveResolver

        globals()["PerspectiveResolver"] = PerspectiveResolver
        return PerspectiveResolver

    # Core exception classes
    if name in ("MCPStoreException", "ServiceNotFoundException", "ToolExecutionError", "ValidationException"):
        from mcpstore.core.exceptions import (
            MCPStoreException,
            ServiceNotFoundException,
            ToolExecutionError,
            ValidationException,
        )

        globals().update({
            "MCPStoreException": MCPStoreException,
            "ServiceNotFoundException": ServiceNotFoundException,
            "ToolExecutionError": ToolExecutionError,
            "ValidationException": ValidationException,
        })
        return globals()[name]

    # Adapter common utilities
    if name in ("call_tool_response_helper", "ToolCallView"):
        from mcpstore.adapters.common import call_tool_response_helper, ToolCallView

        globals().update({
            "call_tool_response_helper": call_tool_response_helper,
            "ToolCallView": ToolCallView,
        })
        return globals()[name]

    # Adapter classes (lazy import, fall back to None if adapter is not installed)
    adapters_mapping = {
        "LangChainAdapter": "langchain_adapter",
        "OpenAIAdapter": "openai_adapter",
        "AutoGenAdapter": "autogen_adapter",
        "LlamaIndexAdapter": "llamaindex_adapter",
        "CrewAIAdapter": "crewai_adapter",
        "SemanticKernelAdapter": "semantic_kernel_adapter",
    }

    if name in adapters_mapping:
        module_name = adapters_mapping[name]
        try:
            module = __import__(f"mcpstore.adapters.{module_name}", fromlist=[name])
            adapter_class = getattr(module, name)
        except ImportError:
            adapter_class = None

        globals()[name] = adapter_class
        return adapter_class

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# ===== Public Exports (API surface) =====
__all__ = [
    # Core Classes
    "MCPStore",
    "LoggingConfig",

    # Cache Config
    "MemoryConfig",
    "RedisConfig",

    # Model Classes
    "ServiceInfo",
    "ServiceConnectionState",
    "ToolInfo",
    "ToolExecutionRequest",
    "APIResponse",
    "ResponseBuilder",
    "timed_response",
    "ErrorDetail",
    "ResponseMeta",
    "Pagination",
    "ErrorCode",
    "ClientIDGenerator",
    "PerspectiveResolver",

    # Exception Classes
    "MCPStoreException",
    "ServiceNotFoundException",
    "ToolExecutionError",
    "ValidationException",

    # Adapter Utilities
    "call_tool_response_helper",
    "ToolCallView",

    # Adapters
    "LangChainAdapter",
    "OpenAIAdapter",
    "AutoGenAdapter",
    "LlamaIndexAdapter",
    "CrewAIAdapter",
    "SemanticKernelAdapter",
]
