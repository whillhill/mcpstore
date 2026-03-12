"""
MCPStore API - Store 级别路由
定义所有 Store 作用域的 API 端点。
"""

from typing import Optional, Dict, Any, List, Union

from fastapi import APIRouter, Request, Query, Body

from mcpstore import (
    APIResponse,
    ErrorCode,
    ResponseBuilder,
    timed_response,
)
from .api_dependencies import get_store
from .api_models import (
    SimpleToolExecutionRequest
)
from .api_service_utils import (
    ServiceOperationHelper
)

# Create Store-level router
store_router = APIRouter()

# === Store-level operations ===

# Note: sync_services endpoint removed (v0.6.0)
# Reason: File monitoring mechanism automates config sync, no manual trigger needed
# Migration: Directly modify mcp.json file, system will auto-sync within 1 second

@store_router.get("/for_store/sync_status", response_model=APIResponse)
@timed_response
async def store_sync_status():
    """Get sync status information"""
    store = get_store()
    context = store.for_store()
    
    if hasattr(store.orchestrator, 'sync_manager') and store.orchestrator.sync_manager:
        status = store.orchestrator.sync_manager.get_sync_status()
        return ResponseBuilder.success(
            message="Sync status retrieved",
            data=status
        )
    else:
        return ResponseBuilder.success(
            message="Sync manager not available",
            data={
                "is_running": False,
                "reason": "sync_manager_not_initialized"
            }
        )

@store_router.post("/for_store/add_service", response_model=APIResponse)
@timed_response
async def store_add_service(
    payload: Union[Dict[str, Any], List[Dict[str, Any]], str] = Body(
        ...,
        description="服务配置，支持单个服务配置或包含 mcpServers 的字典，也可传入配置列表"
    )
):
    """
    Store 级别添加服务（必填 payload，不再支持空参数触发全量同步）

    支持模式:
    1. 直接传入单个服务配置（url/command 等）
    2. 传入包含 mcpServers 的字典（兼容 mcp.json 结构）
    3. 传入配置列表（一次注册多个服务）
    4. 传入 JSON 字符串配置（内部会解析）
    """
    store = get_store()

    # 校验必填参数，拒绝空载
    if payload is None:
        return ResponseBuilder.error(
            code=ErrorCode.MISSING_PARAMETER,
            message="缺少必填参数 payload（服务配置）",
            details={"expected": "服务配置对象或 mcpServers 字典"}
        )
    if isinstance(payload, (dict, list)) and not payload:
        return ResponseBuilder.error(
            code=ErrorCode.MISSING_PARAMETER,
            message="服务配置不能为空",
            details={"expected": "至少包含一个服务配置"}
        )

    # 添加服务
    context = store.for_store()
    try:
        await context.bridge_execute(context.add_service_async(payload))
    except Exception as e:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_INITIALIZATION_FAILED,
            message="服务注册失败",
            details={"error": str(e)}
        )

    # 提取服务名用于响应
    service_names: List[str] = []
    if isinstance(payload, dict):
        # 检查 name 字段
        if "name" in payload:
            service_names = [str(payload.get("name"))]
        # 检查 mcpServers
        else:
            mcp_servers = payload.get("mcpServers") if isinstance(payload, dict) else None
            if isinstance(mcp_servers, dict):
                service_names = list(mcp_servers.keys())
    elif isinstance(payload, list):
        service_names = [
            str(item.get("name"))
            for item in payload
            if isinstance(item, dict) and item.get("name")
        ]
    else:
        service_names = ["(字符串配置)"]

    display_name = service_names or ["unknown"]
    
    # 返回成功，附带服务基本信息
    return ResponseBuilder.success(
        message="服务添加请求已提交",
        data={
            "service_names": display_name,
            "status": "startup"
        }
    )

@store_router.get("/for_store/list_services", response_model=APIResponse)
@timed_response
async def store_list_services(
    # 分页参数（可选）
    page: Optional[int] = Query(None, ge=1, description="页码（从1开始），不传则返回全部"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="每页数量（1-1000），不传则返回全部"),

    # 过滤参数（可选）
    status: Optional[str] = Query(None, description="按状态过滤：active/ready/error/initializing"),
    search: Optional[str] = Query(None, description="搜索服务名称（模糊匹配）"),
    service_type: Optional[str] = Query(None, description="按类型过滤：sse/stdio"),

    # 排序参数（可选）
    sort_by: Optional[str] = Query(None, description="排序字段：name/status/tools_count"),
    sort_order: Optional[str] = Query(None, description="排序方向：asc/desc，默认 asc")
):
    """
    获取 Store 级别服务列表（增强版 - 统一响应格式）

    响应格式说明：
    - 始终返回包含 pagination 字段的统一格式
    - 不传分页参数时，limit 自动等于 total（返回全部数据）
    - 前端只需一套解析逻辑

    示例：

    1. 不传参数（返回全部）：
       GET /for_store/list_services
       → 返回全部服务，pagination.limit = pagination.total

    2. 使用分页：
       GET /for_store/list_services?page=1&limit=20
       → 返回第 1 页，每页 20 条

    3. 搜索：
       GET /for_store/list_services?search=weather
       → 返回名称包含 "weather" 的所有服务

    4. 过滤 + 分页：
       GET /for_store/list_services?status=error&page=1&limit=10
       → 返回错误状态的服务，第 1 页，每页 10 条

    5. 排序：
       GET /for_store/list_services?sort_by=status&sort_order=desc
       → 按状态降序排列，返回全部
    """
    from .api_models import (
        ListFilterInfo,
        ListSortInfo,
        create_enhanced_pagination_info
    )

    store = get_store()
    context = store.for_store()

    # 1. 获取所有服务（使用 async 版本）
    all_services = await context.bridge_execute(context.list_services_async())
    original_count = len(all_services)

    # 2. 应用过滤
    filtered_services = all_services

    if status:
        filtered_services = [
            s for s in filtered_services
            if s.get("status", "").lower() == status.lower()
        ]

    if search:
        search_lower = search.lower()
        filtered_services = [
            s for s in filtered_services
            if search_lower in s.get("name", "").lower()
        ]

    if service_type:
        filtered_services = [
            s for s in filtered_services
            if s.get("type", "") == service_type
        ]

    filtered_count = len(filtered_services)

    # 3. 应用排序
    if sort_by:
        reverse = (sort_order == "desc") if sort_order else False

        if sort_by == "name":
            filtered_services.sort(key=lambda s: s.get("name", ""), reverse=reverse)
        elif sort_by == "status":
            filtered_services.sort(key=lambda s: s.get("status", ""), reverse=reverse)
        elif sort_by == "tools_count":
            filtered_services.sort(key=lambda s: s.get("tools_count", 0) or 0, reverse=reverse)

    # 4. 应用分页（如果有）
    if page is not None or limit is not None:
        page = page or 1
        limit = limit or 20

        start = (page - 1) * limit
        end = start + limit
        paginated_services = filtered_services[start:end]
    else:
        # 不分页，返回全部
        paginated_services = filtered_services

    # 5. 构造服务数据
    def build_service_data(service) -> Dict[str, Any]:
        """构造单个服务的数据"""
        # service 已经是字典（从 StoreProxy.list_services 返回）
        # 如果是对象，转换为字典访问
        if isinstance(service, dict):
            # 直接使用字典键访问
            service_data = {
                "name": service.get("name", ""),
                "url": service.get("url", ""),
                "command": service.get("command", ""),
                "args": service.get("args", []),
                "env": service.get("env", {}),
                "working_dir": service.get("working_dir", ""),
                "package_name": service.get("package_name", ""),
                "keep_alive": service.get("keep_alive", False),
                "type": service.get("type", "unknown"),
                "status": service.get("status", "unknown"),
                "tools_count": service.get("tools_count", 0) or service.get("tool_count", 0) or 0,
                "last_check": None,
                "client_id": service.get("client_id", ""),
            }

            # 处理 state_metadata（如果存在）
            state_metadata = service.get("state_metadata")
            if state_metadata and isinstance(state_metadata, dict):
                last_ping_time = state_metadata.get("last_ping_time")
                if last_ping_time:
                    service_data["last_check"] = last_ping_time if isinstance(last_ping_time, str) else None
        else:
            # 对象访问方式（向后兼容）
            service_data = {
                "name": service.name,
                "url": service.url or "",
                "command": service.command or "",
                "args": service.args or [],
                "env": service.env or {},
                "working_dir": service.working_dir or "",
                "package_name": service.package_name or "",
                "keep_alive": service.keep_alive,
                "type": service.transport_type.value if service.transport_type else "unknown",
                "status": service.status.value if service.status else "unknown",
                "tools_count": service.tool_count or 0,
                "last_check": None,
                "client_id": service.client_id or "",
            }

            if service.state_metadata:
                service_data["last_check"] = (
                    service.state_metadata.last_ping_time.isoformat()
                    if service.state_metadata.last_ping_time else None
                )

        return service_data

    services_data = [build_service_data(s) for s in paginated_services]

    # 6. 创建统一的分页信息
    pagination = create_enhanced_pagination_info(
        page=page,
        limit=limit,
        filtered_count=filtered_count
    )

    # 7. 构造响应数据（统一格式）
    response_data = {
        "services": services_data,
        "pagination": pagination.model_dump()
    }

    # 添加过滤信息（如果有）
    if any([status, search, service_type]):
        response_data["filters"] = ListFilterInfo(
            status=status,
            search=search,
            service_type=service_type
        ).model_dump(exclude_none=True)

    # 添加排序信息（如果有）
    if sort_by:
        response_data["sort"] = ListSortInfo(
            by=sort_by,
            order=sort_order or "asc"
        ).model_dump()

    # 8. 返回统一格式的响应
    message_parts = [f"Retrieved {len(services_data)} services"]

    if filtered_count < original_count:
        message_parts.append(f"(filtered from {original_count})")

    if page is not None:
        message_parts.append(f"(page {pagination.page} of {pagination.total_pages})")

    return ResponseBuilder.success(
        message=" ".join(message_parts),
        data=response_data
    )

@store_router.post("/for_store/reset_service", response_model=APIResponse)
@timed_response
async def store_reset_service(request: Request):
    """Store 级别重置服务状态
    
    重置已存在服务的状态到 STARTUP，清除所有错误计数和历史记录
    """
    body = await request.json()

    store = get_store()
    context = store.for_store()

    # 提取参数
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

    agent_id = store.client_manager.global_agent_store_id
    registry = store.registry

    # 尝试解析最终的 service_name（Store 级别只处理全局服务名/确定性 client_id）
    resolved_service_name = None

    # 优先显式 service_name
    if service_name:
        resolved_service_name = service_name
    else:
        raw = identifier or client_id
        if raw:
            try:
                from mcpstore import ClientIDGenerator

                if ClientIDGenerator.is_deterministic_format(raw):
                    parsed = ClientIDGenerator.parse_client_id(raw)
                    if parsed.get("type") == "store":
                        resolved_service_name = parsed.get("service_name")
                    else:
                        return ResponseBuilder.error(
                            code=ErrorCode.VALIDATION_ERROR,
                            message="Client ID type is not supported for store reset",
                            field="client_id"
                        )
            except Exception:
                # 解析失败时退化为直接视为服务名（与原实现中将 identifier 视为名称的行为对齐）
                resolved_service_name = raw

    if not resolved_service_name:
        resolved_service_name = used_identifier

    # 规范服务名到 Store 视角的全局名（兼容本地名/agent:service 格式）
    try:
        from mcpstore import PerspectiveResolver

        resolver = PerspectiveResolver()
        name_res = resolver.normalize_service_name(
            agent_id,
            resolved_service_name,
            target="global",
            strict=False,
        )
        normalized_service_name = name_res.global_name
    except Exception as e:
        normalized_service_name = resolved_service_name
        logger.error(f"[STORE.RESET_SERVICE] PerspectiveResolver fallback: {e}")

    # 校验服务是否存在（使用异步 API）
    service_exists = await context.bridge_execute(
        registry.has_service_async(agent_id, normalized_service_name)
    )
    if not service_exists:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_NOT_FOUND,
            message=f"Service '{resolved_service_name}' not found",
            field="service_name"
        )

    app_service = store.container.service_application_service
    ok = await context.bridge_execute(
        app_service.reset_service(
            agent_id=agent_id,
            service_name=normalized_service_name,
            wait_timeout=0.0,
        )
    )

    if not ok:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_OPERATION_FAILED,
            message=f"Failed to reset service '{resolved_service_name}'",
            field="service_name"
        )

    return ResponseBuilder.success(
        message=f"Service '{resolved_service_name}' reset successfully",
        data={"service_name": resolved_service_name, "status": "startup"}
    )

@store_router.get("/for_store/list_tools", response_model=APIResponse)
@timed_response
async def store_list_tools(
    # 分页参数（可选）
    page: Optional[int] = Query(None, ge=1, description="页码（从1开始），不传则返回全部"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="每页数量（1-1000），不传则返回全部"),

    # 过滤参数（可选）
    search: Optional[str] = Query(None, description="搜索工具名称或描述（模糊匹配）"),
    service_name: Optional[str] = Query(None, description="按服务名称过滤"),

    # 排序参数（可选）
    sort_by: Optional[str] = Query(None, description="排序字段：name/service"),
    sort_order: Optional[str] = Query(None, description="排序方向：asc/desc，默认 asc")
):
    """
    获取 Store 级别工具列表（增强版 - 统一响应格式）

    响应格式说明：
    - 始终返回包含 pagination 字段的统一格式
    - 不传分页参数时，limit 自动等于 total（返回全部数据）
    - 前端只需一套解析逻辑

    示例：

    1. 不传参数（返回全部）：
       GET /for_store/list_tools
       → 返回全部工具，pagination.limit = pagination.total

    2. 使用分页：
       GET /for_store/list_tools?page=1&limit=20
       → 返回第 1 页，每页 20 条

    3. 搜索：
       GET /for_store/list_tools?search=weather
       → 返回名称或描述包含 "weather" 的所有工具

    4. 按服务过滤：
       GET /for_store/list_tools?service_name=mcpstore-wiki
       → 返回指定服务的所有工具

    5. 排序：
       GET /for_store/list_tools?sort_by=name&sort_order=asc
       → 按名称升序排列，返回全部
    """
    from .api_models import (
        ListSortInfo,
        create_enhanced_pagination_info
    )

    store = get_store()
    context = store.for_store()

    # 1. 获取所有工具（使用 async 版本）
    all_tools = await context.bridge_execute(context.list_tools_async())
    original_count = len(all_tools)

    # 2. 应用过滤
    filtered_tools = all_tools

    if search:
        search_lower = search.lower()
        filtered_tools = [
            t for t in filtered_tools
            if search_lower in (t.get("name", "") if isinstance(t, dict) else t.name).lower() or
               search_lower in (t.get("description", "") if isinstance(t, dict) else (t.description or "")).lower()
        ]

    if service_name:
        filtered_tools = [
            t for t in filtered_tools
            if (t.get('service_name', 'unknown') if isinstance(t, dict) else getattr(t, 'service_name', 'unknown')) == service_name
        ]

    filtered_count = len(filtered_tools)

    # 3. 应用排序
    if sort_by:
        reverse = (sort_order == "desc") if sort_order else False

        if sort_by == "name":
            filtered_tools.sort(key=lambda t: t.get("name", "") if isinstance(t, dict) else t.name, reverse=reverse)
        elif sort_by == "service":
            filtered_tools.sort(
                key=lambda t: t.get('service_name', 'unknown') if isinstance(t, dict) else getattr(t, 'service_name', 'unknown'),
                reverse=reverse
            )

    # 4. 应用分页（如果有）
    if page is not None or limit is not None:
        page = page or 1
        limit = limit or 20

        start = (page - 1) * limit
        end = start + limit
        paginated_tools = filtered_tools[start:end]
    else:
        # 不分页，返回全部
        paginated_tools = filtered_tools

    # 5. 构造工具数据
    def build_tool_data(tool) -> Dict[str, Any]:
        """构造单个工具的数据（兼容字典和对象）"""
        if isinstance(tool, dict):
            return {
                "name": tool.get("name", ""),
                "service": tool.get('service_name', 'unknown'),
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema", {}) or tool.get("input_schema", {})
            }
        else:
            return {
                "name": tool.name,
                "service": getattr(tool, 'service_name', 'unknown'),
                "description": tool.description or "",
                "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
            }

    tools_data = [build_tool_data(t) for t in paginated_tools]

    # 6. 创建统一的分页信息
    pagination = create_enhanced_pagination_info(
        page=page,
        limit=limit,
        filtered_count=filtered_count
    )

    # 7. 构造响应数据（统一格式）
    response_data = {
        "tools": tools_data,
        "pagination": pagination.model_dump()
    }

    # 添加过滤信息（如果有）
    if any([search, service_name]):
        response_data["filters"] = {
            "search": search,
            "service_name": service_name
        }
        # 移除 None 值
        response_data["filters"] = {k: v for k, v in response_data["filters"].items() if v is not None}

    # 添加排序信息（如果有）
    if sort_by:
        response_data["sort"] = ListSortInfo(
            by=sort_by,
            order=sort_order or "asc"
        ).model_dump()

    # 8. 返回统一格式的响应
    message_parts = [f"Retrieved {len(tools_data)} tools"]

    if filtered_count < original_count:
        message_parts.append(f"(filtered from {original_count})")

    if page is not None:
        message_parts.append(f"(page {pagination.page} of {pagination.total_pages})")

    return ResponseBuilder.success(
        message=" ".join(message_parts),
        data=response_data
    )

@store_router.get("/for_store/check_services", response_model=APIResponse)
@timed_response
async def store_check_services():
    """Store 级别批量健康检查"""
    store = get_store()
    context = store.for_store()
    health_status = await context.bridge_execute(context.check_services_async())
    
    return ResponseBuilder.success(
        message=f"Health check completed for {len(health_status.get('services', []))} services",
        data=health_status
    )

@store_router.get("/for_store/list_agents", response_model=APIResponse)
@timed_response
async def store_list_agents():
    """Store 级列出所有 Agents 概要信息（增强版，无分页）

    返回统一结构，包含 agents 明细与汇总 summary。
    
    [架构说明] 使用异步方法 list_agents_async() 避免在 FastAPI 事件循环中触发 AOB 冲突
    """
    store = get_store()
    # 使用异步方法，避免在 FastAPI 事件循环中调用同步方法触发 AOB 冲突
    context = store.for_store()
    agents = await context.bridge_execute(context.list_agents_async())

    total_agents = len(agents)
    total_services = sum(int(a.get("service_count", 0)) for a in agents)
    total_tools = sum(int(a.get("tool_count", 0)) for a in agents)
    healthy_agents = sum(1 for a in agents if int(a.get("healthy_services", 0)) > 0)
    unhealthy_agents = total_agents - healthy_agents

    response_data = {
        "agents": agents,
        "summary": {
            "total_agents": total_agents,
            "total_services": total_services,
            "total_tools": total_tools,
            "healthy_agents": healthy_agents,
            "unhealthy_agents": unhealthy_agents
        }
    }

    return ResponseBuilder.success(
        message=f"Retrieved {total_agents} agents",
        data=response_data
    )

@store_router.post("/for_store/call_tool", response_model=APIResponse)
@timed_response
async def store_call_tool(request: SimpleToolExecutionRequest):
    """Store 级别工具执行"""
    store = get_store()
    context = store.for_store()
    result = await context.bridge_execute(
        context.call_tool_async(request.tool_name, request.args)
    )

    # 规范化 CallToolResult 或其它返回值为可序列化结构
    def _normalize_result(res):
        try:
            # MCPStore CallToolResult: 有 content/is_error 字段
            if hasattr(res, 'content'):
                items = []
                for c in getattr(res, 'content', []) or []:
                    try:
                        if isinstance(c, dict):
                            items.append(c)
                        elif hasattr(c, 'type') and hasattr(c, 'text'):
                            items.append({"type": getattr(c, 'type', 'text'), "text": getattr(c, 'text', '')})
                        elif hasattr(c, 'type') and hasattr(c, 'uri'):
                            items.append({"type": getattr(c, 'type', 'uri'), "uri": getattr(c, 'uri', '')})
                        else:
                            items.append(str(c))
                    except Exception:
                        items.append(str(c))
                return {"content": items, "is_error": bool(getattr(res, 'is_error', False))}
            # 已是 Dict/List
            if isinstance(res, (dict, list)):
                return res
            # 其它类型转字符串
            return {"result": str(res)}
        except Exception:
            return {"result": str(res)}

    normalized = _normalize_result(result)

    return ResponseBuilder.success(
        message=f"Tool '{request.tool_name}' executed successfully",
        data=normalized
    )

# Deleted POST /for_store/get_service_info (v0.6.0)
# Please use GET /for_store/service_info/{service_name} instead (RESTful standard)

@store_router.put("/for_store/update_service/{service_name}", response_model=APIResponse)
@timed_response
async def store_update_service(service_name: str, request: Request):
    """Store 级别更新服务配置"""
    body = await request.json()
    
    store = get_store()
    context = store.for_store()
    result = await context.bridge_execute(
        context.update_service_async(service_name, body)
    )
    
    if not result:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_NOT_FOUND,
            message=f"Failed to update service '{service_name}'",
            field="service_name"
        )
    
    return ResponseBuilder.success(
        message=f"Service '{service_name}' updated successfully",
        data={"service_name": service_name, "updated_fields": list(body.keys())}
    )

@store_router.delete("/for_store/delete_service/{service_name}", response_model=APIResponse)
@timed_response
async def store_delete_service(service_name: str):
    """Store 级别删除服务"""
    store = get_store()
    context = store.for_store()
    result = await context.bridge_execute(
        context.delete_service_async(service_name)
    )
    
    if not result:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_NOT_FOUND,
            message=f"Failed to delete service '{service_name}'",
            field="service_name",
            details={"service_name": service_name}
        )
    
    return ResponseBuilder.success(
        message=f"Service '{service_name}' deleted successfully",
        data={
            "service_name": service_name,
            "deleted_at": ResponseBuilder._get_timestamp()
        }
    )

@store_router.post("/for_store/disconnect_service", response_model=APIResponse)
@timed_response
async def store_disconnect_service(request: Request):
    """Store 级别断开服务（生命周期断链，不修改配置）

    Body 示例：
    {
      "service_name": "remote-demo",
      "reason": "user_requested"
    }
    """
    body = await request.json()
    service_name = body.get("service_name") or body.get("name")
    reason = body.get("reason", "user_requested")

    if not service_name:
        return ResponseBuilder.error(
            code=ErrorCode.VALIDATION_ERROR,
            message="Missing service_name"
        )

    store = get_store()
    context = store.for_store()

    try:
        ok = await context.bridge_execute(
            context.disconnect_service_async(service_name, reason=reason)
        )
        if ok:
            return ResponseBuilder.success(
                message=f"Service '{service_name}' disconnected",
                data={"service_name": service_name, "status": "disconnected"}
            )
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_OPERATION_FAILED,
            message=f"Failed to disconnect service '{service_name}'",
            details={"service_name": service_name}
        )
    except Exception as e:
        return ResponseBuilder.error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to disconnect service '{service_name}': {e}",
            details={"service_name": service_name}
        )

@store_router.get("/for_store/show_config", response_model=APIResponse)
@timed_response
async def store_show_config():
    """获取运行时配置和服务映射关系
    
    返回格式与 mcp.json 一致：{"mcpServers": {...}}
    服务名称使用全局名称（Store 添加的服务使用原始名称，Agent 添加的服务使用 name_byagent_agentId 格式）
    """
    store = get_store()
    context = store.for_store()
    config_data = await context.bridge_execute(context.show_config_async())
    
    # 检查是否有错误
    if "error" in config_data:
        return ResponseBuilder.error(
            code=ErrorCode.CONFIGURATION_ERROR,
            message=config_data["error"],
            details=config_data
        )
    
    return ResponseBuilder.success(
        message="Retrieved service configuration",
        data=config_data
    )

@store_router.delete("/for_store/delete_config/{client_id_or_service_name}", response_model=APIResponse)
@timed_response
async def store_delete_config(client_id_or_service_name: str):
    """Store 级别删除服务配置"""
    store = get_store()
    context = store.for_store()
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

@store_router.put("/for_store/update_config/{client_id_or_service_name}", response_model=APIResponse)
@timed_response
async def store_update_config(client_id_or_service_name: str, new_config: dict):
    """Store 级别更新服务配置"""
    store = get_store()
    context = store.for_store()
    
    # 使用带超时的配置更新方法
    success = await ServiceOperationHelper.update_config_with_timeout(
        context, 
        new_config,
        timeout=30.0
    )
    
    if not success:
        return ResponseBuilder.error(
            code=ErrorCode.CONFIGURATION_ERROR,
            message=f"Failed to update configuration for {client_id_or_service_name}",
            field="client_id_or_service_name"
        )
    
    return ResponseBuilder.success(
        message=f"Configuration updated for {client_id_or_service_name}",
        data={"identifier": client_id_or_service_name, "updated": True}
    )

@store_router.post("/for_store/reset_config", response_model=APIResponse)
@timed_response
async def store_reset_config():
    """重置配置（缓存+文件全量重置）
    
    清空所有 pykv 缓存数据和 mcp.json 文件。
    相当于批量执行 delete_service 操作。
    
    清理内容：
    - pykv 实体层：services, tools
    - pykv 关系层：agent_services, service_tools
    - pykv 状态层：service_status, service_metadata
    - mcp.json 文件
    
    [警告] 此操作不可逆，请谨慎使用
    """
    store = get_store()
    context = store.for_store()
    success = await context.bridge_execute(context.reset_config_async())
    
    if not success:
        return ResponseBuilder.error(
            code=ErrorCode.CONFIGURATION_ERROR,
            message="Failed to reset configuration"
        )
    
    return ResponseBuilder.success(
        message="All configuration reset successfully",
        data={"reset": True}
    )

# Removed shard-file reset APIs (client_services.json / agent_clients.json) in single-source mode

@store_router.get("/for_store/setup_config", response_model=APIResponse)
@timed_response
async def store_setup_config():
    """获取启动时的配置快照（在 MCPStore.setup_store 阶段记录）"""
    store = get_store()
    context = store.for_store()
    setup_snapshot = context.setup_config()
    
    return ResponseBuilder.success(
        message="Setup configuration snapshot retrieved",
        data=setup_snapshot
    )

@store_router.get("/for_store/show_mcpjson", response_model=APIResponse)
@timed_response
async def store_show_mcpjson():
    """获取 mcp.json 配置文件的原始内容"""
    store = get_store()
    mcpjson = store.show_mcpjson()
    
    return ResponseBuilder.success(
        message="MCP JSON content retrieved",
        data=mcpjson
    )

# === 服务详情相关 API ===

@store_router.get("/for_store/service_info/{service_name}", response_model=APIResponse)
@timed_response
async def store_get_service_info_detailed(service_name: str):
    """获取服务详细信息"""
    store = get_store()
    context = store.for_store()
    info = await context.bridge_execute(
        context.service_info_async(service_name)
    )

    # info 是字典，不是对象
    if not info or not info.get("service"):
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_NOT_FOUND,
            message=f"Service '{service_name}' not found",
            field="service_name"
        )

    service = info.get("service")
    service_info = {
        "name": service.get("name", ""),
        "status": service.get("status", "unknown"),
        "type": service.get("transport_type", "unknown"),
        "client_id": service.get("client_id", ""),
        "url": service.get("url", ""),
        "tools_count": service.get("tool_count", 0),
    }

    # 如果 status/transport 是枚举，转换为字符串
    if hasattr(service_info["status"], "value"):
        service_info["status"] = service_info["status"].value
    if hasattr(service_info["type"], "value"):
        service_info["type"] = service_info["type"].value

    return ResponseBuilder.success(
        message=f"Service info retrieved for '{service_name}'",
        data=service_info
    )

@store_router.get("/for_store/service_status/{service_name}", response_model=APIResponse)
@timed_response
async def store_get_service_status(service_name: str):
    """获取服务状态（轻量级，纯缓存读取）"""
    store = get_store()
    context = store.for_store()
    agent_id = store.client_manager.global_agent_store_id

    # 统一从 pykv 完整信息获取，避免“工具存在但实体缺失”导致的误报
    complete_info = await context.bridge_execute(
        store.registry.get_complete_service_info_async(agent_id, service_name)
    )
    if not complete_info:
        return ResponseBuilder.error(
            code=ErrorCode.SERVICE_NOT_FOUND,
            message=f"Service '{service_name}' not found",
            field="service_name"
        )

    # 使用 SDK 别名获取状态
    status = await context.bridge_execute(
        context.service_status_async(service_name)
    )

    status_info = {
        "name": service_name,
        "status": status.get("status", "unknown"),
        "client_id": status.get("client_id", "") or "",
    }

    return ResponseBuilder.success(
        message=f"Service status retrieved for '{service_name}'",
        data=status_info
    )
