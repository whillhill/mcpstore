"""
MCPStore API Response Models
Contains request and response models used by all API endpoints
"""

from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# === Monitoring-related response models ===

class ToolUsageStatsResponse(BaseModel):
    """Tool usage statistics response"""
    tool_name: str = Field(description="Tool name")
    service_name: str = Field(description="Service name")
    execution_count: int = Field(description="Execution count")
    last_executed: Optional[str] = Field(description="Last execution time")
    average_response_time: float = Field(description="Average response time")
    success_rate: float = Field(description="Success rate")

class ToolExecutionRecordResponse(BaseModel):
    """Tool execution record response"""
    id: str = Field(description="Record ID")
    tool_name: str = Field(description="Tool name")
    service_name: str = Field(description="Service name")
    params: Dict[str, Any] = Field(description="Execution parameters")
    result: Optional[Any] = Field(description="Execution result")
    error: Optional[str] = Field(description="Error message")
    response_time: float = Field(description="Response time (milliseconds)")
    execution_time: str = Field(description="Execution time")
    timestamp: int = Field(description="Timestamp")

class ToolRecordsSummaryResponse(BaseModel):
    """工具记录汇总响应"""
    total_executions: int = Field(description="总执行次数")
    by_tool: Dict[str, Dict[str, Any]] = Field(description="按工具统计")
    by_service: Dict[str, Dict[str, Any]] = Field(description="按服务统计")

class ToolRecordsResponse(BaseModel):
    """工具记录完整响应"""
    executions: List[ToolExecutionRecordResponse] = Field(description="执行记录列表")
    summary: ToolRecordsSummaryResponse = Field(description="汇总统计")

class AddAlertRequest(BaseModel):
    """添加告警请求"""
    type: str = Field(description="告警类型: warning, error, info")
    title: str = Field(description="告警标题")
    message: str = Field(description="告警消息")
    service_name: Optional[str] = Field(None, description="相关服务名称")

# === 健康状态相关响应模型 ===
class ServiceHealthResponse(BaseModel):
    """服务健康状态响应"""
    service_name: str = Field(description="服务名称")
    status: str = Field(description="服务状态: init, startup, ready, healthy, degraded, circuit_open, half_open, disconnected")
    response_time: float = Field(description="最近响应时间（秒）")
    last_check_time: float = Field(description="最后检查时间戳")
    consecutive_failures: int = Field(description="连续失败次数")
    consecutive_successes: int = Field(description="连续成功次数")
    reconnect_attempts: int = Field(description="重连尝试次数")
    state_entered_time: Optional[str] = Field(None, description="状态进入时间")
    next_retry_time: Optional[str] = Field(None, description="下次重试时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    details: Dict[str, Any] = Field(default_factory=dict, description="详细信息")

class HealthSummaryResponse(BaseModel):
    """健康状态汇总响应"""
    total_services: int = Field(description="总服务数量")
    init_count: int = Field(description="注册未探针数量")
    startup_count: int = Field(description="启动探针中数量")
    ready_count: int = Field(description="业务就绪数量")
    healthy_count: int = Field(description="健康服务数量")
    degraded_count: int = Field(description="降级/警告数量")
    circuit_open_count: int = Field(description="熔断/放逐数量")
    half_open_count: int = Field(description="半开试探数量")
    disconnected_count: int = Field(description="已断连/放弃数量")
    services: Dict[str, ServiceHealthResponse] = Field(description="各服务健康状态详情")

# === Agent统计相关响应模型 ===
class AgentServiceSummaryResponse(BaseModel):
    """Agent服务摘要响应"""
    service_name: str = Field(description="服务名称")
    service_type: str = Field(description="服务类型")
    status: str = Field(description="服务状态: init, startup, ready, healthy, degraded, circuit_open, half_open, disconnected")
    tool_count: int = Field(description="工具数量")
    last_used: Optional[str] = Field(None, description="最后使用时间")
    client_id: Optional[str] = Field(None, description="客户端ID")
    response_time: Optional[float] = Field(None, description="最近响应时间（秒）")
    health_details: Optional[Dict[str, Any]] = Field(None, description="健康状态详情")

class AgentStatisticsResponse(BaseModel):
    """Agent统计信息响应"""
    agent_id: str = Field(description="Agent ID")
    service_count: int = Field(description="服务数量")
    tool_count: int = Field(description="工具数量")
    healthy_services: int = Field(description="健康服务数量")
    unhealthy_services: int = Field(description="不健康服务数量")
    total_tool_executions: int = Field(description="总工具执行次数")
    last_activity: Optional[str] = Field(None, description="最后活动时间")
    services: List[AgentServiceSummaryResponse] = Field(description="服务列表")

class AgentsSummaryResponse(BaseModel):
    """所有Agent汇总信息响应"""
    total_agents: int = Field(description="总Agent数量")
    active_agents: int = Field(description="活跃Agent数量")
    total_services: int = Field(description="总服务数量")
    total_tools: int = Field(description="总工具数量")
    store_services: int = Field(description="Store级别服务数量")
    store_tools: int = Field(description="Store级别工具数量")
    agents: List[AgentStatisticsResponse] = Field(description="Agent列表")

# === 工具执行请求模型 ===
class SimpleToolExecutionRequest(BaseModel):
    """简化的工具执行请求模型（用于API）"""
    tool_name: str = Field(..., description="工具名称")
    args: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    service_name: Optional[str] = Field(None, description="服务名称（可选，会自动推断）")

# === 生命周期配置模型 ===
class ServiceLifecycleConfig(BaseModel):
    """服务生命周期配置模型（新健康模型，无兼容层）"""
    enabled: Optional[bool] = Field(default=None, description="是否启用健康检查")
    # 探针
    startup_interval: Optional[float] = Field(default=None, ge=0.1, le=60.0, description="Startup 探针间隔（秒）")
    startup_timeout: Optional[float] = Field(default=None, ge=1.0, le=1800.0, description="Startup 超时（秒）")
    startup_hard_timeout: Optional[float] = Field(default=None, ge=1.0, le=7200.0, description="Startup 硬超时（秒）")
    readiness_interval: Optional[float] = Field(default=None, ge=1.0, le=300.0, description="Readiness 探针间隔（秒）")
    readiness_success_threshold: Optional[int] = Field(default=None, ge=1, le=10, description="Readiness 连续成功阈值")
    readiness_failure_threshold: Optional[int] = Field(default=None, ge=1, le=10, description="Readiness 连续失败阈值")
    liveness_interval: Optional[float] = Field(default=None, ge=1.0, le=300.0, description="Liveness 探针间隔（秒）")
    liveness_failure_threshold: Optional[int] = Field(default=None, ge=1, le=10, description="Liveness 连续失败阈值")
    ping_timeout_http: Optional[float] = Field(default=None, ge=0.1, le=600.0, description="HTTP ping 超时（秒）")
    ping_timeout_sse: Optional[float] = Field(default=None, ge=0.1, le=600.0, description="SSE ping 超时（秒）")
    ping_timeout_stdio: Optional[float] = Field(default=None, ge=0.1, le=1200.0, description="STDIO ping 超时（秒）")
    warning_ping_timeout: Optional[float] = Field(default=None, ge=0.1, le=1200.0, description="降级/熔断/半开放宽 ping 超时（秒）")
    # 窗口判定
    window_size: Optional[int] = Field(default=None, ge=1, le=1000, description="滑动窗口样本大小")
    window_min_calls: Optional[int] = Field(default=None, ge=1, le=1000, description="窗口最小样本数")
    error_rate_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="错误率阈值")
    latency_p95_warn: Optional[float] = Field(default=None, ge=0.01, le=30.0, description="P95 警告阈值（秒）")
    latency_p99_critical: Optional[float] = Field(default=None, ge=0.01, le=60.0, description="P99 危急阈值（秒）")
    # 退避/熔断/半开
    max_reconnect_attempts: Optional[int] = Field(default=None, ge=1, le=100, description="最大重连尝试次数")
    backoff_base: Optional[float] = Field(default=None, ge=0.1, le=300.0, description="退避基数（秒）")
    backoff_max: Optional[float] = Field(default=None, ge=1.0, le=3600.0, description="退避最大间隔（秒）")
    backoff_jitter: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="退避抖动系数")
    backoff_max_duration: Optional[float] = Field(default=None, ge=1.0, le=7200.0, description="退避最大总时长（秒）")
    half_open_max_calls: Optional[int] = Field(default=None, ge=1, le=100, description="半开试探请求数上限")
    half_open_success_rate_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="半开恢复成功率阈值")
    reconnect_hard_timeout: Optional[float] = Field(default=None, ge=1.0, le=7200.0, description="重连硬超时（秒）")
    # 租约与生命周期
    lease_ttl: Optional[float] = Field(default=None, ge=1.0, le=3600.0, description="租约 TTL（秒）")
    lease_renew_interval: Optional[float] = Field(default=None, ge=0.5, le=3600.0, description="租约续约间隔（秒）")
    initialization_timeout: Optional[float] = Field(default=None, ge=1.0, le=7200.0, description="初始化硬超时（秒）")
    termination_timeout: Optional[float] = Field(default=None, ge=1.0, le=3600.0, description="终止超时（秒）")
    shutdown_timeout: Optional[float] = Field(default=None, ge=1.0, le=3600.0, description="优雅关闭超时（秒）")

# === 服务详情相关响应模型 ===

class ServiceLifecycleInfo(BaseModel):
    """服务生命周期信息"""
    consecutive_successes: int = Field(description="连续成功次数")
    consecutive_failures: int = Field(description="连续失败次数")
    last_ping_time: Optional[str] = Field(None, description="最后ping时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    reconnect_attempts: int = Field(description="重连尝试次数")
    state_entered_time: Optional[str] = Field(None, description="状态进入时间")

class ServiceToolInfo(BaseModel):
    """服务工具信息"""
    name: str = Field(description="工具名称")
    description: Optional[str] = Field(None, description="工具描述")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="输入模式")
    service_name: str = Field(description="所属服务名称")

class ServiceHealthDetail(BaseModel):
    """服务健康详情"""
    status: str = Field(description="健康状态")
    message: Optional[str] = Field(None, description="健康消息")
    timestamp: Optional[str] = Field(None, description="检查时间戳")
    uptime: Optional[str] = Field(None, description="运行时间")
    error_count: int = Field(default=0, description="错误计数")
    last_error: Optional[str] = Field(None, description="最后错误")
    response_time: Optional[float] = Field(None, description="响应时间（毫秒）")
    is_healthy: bool = Field(description="是否健康")

class ServiceDetailResponse(BaseModel):
    """服务详细信息响应"""
    name: str = Field(description="服务名称")
    status: str = Field(description="服务状态")
    transport: str = Field(description="传输类型")
    client_id: Optional[str] = Field(None, description="客户端ID")
    url: Optional[str] = Field(None, description="服务URL")
    command: Optional[str] = Field(None, description="启动命令")
    args: Optional[List[str]] = Field(None, description="命令参数")
    env: Optional[Dict[str, str]] = Field(None, description="环境变量")
    tool_count: int = Field(description="工具数量")
    is_active: bool = Field(description="是否已激活")
    config: Dict[str, Any] = Field(default_factory=dict, description="配置信息")
    lifecycle: Optional[ServiceLifecycleInfo] = Field(None, description="生命周期信息")
    tools: List[ServiceToolInfo] = Field(default_factory=list, description="工具列表")
    health: Optional[ServiceHealthDetail] = Field(None, description="健康信息")

class ServiceStatusResponse(BaseModel):
    """服务状态响应"""
    name: str = Field(description="服务名称")
    status: str = Field(description="服务状态")
    is_active: bool = Field(description="是否已激活")
    client_id: Optional[str] = Field(None, description="客户端ID")
    last_updated: Optional[str] = Field(None, description="最后更新时间")
    consecutive_successes: int = Field(default=0, description="连续成功次数")
    consecutive_failures: int = Field(default=0, description="连续失败次数")
    error_message: Optional[str] = Field(None, description="错误信息")
    reconnect_attempts: int = Field(default=0, description="重连尝试次数")

# === 数据空间相关响应模型 ===

class WorkspaceInfo(BaseModel):
    """工作空间信息"""
    name: str = Field(description="工作空间名称")
    path: str = Field(description="工作空间路径")
    mcp_config_path: str = Field(description="MCP配置文件路径")
    is_current: bool = Field(description="是否为当前工作空间")

class DataSpaceInfo(BaseModel):
    """数据空间信息"""
    is_using_data_space: bool = Field(description="是否使用数据空间")
    workspace_dir: Optional[str] = Field(None, description="工作空间目录")
    mcp_config_path: Optional[str] = Field(None, description="MCP配置文件路径")
    data_space_path: Optional[str] = Field(None, description="数据空间路径")
    workspace_config: Dict[str, Any] = Field(default_factory=dict, description="工作空间配置")

class WorkspacesListResponse(BaseModel):
    """工作空间列表响应"""
    workspaces: List[WorkspaceInfo] = Field(description="工作空间列表")
    current_workspace: Optional[str] = Field(None, description="当前工作空间路径")
    using_default: bool = Field(default=False, description="是否使用默认配置")

# === LangChain 相关响应模型 ===

class LangChainToolParameter(BaseModel):
    """LangChain工具参数信息"""
    required: List[str] = Field(default_factory=list, description="必需参数")
    optional: List[str] = Field(default_factory=list, description="可选参数")
    total_count: int = Field(default=0, description="参数总数")

class LangChainToolResponse(BaseModel):
    """LangChain工具响应"""
    name: str = Field(description="工具名称")
    description: str = Field(description="工具描述")
    args_schema: Optional[Dict[str, Any]] = Field(None, description="参数模式")
    is_structured: bool = Field(description="是否为结构化工具")
    tool_type: str = Field(description="工具类型")
    parameters: Optional[LangChainToolParameter] = Field(None, description="参数信息")
    original_info: Optional[Dict[str, Any]] = Field(None, description="原始工具信息")

class LangChainToolsListResponse(BaseModel):
    """LangChain工具列表响应"""
    tools: List[LangChainToolResponse] = Field(description="工具列表")
    total_tools: int = Field(description="工具总数")
    structured_tools: int = Field(description="结构化工具数量")

# === 批量操作请求模型 ===

class BatchServiceOperationRequest(BaseModel):
    """批量服务操作请求"""
    service_names: List[str] = Field(..., description="服务名称列表")
    operation: str = Field(..., description="操作类型: init, start, stop, restart, delete")

class BatchServiceOperationResponse(BaseModel):
    """批量服务操作响应"""
    total_count: int = Field(description="总数")
    success_count: int = Field(description="成功数量")
    failure_count: int = Field(description="失败数量")
    results: List[Dict[str, Any]] = Field(description="各服务操作结果")

# === API分页模型 ===

class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页大小")

class PaginatedResponse(BaseModel):
    """分页响应基类"""
    items: List[Any] = Field(description="数据项")
    total: int = Field(description="总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页大小")
    total_pages: int = Field(description="总页数")

# === 生命周期配置扩展 ===

class ExtendedServiceLifecycleConfig(ServiceLifecycleConfig):
    """扩展的服务生命周期配置模型"""
    # 性能监控配置（保留）
    enable_performance_metrics: Optional[bool] = Field(default=None, description="是否启用性能指标收集")
    metrics_retention_days: Optional[int] = Field(default=None, ge=1, le=365, description="指标保留天数，范围1-365")

# === 内容更新配置模型 ===
class ContentUpdateConfig(BaseModel):
    """服务内容更新配置模型"""
    # 更新间隔
    tools_update_interval: Optional[float] = Field(default=None, ge=60.0, le=3600.0, description="工具更新间隔（秒），范围60.0-3600.0")
    resources_update_interval: Optional[float] = Field(default=None, ge=60.0, le=3600.0, description="资源更新间隔（秒），范围60.0-3600.0")
    prompts_update_interval: Optional[float] = Field(default=None, ge=60.0, le=3600.0, description="提示词更新间隔（秒），范围60.0-3600.0")

    # 批量处理配置
    max_concurrent_updates: Optional[int] = Field(default=None, ge=1, le=10, description="最大并发更新数，范围1-10")
    update_timeout: Optional[float] = Field(default=None, ge=10.0, le=120.0, description="单次更新超时（秒），范围10.0-120.0")

    # 错误处理
    max_consecutive_failures: Optional[int] = Field(default=None, ge=1, le=10, description="最大连续失败次数，范围1-10")
    failure_backoff_multiplier: Optional[float] = Field(default=None, ge=1.0, le=5.0, description="失败退避倍数，范围1.0-5.0")


# === 🆕 分页/排序/过滤增强模型 ===

class EnhancedPaginationInfo(BaseModel):
    """
    增强的分页信息（统一格式）
    
    无论是否使用分页参数，始终返回此结构。
    不使用分页时，limit 会等于 total，表示返回全部数据。
    """
    page: int = Field(..., description="当前页码（从1开始）")
    limit: int = Field(..., description="每页数量")
    total: int = Field(..., description="总记录数")
    total_pages: int = Field(..., description="总页数")
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")


class ListFilterInfo(BaseModel):
    """列表过滤信息"""
    status: Optional[str] = Field(None, description="状态过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    service_type: Optional[str] = Field(None, description="服务类型")


class ListSortInfo(BaseModel):
    """列表排序信息"""
    by: str = Field(..., description="排序字段")
    order: str = Field(..., description="排序方向: asc/desc")


def create_enhanced_pagination_info(
    page: Optional[int],
    limit: Optional[int],
    filtered_count: int
) -> EnhancedPaginationInfo:
    """
    创建增强的分页信息（统一格式）
    
    Args:
        page: 用户请求的页码（None 表示不分页）
        limit: 用户请求的每页数量（None 表示不分页）
        filtered_count: 过滤后的记录数
        
    Returns:
        EnhancedPaginationInfo: 统一格式的分页信息
        
    Note:
        - 如果不传分页参数（page 和 limit 都为 None），limit 自动设置为 filtered_count
        - 这样前端可以统一处理响应格式，无需区分是否��页
    """
    # 不传分页参数时，返回全部数据
    if page is None and limit is None:
        return EnhancedPaginationInfo(
            page=1,
            limit=filtered_count,  # limit 等于总数（返回全部）
            total=filtered_count,
            total_pages=1,
            has_next=False,
            has_prev=False
        )
    
    # 使用分页参数
    page = page or 1
    limit = limit or 20
    
    # 计算总页数（向上取整）
    total_pages = (filtered_count + limit - 1) // limit if limit > 0 else 0
    
    # 计算当前页的范围
    start = (page - 1) * limit
    end = start + limit
    
    return EnhancedPaginationInfo(
        page=page,
        limit=limit,
        total=filtered_count,
        total_pages=total_pages,
        has_next=end < filtered_count,  # 是否有下一页
        has_prev=page > 1                 # 是否有上一页
    )
