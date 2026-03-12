"""
MCPStore API - Agent-level routes
Contains all Agent-level API endpoints
"""

import logging
from typing import Dict, Any, Union, List, Optional

from fastapi import APIRouter, Request, Query

from mcpstore import (
    APIResponse,
    ErrorCode,
    ResponseBuilder,
    timed_response,
    call_tool_response_helper,
)
from .api_decorators import validate_agent_id
from .api_dependencies import get_store
from .api_models import (
    SimpleToolExecutionRequest, create_enhanced_pagination_info
)

# Create Agent-level router
agent_router = APIRouter()

logger = logging.getLogger(__name__)

# === Agent-level operations ===
@agent_router.post("/for_agent/{agent_id}/add_service", response_model=APIResponse)
@timed_response
async def agent_add_service(
    agent_id: str,
    payload: Union[List[str], Dict[str, Any]]
):
    """Add service at agent level"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)
    
    # Manually aggregate details after calling add_service
    try:
        await context.bridge_execute(context.add_service_async(payload))
        
        # Aggregate detailed information（使用 async 版本）
        services = await context.bridge_execute(context.list_services_async())
        tools = await context.bridge_execute(context.list_tools_async())
        
        result = {
            "success": True,
            "message": f"Service added successfully for agent '{agent_id}'",
            "added_services": [s.get("name") if isinstance(s, dict) else getattr(s, "name", "unknown") for s in services],
            "total_services": len(services),
            "total_tools": len(tools)
        }
        
        return ResponseBuilder.success(
            message=result["message"],
            data=result
        )
    except Exception as e:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_INITIALIZATION_FAILED,
            message=f"Service operation failed for agent '{agent_id}': {str(e)}",
            details={"error": str(e)}
        )

@agent_router.get("/for_agent/{agent_id}/list_services", response_model=APIResponse)
@timed_response
async def agent_list_services(
    agent_id: str,
    # Pagination parameters (optional)
    page: Optional[int] = Query(None, ge=1, description="Page number starting from 1. No pagination when omitted."),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Items per page. No pagination when omitted."),
    # Filter parameters (optional)
    status: Optional[str] = Query(None, description="Filter by status (e.g., healthy, initializing, error)"),
    search: Optional[str] = Query(None, description="Search by service name (fuzzy match)"),
    service_type: Optional[str] = Query(None, description="Filter by service type (e.g., sse, stdio)"),
    # Sort parameters (optional)
    sort_by: Optional[str] = Query(None, description="Sort field (name, status, type, tools_count)"),
    sort_order: Optional[str] = Query(None, description="Sort direction (asc, desc)")
):
    """
    Get service list at agent level (supports pagination/filtering/sorting)

    Features:
    - All parameters are optional, returns all data when no parameters provided
    - Supports filtering by status, name, type
    - Supports sorting by multiple fields
    - Unified response format, always includes pagination field

    Examples:
    - Get all: GET /for_agent/agent1/list_services
    - Pagination: GET /for_agent/agent1/list_services?page=1&limit=10
    - Filter: GET /for_agent/agent1/list_services?status=healthy&service_type=sse
    - Search: GET /for_agent/agent1/list_services?search=weather
    - Sort: GET /for_agent/agent1/list_services?sort_by=name&sort_order=asc
    - Combined: GET /for_agent/agent1/list_services?status=healthy&page=1&limit=10&sort_by=tools_count&sort_order=desc
    """
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)

    # 1. Get all services
    all_services = await context.bridge_execute(context.list_services_async())

    # 2. Build complete service data
    services_data = []
    for service in all_services:
        service_data = {
            "name": service.name,
            "url": service.url or "",
            "command": service.command or "",
            "args": service.args or [],
            "env": service.env or {},
            "working_dir": service.working_dir or "",
            "package_name": service.package_name or "",
            "keep_alive": service.keep_alive,
            "type": service.transport_type.value if service.transport_type else 'unknown',
            "status": service.status.value if hasattr(service.status, 'value') else str(service.status),
            "tools_count": getattr(service, 'tool_count', 0),
            "client_id": service.client_id or "",
            "config": service.config or {}
        }
        services_data.append(service_data)

    # 3. Apply filtering
    filtered = services_data
    applied_filters = {}

    if status:
        filtered = [s for s in filtered if s.get("status", "").lower() == status.lower()]
        applied_filters["status"] = status

    if search:
        search_lower = search.lower()
        filtered = [s for s in filtered if search_lower in s.get("name", "").lower()]
        applied_filters["search"] = search

    if service_type:
        filtered = [s for s in filtered if s.get("type", "").lower() == service_type.lower()]
        applied_filters["service_type"] = service_type

    # 4. Apply sorting
    applied_sort = {}
    if sort_by:
        reverse = (sort_order == "desc")
        if sort_by == "name":
            filtered.sort(key=lambda s: s.get("name", ""), reverse=reverse)
        elif sort_by == "status":
            filtered.sort(key=lambda s: s.get("status", ""), reverse=reverse)
        elif sort_by == "type":
            filtered.sort(key=lambda s: s.get("type", ""), reverse=reverse)
        elif sort_by == "tools_count":
            filtered.sort(key=lambda s: s.get("tools_count", 0), reverse=reverse)

        applied_sort = {"by": sort_by, "order": sort_order or "asc"}

    filtered_count = len(filtered)

    # 5. Apply pagination
    if page is not None or limit is not None:
        # Paginate only when pagination parameters are provided
        page = page or 1
        limit = limit or 20
        start = (page - 1) * limit
        paginated = filtered[start:start + limit]
    else:
        # Return all data when no pagination parameters
        paginated = filtered

    # 6. Build unified response format (always includes pagination field)
    pagination = create_enhanced_pagination_info(page, limit, filtered_count)

    response_data = {
        "services": paginated,
        "pagination": pagination.dict()
    }

    # Add filter and sort information (if applied)
    if applied_filters:
        response_data["filters"] = applied_filters
    if applied_sort:
        response_data["sort"] = applied_sort

    return ResponseBuilder.success(
        message=f"Retrieved {len(paginated)} of {filtered_count} services for agent '{agent_id}'",
        data=response_data
    )

@agent_router.get("/for_agent/{agent_id}/agent_status", response_model=APIResponse)
@timed_response
async def agent_status(agent_id: str):
    """返回 Agent 级别的状态与统计信息（使用 SDK 封装接口）。"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)
    stats = await context.bridge_execute(
        context.get_stats_async()
    )

    return ResponseBuilder.success(
        message=f"Agent '{agent_id}' status returned",
        data=stats
    )

@agent_router.post("/for_agent/{agent_id}/reset_service", response_model=APIResponse)
@timed_response
async def agent_reset_service(agent_id: str, request: Request):
    """Reset service status at agent level (via Application Service)"""
    validate_agent_id(agent_id)
    body = await request.json()
    
    store = get_store()
    context = store.for_agent(agent_id)
    
    # Extract parameters
    identifier = body.get("identifier")
    client_id = body.get("client_id")
    service_name = body.get("service_name")

    used_identifier = service_name or identifier or client_id

    if not used_identifier:
        return ResponseBuilder.error(
            code=ErrorCode.VALIDATION_ERROR,
            message="Missing service identifier",
            field="service_name"
        )

    # 解析到全局服务名（Agent 视角 → Store 全局命名空间）
    raw = service_name or identifier or client_id
    try:
        resolved_client_id, resolved_service_name = await context.bridge_execute(
            context._resolve_client_id_async(raw, agent_id)
        )
    except Exception as e:
        return ResponseBuilder.error(
            code=ErrorCode.VALIDATION_ERROR,
            message=str(e),
            field="service_name"
        )

    global_agent_id = store.client_manager.global_agent_store_id
    app_service = store.container.service_application_service

    ok = await context.bridge_execute(
        app_service.reset_service(
            agent_id=global_agent_id,
            service_name=resolved_service_name,
            wait_timeout=0.0,
        )
    )

    if not ok:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_OPERATION_FAILED,
            message=f"Failed to reset service '{used_identifier}' for agent '{agent_id}'",
            field="service_name"
        )
    
    return ResponseBuilder.success(
        message=f"Service '{used_identifier}' reset successfully for agent '{agent_id}'",
        data={"service_name": used_identifier, "agent_id": agent_id, "status": "startup"}
    )

@agent_router.get("/for_agent/{agent_id}/list_tools", response_model=APIResponse)
@timed_response
async def agent_list_tools(
    agent_id: str,
    # Pagination parameters (optional)
    page: Optional[int] = Query(None, ge=1, description="Page number starting from 1. No pagination when omitted."),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Items per page. No pagination when omitted."),
    # Filter parameters (optional)
    search: Optional[str] = Query(None, description="Search by tool name or description (fuzzy match)"),
    service_name: Optional[str] = Query(None, description="Filter by service name (exact match)"),
    # Sort parameters (optional)
    sort_by: Optional[str] = Query(None, description="Sort field (name, service)"),
    sort_order: Optional[str] = Query(None, description="Sort direction (asc, desc)")
):
    """
    Get tool list at agent level (supports pagination/filtering/sorting)

    Features:
    - All parameters are optional, returns all data when no parameters provided
    - Supports filtering by tool name, description, service name
    - Supports sorting by name, service
    - Unified response format, always includes pagination field

    Examples:
    - Get all: GET /for_agent/agent1/list_tools
    - Pagination: GET /for_agent/agent1/list_tools?page=1&limit=20
    - Search: GET /for_agent/agent1/list_tools?search=read
    - By service: GET /for_agent/agent1/list_tools?service_name=filesystem
    - Sort: GET /for_agent/agent1/list_tools?sort_by=name&sort_order=asc
    - Combined: GET /for_agent/agent1/list_tools?service_name=filesystem&page=1&limit=10&sort_by=name
    """
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)

    # 1. Get all tools（使用 async 版本）
    all_tools = await context.bridge_execute(context.list_tools_async())

    # 2. Build tool data
    tools_data = [
        {
            "name": tool.name,
            "service": getattr(tool, 'service_name', 'unknown'),
            "description": tool.description or ""
        }
        for tool in all_tools
    ]

    # 3. Apply filtering
    filtered = tools_data
    applied_filters = {}

    if search:
        search_lower = search.lower()
        filtered = [
            t for t in filtered
            if search_lower in t.get("name", "").lower() or search_lower in t.get("description", "").lower()
        ]
        applied_filters["search"] = search

    if service_name:
        filtered = [t for t in filtered if t.get("service", "") == service_name]
        applied_filters["service_name"] = service_name

    # 4. Apply sorting
    applied_sort = {}
    if sort_by:
        reverse = (sort_order == "desc")
        if sort_by == "name":
            filtered.sort(key=lambda t: t.get("name", ""), reverse=reverse)
        elif sort_by == "service":
            filtered.sort(key=lambda t: t.get("service", ""), reverse=reverse)

        applied_sort = {"by": sort_by, "order": sort_order or "asc"}

    filtered_count = len(filtered)

    # 5. Apply pagination
    if page is not None or limit is not None:
        # Paginate only when pagination parameters are provided
        page = page or 1
        limit = limit or 20
        start = (page - 1) * limit
        paginated = filtered[start:start + limit]
    else:
        # Return all data when no pagination parameters
        paginated = filtered

    # 6. Build unified response format (always includes pagination field)
    pagination = create_enhanced_pagination_info(page, limit, filtered_count)

    response_data = {
        "tools": paginated,
        "pagination": pagination.dict()
    }

    # Add filter and sort information (if applied)
    if applied_filters:
        response_data["filters"] = applied_filters
    if applied_sort:
        response_data["sort"] = applied_sort

    return ResponseBuilder.success(
        message=f"Retrieved {len(paginated)} of {filtered_count} tools for agent '{agent_id}'",
        data=response_data
    )

@agent_router.get("/for_agent/{agent_id}/check_services", response_model=APIResponse)
@timed_response
async def agent_check_services(agent_id: str):
    """Batch health check at agent level"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)
    health_status = await context.bridge_execute(context.check_services_async())
    
    return ResponseBuilder.success(
        message=f"Health check completed for agent '{agent_id}'",
        data=health_status
    )

@agent_router.post("/for_agent/{agent_id}/call_tool", response_model=APIResponse)
@timed_response
async def agent_call_tool(agent_id: str, request: SimpleToolExecutionRequest):
    """Tool execution at agent level"""
    validate_agent_id(agent_id)
    
    store = get_store()
    context = store.for_agent(agent_id)
    result = await context.bridge_execute(
        context.call_tool_async(request.tool_name, request.args)
    )
    # 将 MCPStore CallToolResult 标准化为可序列化的视图
    try:
        result_view = call_tool_response_helper(result).model_dump()
    except Exception as e:
        # 出现异常时返回原始结果的字符串化内容，避免序列化失败
        result_view = {
            "text": str(result),
            "is_error": True,
            "error_message": f"call_tool result serialize failed: {e}"
        }
    
    return ResponseBuilder.success(
        message=f"Tool '{request.tool_name}' executed successfully for agent '{agent_id}'",
        data=result_view
    )

@agent_router.put("/for_agent/{agent_id}/update_service/{service_name}", response_model=APIResponse)
@timed_response
async def agent_update_service(agent_id: str, service_name: str, request: Request):
    """Update service configuration at agent level"""
    validate_agent_id(agent_id)
    body = await request.json()
    
    store = get_store()
    context = store.for_agent(agent_id)
    result = await context.bridge_execute(
        context.update_service_async(service_name, body)
    )
    
    if not result:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_NOT_FOUND,
            message=f"Failed to update service '{service_name}' for agent '{agent_id}'",
            field="service_name"
        )
    
    return ResponseBuilder.success(
        message=f"Service '{service_name}' updated for agent '{agent_id}'",
        data={"service_name": service_name, "agent_id": agent_id}
    )

@agent_router.delete("/for_agent/{agent_id}/delete_service/{service_name}", response_model=APIResponse)
@timed_response
async def agent_delete_service(agent_id: str, service_name: str):
    """Delete service at agent level"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)
    result = await context.bridge_execute(
        context.delete_service_async(service_name)
    )
    
    if not result:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_NOT_FOUND,
            message=f"Failed to delete service '{service_name}' for agent '{agent_id}'",
            field="service_name"
        )
    
    return ResponseBuilder.success(
        message=f"Service '{service_name}' deleted for agent '{agent_id}'",
        data={"service_name": service_name, "agent_id": agent_id}
    )

@agent_router.post("/for_agent/{agent_id}/disconnect_service", response_model=APIResponse)
@timed_response
async def agent_disconnect_service(agent_id: str, request: Request):
    """Disconnect service at agent level (lifecycle disconnection without config modification)

    Body example:
    {
      "service_name": "localName",  # Agent local name
      "reason": "user_requested"
    }
    """
    validate_agent_id(agent_id)
    body = await request.json()
    local_name = body.get("service_name") or body.get("name")
    reason = body.get("reason", "user_requested")

    if not local_name:
        return ResponseBuilder.error(
            code=ErrorCode.VALIDATION_ERROR,
            message="Missing service_name",
            field="service_name"
        )

    store = get_store()
    context = store.for_agent(agent_id)

    try:
        ok = await context.bridge_execute(
            context.disconnect_service_async(local_name, reason=reason)
        )
        if ok:
            return ResponseBuilder.success(
                message=f"Service '{local_name}' disconnected for agent '{agent_id}'",
                data={"agent_id": agent_id, "service_name": local_name, "status": "disconnected"}
            )
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_OPERATION_FAILED,
            message=f"Failed to disconnect service '{local_name}' for agent '{agent_id}'",
            details={"agent_id": agent_id, "service_name": local_name}
        )
    except Exception as e:
        return ResponseBuilder.error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to disconnect service '{local_name}' for agent '{agent_id}': {e}",
            details={"agent_id": agent_id, "service_name": local_name}
        )

@agent_router.get("/for_agent/{agent_id}/show_mcpconfig", response_model=APIResponse)
@timed_response
async def agent_show_mcpconfig(agent_id: str):
    """Get MCP configuration at agent level"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)
    config = await context.bridge_execute(context.show_mcpconfig_async())
    
    return ResponseBuilder.success(
        message=f"MCP configuration retrieved for agent '{agent_id}'",
        data=config
    )

@agent_router.get("/for_agent/{agent_id}/show_config", response_model=APIResponse)
@timed_response
async def agent_show_config(agent_id: str):
    """Display configuration information at agent level"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)
    config_data = await context.bridge_execute(context.show_config_async())
    
    # Check for errors
    if "error" in config_data:
        return ResponseBuilder.error(
            code=ErrorCode.CONFIGURATION_ERROR,
            message=config_data["error"],
            details=config_data
        )
    
    return ResponseBuilder.success(
        message=f"Retrieved configuration for agent '{agent_id}'",
        data=config_data
    )

@agent_router.delete("/for_agent/{agent_id}/delete_config/{client_id_or_service_name}", response_model=APIResponse)
@timed_response
async def agent_delete_config(agent_id: str, client_id_or_service_name: str):
    """Delete service configuration at agent level"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)
    result = await context.bridge_execute(
        context.delete_config_async(client_id_or_service_name)
    )
    
    if result.get("success"):
        return ResponseBuilder.success(
            message=result.get("message", "Configuration deleted successfully"),
            data=result
        )
    else:
        return ResponseBuilder.error(
            code=ErrorCode.CONFIGURATION_ERROR,
            message=result.get("error", "Failed to delete configuration"),
            details=result
        )

@agent_router.put("/for_agent/{agent_id}/update_config/{client_id_or_service_name}", response_model=APIResponse)
@timed_response
async def agent_update_config(agent_id: str, client_id_or_service_name: str, new_config: dict):
    """Update service configuration at agent level"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)
    result = await context.bridge_execute(
        context.update_config_async(client_id_or_service_name, new_config)
    )
    
    if result.get("success"):
        return ResponseBuilder.success(
            message=result.get("message", "Configuration updated successfully"),
            data=result
        )
    else:
        return ResponseBuilder.error(
            code=ErrorCode.CONFIGURATION_ERROR,
            message=result.get("error", "Failed to update configuration"),
            details=result
        )

@agent_router.post("/for_agent/{agent_id}/reset_config", response_model=APIResponse)
@timed_response
async def agent_reset_config(agent_id: str):
    """Reset configuration at agent level"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)
    success = await context.bridge_execute(context.reset_config_async())
    
    if not success:
        return ResponseBuilder.error(
            code=ErrorCode.CONFIGURATION_ERROR,
            message=f"Failed to reset agent '{agent_id}' configuration",
            field="agent_id"
        )
    
    return ResponseBuilder.success(
        message=f"Agent '{agent_id}' configuration reset successfully",
        data={"agent_id": agent_id, "reset": True}
    )

@agent_router.post("/for_agent/{agent_id}/restart_service", response_model=APIResponse)
@timed_response
async def agent_restart_service(agent_id: str, request: Request):
    """Restart service at agent level"""
    body = await request.json()

    # Extract parameters
    service_name = body.get("service_name")
    if not service_name:
        return ResponseBuilder.error(
            code=ErrorCode.VALIDATION_ERROR,
            message="Missing required parameter: service_name",
            field="service_name"
        )

    store = get_store()
    context = store.for_agent(agent_id)

    # 使用 Agent 解析逻辑将本地服务名解析为全局服务名
    try:
        _, global_service_name = await context.bridge_execute(
            context._resolve_client_id_async(service_name, agent_id)
        )
    except Exception as e:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_NOT_FOUND,
            message=str(e),
            field="service_name"
        )

    global_agent_id = store.client_manager.global_agent_store_id
    app_service = store.container.service_application_service

    result = await context.bridge_execute(
        app_service.restart_service(
            service_name=global_service_name,
            agent_id=global_agent_id,
            wait_timeout=0.0,
        )
    )

    if not result:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_OPERATION_FAILED,
            message=f"Failed to restart service '{service_name}' for agent '{agent_id}'",
            field="service_name"
        )

    return ResponseBuilder.success(
        message=f"Service '{service_name}' restarted for agent '{agent_id}'",
        data={"agent_id": agent_id, "service_name": service_name, "restarted": True}
    )


# === Agent-level Service Details APIs ===

@agent_router.get("/for_agent/{agent_id}/service_info/{service_name}", response_model=APIResponse)
@timed_response
async def agent_get_service_info_detailed(agent_id: str, service_name: str):
    """Get detailed service information at agent level"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)

    # Use SDK to get service information（使用 async 版本）
    info = await context.bridge_execute(
        context.service_info_async(service_name)
    )
    if not info or not getattr(info, 'success', False):
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_NOT_FOUND,
            message=getattr(info, 'message', f"Service '{service_name}' not found for agent '{agent_id}'"),
            field="service_name"
        )

    # Simplify response structure
    service = getattr(info, 'service', None)
    service_info = {
        "name": service.name,
        "status": service.status.value if hasattr(service.status, 'value') else str(service.status),
        "type": service.transport_type.value if service.transport_type else 'unknown',
        "tools_count": getattr(service, 'tool_count', 0)
    }
    
    return ResponseBuilder.success(
        message=f"Service info retrieved for '{service_name}' in agent '{agent_id}'",
        data=service_info
    )

@agent_router.get("/for_agent/{agent_id}/service_status/{service_name}", response_model=APIResponse)
@timed_response
async def agent_get_service_status(agent_id: str, service_name: str):
    """Get service status at agent level"""
    validate_agent_id(agent_id)
    store = get_store()
    context = store.for_agent(agent_id)

    status = await context.bridge_execute(
        context.service_status_async(service_name)
    )

    # 如果状态为 unknown 且没有 client_id，视为服务不存在或已移除
    if status.get("status") == "unknown" and not status.get("client_id"):
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_NOT_FOUND,
            message=f"Service '{service_name}' not found for agent '{agent_id}'",
            field="service_name"
        )

    # 保持原有返回结构：name/status/is_active
    effective_status = status.get("status", "unknown")
    is_active = effective_status not in {"disconnected", "unknown", "error"}

    status_info = {
        "name": service_name,
        "status": effective_status,
        "is_active": is_active,
    }

    return ResponseBuilder.success(
        message=f"Service status retrieved for '{service_name}' in agent '{agent_id}'",
        data=status_info
    )
