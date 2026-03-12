"""
MCPOrchestrator Tool Execution Module
Tool execution module - contains tool execution and processing
"""

import logging
from typing import Dict, Any, Optional

from mcpstore.core.exceptions import ToolNotFoundException
from mcpstore.mcp import Client

logger = logging.getLogger(__name__)


# Correct session implementation based on langchain_mcp_adapters source code analysis
# Use built-in reentrant context manager features of MCP Client

class ToolExecutionMixin:
    """Tool execution mixin class"""

    async def ensure_persistent_client(self, session, service_name: str):
        """Public API: ensure a persistent MCP client is created and cached.

        This is a non-breaking wrapper exposing the previously private
        `_create_persistent_client` method, allowing callers (e.g., context/session)
        to depend on a stable public API.
        """
        return await self._create_persistent_client(session, service_name)

    async def execute_tool_mcpstore(
        self,
        service_name: str,
        tool_name: str,
        arguments: Dict[str, Any] = None,
        agent_id: Optional[str] = None,
        timeout: Optional[float] = None,
        progress_handler = None,
        raise_on_error: bool = True,
        session_id: Optional[str] = None
    ) -> Any:
        """
        Execute tool (MCP canonical standard)
        Strictly execute tool calls according to MCP protocol expectations

        Args:
            service_name: Service name
            tool_name: Tool name (MCP canonical/original name)
            arguments: Tool parameters
            agent_id: Agent ID (optional)
            timeout: Timeout in seconds
            progress_handler: Progress handler
            raise_on_error: Whether to raise exception on error
            session_id: Session ID (optional, for session-aware execution)

        Returns:
            MCP CallToolResult or extracted data
        """
        from mcpstore.core.registry.tool_resolver import MCPStoreToolExecutor

        arguments = arguments or {}
        executor = MCPStoreToolExecutor(default_timeout=timeout or 30.0)

        # [SESSION MODE] Use cached MCP Client
        if session_id:
            logger.info(f"[SESSION_EXECUTION] Using session mode for tool '{tool_name}' in service '{service_name}'")
            return await self._execute_tool_with_session(
                session_id, service_name, tool_name, arguments, agent_id, 
                executor, timeout, progress_handler, raise_on_error
            )

        # [TRADITIONAL MODE] Maintain original logic, ensure backward compatibility
        logger.debug(f"[TRADITIONAL_EXECUTION] Using traditional mode for tool '{tool_name}' in service '{service_name}'")

        try:
            # 确定 effective_agent_id
            effective_agent_id = agent_id if agent_id else self.client_manager.global_agent_store_id
            
            # [pykv 唯一真相源] 从关系层获取 Agent 的服务列表
            relation_manager = self.registry._relation_manager
            agent_services = await relation_manager.get_agent_services(effective_agent_id)
            
            if not agent_services:
                raise Exception(f"No services found in pykv for agent {effective_agent_id}")
            
            logger.debug(f"[TOOL_EXECUTION] pykv relationship layer service count: {len(agent_services)}")
            
            # 从关系层提取 client_ids
            client_ids = list(set(
                svc.get("client_id") for svc in agent_services if svc.get("client_id")
            ))
            
            if not client_ids:
                raise Exception(f"No client_ids found in pykv relations for agent {effective_agent_id}")
            
            logger.debug(f"[TOOL_EXECUTION] pykv relationship layer client_ids: {client_ids}")

            # 检查服务是否存在于关系层
            service_exists = any(
                svc.get("service_global_name") == service_name or 
                svc.get("service_original_name") == service_name
                for svc in agent_services
            )
            
            if not service_exists:
                raise Exception(f"Service {service_name} not found in pykv relations for agent {effective_agent_id}")
            
            # [pykv 唯一真相源] 从实体层获取服务配置
            service_manager = self.registry._cache_service_manager
            service_entity = await service_manager.get_service(service_name)
            
            if not service_entity:
                raise Exception(f"Service entity not found in pykv: {service_name}")
            
            service_config = service_entity.config
            if not service_config:
                raise Exception(f"Service configuration is empty in pykv: {service_name}")
            
            logger.debug(f"[TOOL_EXECUTION] Getting service config from pykv entity layer: {service_name}")

            # 标准化配置并创建 MCP 客户端
            normalized_config = self._normalize_service_config(service_config)
            client = Client({"mcpServers": {service_name: normalized_config}})

            async with client:
                # 验证工具存在
                tools = await client.list_tools()

                # 调试日志：验证工具存在
                logger.debug(f"[MCP_DEBUG] lookup tool='{tool_name}'")
                logger.debug(f"[MCP_DEBUG] service='{service_name}' tools:")
                for i, tool in enumerate(tools):
                    logger.debug(f"   {i+1}. {tool.name}")

                if not any(t.name == tool_name for t in tools):
                    available = [t.name for t in tools]
                    suggestions = available[:3]
                    logger.info(
                        "[MCP_DEBUG] tool not found: tool='%s' service='%s' available=%s suggestions=%s",
                        tool_name,
                        service_name,
                        available,
                        suggestions,
                    )
                    raise ToolNotFoundException(
                        tool_name,
                        service_name,
                        details={"suggestions": suggestions},
                    )

                # 使用 MCP 规范执行器执行工具（标准 canonical 名称）
                result = await executor.execute_tool(
                    client=client,
                    tool_name=tool_name,
                    arguments=arguments,
                    timeout=timeout,
                    progress_handler=progress_handler,
                    raise_on_error=raise_on_error
                )

                # 返回 MCP 客户端的 CallToolResult（与官方保持一致）
                logger.info(f"[MCP] call ok tool='{tool_name}' service='{service_name}'")
                return result

        except Exception as e:
            # 以 info 级别标记外部 MCP 服务异常，避免误判为 mcpstore 内部崩溃
            logger.info(
                "[MCP_SERVICE_ERROR] tool='%s' service='%s' reason=%s",
                tool_name,
                service_name,
                e,
            )
            # 保留详细堆栈在 debug 级别，便于排查
            logger.debug(
                "[MCP_SERVICE_ERROR] full traceback for tool='%s' service='%s'",
                tool_name,
                service_name,
                exc_info=True,
            )
            raise Exception(f"Tool execution failed: {str(e)}")

    async def _execute_tool_with_session(
        self,
        session_id: str,
        service_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        agent_id: Optional[str],
        executor,
        timeout: Optional[float],
        progress_handler,
        raise_on_error: bool
    ) -> Any:
        """
        会话感知的工具执行模式
        
        使用缓存的 MCP Client 执行工具，实现连接复用和状态保持。
        这是解决浏览器会话持久化问题的核心逻辑。
        
        Args:
            session_id: 会话标识
            service_name: 服务名称
            tool_name: 工具名称
            arguments: 工具参数
            agent_id: Agent ID
            executor: MCP 执行器
            timeout: 超时时间
            progress_handler: 进度处理器
            raise_on_error: 是否在错误时抛出异常
            
        Returns:
            工具执行结果
        """
        try:
            # Use session_id to get/create named session (priority), otherwise fallback to default session
            effective_agent_id = agent_id or self.client_manager.global_agent_store_id
            session = None
            try:
                if hasattr(self.session_manager, 'get_named_session') and session_id:
                    session = self.session_manager.get_named_session(effective_agent_id, session_id)
                    if not session:
                        logger.info(f"[SESSION_EXECUTION] Named session '{session_id}' not found for agent {effective_agent_id}, creating new named session")
                        if hasattr(self.session_manager, 'create_named_session'):
                            session = self.session_manager.create_named_session(effective_agent_id, session_id)
                if not session:
                    # 回退：使用默认会话
                    session = self.session_manager.get_session(effective_agent_id)
                    if not session:
                        logger.info(f"[SESSION_EXECUTION] Default session not found for agent {effective_agent_id}, creating new session")
                        session = self.session_manager.create_session(effective_agent_id)
            except Exception as e:
                logger.info(
                    "[MCP_SERVICE_ERROR] session setup failed tool='%s' service='%s' reason=%s",
                    tool_name,
                    service_name,
                    e,
                )
                logger.debug(
                    "[MCP_SERVICE_ERROR] session setup traceback tool='%s' service='%s'",
                    tool_name,
                    service_name,
                    exc_info=True,
                )
                # 最后兜底创建一个默认会话
                session = self.session_manager.create_session(effective_agent_id)

            # Get or create persistent MCP Client (refer to langchain_mcp_adapters design)
            client = session.services.get(service_name)
            if client is None:
                logger.info(f"[SESSION_EXECUTION] Service '{service_name}' not bound or client is None, creating persistent client")
                client = await self._create_persistent_client(session, service_name)
            else:
                # 如果已有缓存客户端，但未连接，确保连接可用
                try:
                    if hasattr(client, 'is_connected') and not client.is_connected():
                        logger.debug(f"[SESSION_EXECUTION] Cached client for '{service_name}' not connected, calling _connect()")
                        await client._connect()
                except Exception as e:
                    logger.warning(f"[SESSION_EXECUTION] Cached client health check failed for '{service_name}', recreating client: {e}")
                    client = await self._create_persistent_client(session, service_name)

                logger.debug(f"[SESSION_EXECUTION] Reusing cached persistent client for service '{service_name}'")
            
            # Use persistent connection to execute tool directly (avoid state loss from closing connection on each async with)
            logger.info(f"[SESSION_EXECUTION] Executing tool '{tool_name}' with persistent client (no async with)")

            import time as _t
            # 确保连接仍然有效
            try:
                if hasattr(client, 'is_connected') and not client.is_connected():
                    t_reconnect0 = _t.perf_counter()
                    await client._connect()
                    t_reconnect1 = _t.perf_counter()
                    logger.debug(f"[TIMING] client._connect() (reconnect): {(t_reconnect1 - t_reconnect0):.3f}s")
            except Exception as e:
                logger.warning(f"[SESSION_EXECUTION] Client reconnect check failed: {e}")

            # 验证工具存在
            t_list0 = _t.perf_counter()
            tools = await client.list_tools()
            t_list1 = _t.perf_counter()
            logger.debug(f"[TIMING] client.list_tools(): {(t_list1 - t_list0):.3f}s")

            if not any(t.name == tool_name for t in tools):
                available_tools = [t.name for t in tools]
                suggestions = available_tools[:3]
                msg = (
                    f"Tool '{tool_name}' not found in service '{service_name}'. "
                    f"Available: {available_tools}. Suggestions: {suggestions}"
                )
                logger.info(msg)
                raise ToolNotFoundException(
                    tool_name,
                    service_name,
                    details={"suggestions": suggestions},
                )

            # 使用 MCP 规范执行器执行工具（不进入 async with，保持连接）
            t_exec0 = _t.perf_counter()
            result = await executor.execute_tool(
                client=client,
                tool_name=tool_name,
                arguments=arguments,
                timeout=timeout,
                progress_handler=progress_handler,
                raise_on_error=raise_on_error
            )
            t_exec1 = _t.perf_counter()
            logger.debug(f"[TIMING] executor.execute_tool(): {(t_exec1 - t_exec0):.3f}s")

            # Update session activity time
            session.update_activity()
            
            # Return MCP client's CallToolResult (consistent with official implementation)
            logger.info(f"[SESSION_EXECUTION] Tool '{tool_name}' executed successfully in session mode")
            return result
            
        except Exception as e:
            logger.error(f"[SESSION_EXECUTION] Tool execution failed: {e}")
            if raise_on_error:
                raise
            raise Exception(f"Session tool execution failed: {str(e)}")

    async def _create_persistent_client(self, session, service_name: str):
        """
        创建持久的 MCP Client 并缓存到会话中
        
        基于 langchain_mcp_adapters 和 MCP 客户端源码的正确实现：
        
        核心发现：
        1. MCP Client 支持可重入上下文管理器（multiple async with）
        2. 使用引用计数维护连接生命周期
        3. 后台任务管理实际 session 连接
        
        正确的方法：利用 MCP Client 的内置机制，不需要自定义 wrapper
        
        [pykv 唯一真相源] 从实体层获取服务配置
        
        Args:
            session: AgentSession 对象
            service_name: 服务名称
            
        Returns:
            Client: 已连接的 MCP Client，支持多次复用
        """
        try:
            # [pykv 唯一真相源] 从实体层获取服务配置
            service_manager = self.registry._cache_service_manager
            service_entity = await service_manager.get_service(service_name)
            
            if not service_entity:
                raise Exception(f"Service entity not found in pykv: {service_name}")
            
            service_config = service_entity.config
            if not service_config:
                raise Exception(f"Service configuration is empty in pykv: {service_name}")
            
            # 标准化配置
            normalized_config = self._normalize_service_config(service_config)
            
            # Create MCP Client (utilize its reentrant feature)
            client = Client({"mcpServers": {service_name: normalized_config}})
            
            # Start persistent connection (correct usage of MCP Client)
            # 注意：我们调用_connect()而不是使用async with，这样连接会保持活跃
            await client._connect()
            
            # 缓存到会话中
            session.add_service(service_name, client)
            
            logger.info(f"[SESSION_EXECUTION] Persistent client created and cached for service '{service_name}'")
            return client
            
        except Exception as e:
            logger.error(f"[SESSION_EXECUTION] Failed to create persistent client for service '{service_name}': {e}")
            raise

# 这些方法已移除 - 使用MCP Client的内置连接管理

    async def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up MCP Orchestrator resources...")

        # 清理会话
        self.session_manager.cleanup_expired_sessions()

        # 旧的监控任务已被废弃，无需停止
        logger.info("Previous monitoring tasks were already disabled")

        # 关闭所有客户端连接
        for name, client in self.clients.items():
            try:
                await client.close()
            except Exception as e:
                logger.error(f"Error closing client {name}: {e}")

        # 清理所有状态
        self.clients.clear()
        # 智能重连管理器已被废弃，无需清理

        logger.info("MCP Orchestrator cleanup completed")

    async def _restart_monitoring_tasks(self):
        """重启监控任务以应用新配置"""
        logger.info("Restarting monitoring tasks with new configuration...")

        # 旧的监控任务已被废弃，无需停止
        logger.info("Previous monitoring tasks were already disabled")

        # 重新启动监控（现在由ServiceLifecycleManager处理）
        await self._start_monitoring()
        logger.info("Monitoring tasks restarted successfully")
