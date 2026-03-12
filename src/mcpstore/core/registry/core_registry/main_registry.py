"""
ServiceRegistry - 主服务注册表门面类

这是主门面类，已禁用旧接口，统一通过核心缓存管理器工作。
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple

from mcpstore.core.models.service import ServiceConnectionState, ServiceStateMetadata
# 导入所有管理器
from .errors import ERROR_PREFIX, DisabledManagerProxy, raise_disabled_interface_error


class CacheBackedAgentClientService:
    """
    Agent-Client 映射服务（新架构）

    所有数据来源于关系管理器（pykv 唯一真相源）。
    """

    def __init__(self, registry: 'ServiceRegistry'):
        self._registry = registry
        self._relation_manager = registry._relation_manager
        self._run_async = registry._run_async
        self._logger = logging.getLogger(f"{__name__}.AgentClient")

    def add_agent_client_mapping(self, agent_id: str, client_id: str) -> bool:
        """
        Agent-Client 映射由服务映射派生，这里仅保留方法以保持 API 自洽。
        """
        self._logger.debug(
            "[AGENT_CLIENT] add_agent_client_mapping is a no-op (derived from service mappings) "
            "agent_id=%s client_id=%s", agent_id, client_id
        )
        return True

    def remove_agent_client_mapping(self, agent_id: str, client_id: str) -> bool:
        """见 add_agent_client_mapping 说明。"""
        self._logger.debug(
            "[AGENT_CLIENT] remove_agent_client_mapping is a no-op agent_id=%s client_id=%s",
            agent_id,
            client_id,
        )
        return True

    def add_service_client_mapping(self, agent_id: str, service_name: str, client_id: str) -> bool:
        return self._registry.set_service_client_mapping(agent_id, service_name, client_id)

    def remove_service_client_mapping(self, agent_id: str, service_name: str) -> bool:
        return self._registry.remove_service_client_mapping(agent_id, service_name)

    def get_service_client_id(self, agent_id: str, service_name: str) -> Optional[str]:
        return self._registry.get_service_client_id(agent_id, service_name)

    async def get_service_client_id_async(self, agent_id: str, service_name: str) -> Optional[str]:
        """
        异步获取 service -> client_id 映射。

        直接委托给 ServiceRegistry，保持 pyKV 作为唯一数据源。
        """
        return await self._registry.get_service_client_id_async(agent_id, service_name)

    async def get_agent_clients_async(self, agent_id: str) -> List[str]:
        return await self._registry.get_agent_clients_async(agent_id)

    def get_service_client_mapping(self, agent_id: str) -> Dict[str, str]:
        """
        获取 agent 下所有服务与 client_id 的映射。

        同时返回本地名称和全局名称，保证旧代码能识别。
        """
        return self._run_async(
            self.get_service_client_mapping_async(agent_id),
            op_name="AgentClientService.get_service_client_mapping",
        )

    async def get_service_client_mapping_async(self, agent_id: str) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        services = await self._relation_manager.get_agent_services(agent_id)
        for svc in services:
            client_id = svc.get("client_id")
            if not client_id:
                continue
            original = svc.get("service_original_name")
            global_name = svc.get("service_global_name")
            if original:
                mapping[original] = client_id
            if global_name and global_name != original:
                mapping[global_name] = client_id
        return mapping


class CacheBackedServiceStateService:
    """
    ServiceStateService 新实现

    直接委托给 ServiceRegistry 的新式接口，确保所有数据来自 pykv。
    """

    def __init__(self, registry: 'ServiceRegistry'):
        self._registry = registry
        self._logger = logging.getLogger(f"{__name__}.ServiceState")

    def get_service_state(self, agent_id: str, service_name: str) -> Optional[Any]:
        return self._registry.get_service_state(agent_id, service_name)

    def set_service_state(self, agent_id: str, service_name: str, state: Any) -> bool:
        return self._registry.set_service_state(agent_id, service_name, state)

    async def get_service_state_async(self, agent_id: str, service_name: str) -> Optional[Any]:
        return await self._registry.get_service_state_async(agent_id, service_name)

    async def delete_service_state_async(self, agent_id: str, service_name: str) -> bool:
        return await self._registry.delete_service_state_async(agent_id, service_name)

    def get_all_service_names(self, agent_id: str) -> List[str]:
        return self._registry.get_all_service_names(agent_id)

    async def get_all_service_names_async(self, agent_id: str) -> List[str]:
        """
        异步获取指定 agent_id 下所有已注册服务名。
        
        [pykv 唯一真相源] 委托给 ServiceRegistry 的异步方法从 pykv 读取。
        """
        return await self._registry.get_all_service_names_async(agent_id)

    def clear_service_state(self, agent_id: str, service_name: str) -> bool:
        return self._registry.clear_service_state(agent_id, service_name)

    def set_service_metadata(self, agent_id: str, service_name: str, metadata: Any) -> bool:
        return self._registry.set_service_metadata(agent_id, service_name, metadata)

    async def get_service_metadata_async(self, agent_id: str, service_name: str) -> Optional[Any]:
        return await self._registry.get_service_metadata_async(agent_id, service_name)

    async def delete_service_metadata_async(self, agent_id: str, service_name: str) -> bool:
        return await self._registry.delete_service_metadata_async(agent_id, service_name)


class ServiceRegistry:
    """
    主服务注册表门面类

    通过门面模式整合所有专门管理器，提供统一的接口。
        已禁用旧接口，调用将直接报错。
    """

    def __init__(self,
                 kv_store: Optional['AsyncKeyValue'] = None,
                 namespace: str = "mcpstore"):
        """
        Initialize ServiceRegistry with new cache architecture.

        Args:
            kv_store: AsyncKeyValue instance for data storage (required).
                     Session data is always kept in memory regardless of kv_store type.
            namespace: Cache namespace for data isolation (default: "mcpstore")

        Note:
            - Sessions are stored in memory (not serializable)
            - All other data uses the new three-layer cache architecture
            - Uses CacheLayerManager for all cache operations
        """
        self._config = {}
        self._kv_store = self._create_cache_layer(kv_store)
        self._namespace = namespace
        self._logger = logging.getLogger(__name__)

        # 创建缓存层和命名服务
        naming_service = self._create_naming_service()
        from mcpstore.core.cache.cache_layer_manager import CacheLayerManager
        cache_layer_manager = CacheLayerManager(self._kv_store, namespace)

        # 统一缓存入口
        self._cache_layer = cache_layer_manager
        self._naming = naming_service

        # 会话存储（内存中）
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.service_states: Dict[str, Dict[str, Any]] = {}
        self.service_metadata: Dict[str, Dict[str, Any]] = {}

        # 统一配置管理器
        self._unified_config = None

        # 同步助手（懒加载）
        self._sync_helper: Optional[Any] = None

        # 状态同步管理器
        self._state_sync_manager = None

        self._coordinator = DisabledManagerProxy(
            "core_registry.ManagerCoordinator",
            "ManagerCoordinator is disabled; use CacheLayerManager.",
        )
        from mcpstore.core.registry.core_registry.session_manager import SessionManager
        self._session_manager = SessionManager(cache_layer_manager, naming_service, namespace)
        self.sessions = self._session_manager.sessions
        self._tool_manager = DisabledManagerProxy(
            "core_registry.ToolManager",
            "ToolManager is disabled; use core/cache tool managers.",
        )
        self._cache_manager = DisabledManagerProxy(
            "core_registry.CacheManager",
            "CacheManager is disabled; use CacheLayerManager.",
        )
        # 缓存同步状态记录（初始化时间/同步来源等），供初始化/同步流程写入
        self.cache_sync_status: Dict[str, Any] = {}
        # 缓存是否已完成初始化的标记（单一数据源模式使用）
        self.cache_initialized: bool = False
        self._persistence_manager = DisabledManagerProxy(
            "core_registry.PersistenceManager",
            "PersistenceManager is disabled; use core/cache shells.",
        )
        self._service_manager = DisabledManagerProxy(
            "core_registry.ServiceManager",
            "ServiceManager is disabled; use core/cache service managers.",
        )

        self._mapping_manager = DisabledManagerProxy(
            "core_registry.MappingManager",
            "MappingManager is disabled; use core/cache relationship managers.",
        )

        # 创建缓存层管理器（原始架构中的核心组件）
        # 这些管理器直接操作 pykv，是数据的唯一真相源
        from mcpstore.core.cache.service_entity_manager import ServiceEntityManager
        from mcpstore.core.cache.tool_entity_manager import ToolEntityManager
        from mcpstore.core.cache.state_manager import StateManager as CacheStateManager
        from mcpstore.core.cache.relationship_manager import RelationshipManager

        # 缓存层实体管理器（用于直接操作 pykv）
        self._cache_service_manager = ServiceEntityManager(cache_layer_manager, naming_service)
        self._cache_tool_manager = ToolEntityManager(cache_layer_manager, naming_service)
        self._cache_state_manager = CacheStateManager(cache_layer_manager)
        self._state_manager = self._cache_state_manager
        self._cache_layer_manager = cache_layer_manager

        # 创建关系管理器（使用 CacheLayerManager）
        self._relation_manager = RelationshipManager(cache_layer_manager)
        self._logger.debug("Cache layer manager initialization successful")
        
        # 映射管理器已禁用

        # 面向核心模块的 façade，统一通过新的缓存管理器实现
        self._service_state_service = CacheBackedServiceStateService(self)
        self._agent_client_service = CacheBackedAgentClientService(self)

        self._logger.info("ServiceRegistry initialized with all managers")

    async def switch_backend(self, kv_store, namespace: Optional[str] = None) -> bool:
        """
        运行时切换底层 KV 存储，并重建缓存管理器

        Args:
            kv_store: 新的 AsyncKeyValue 实例（MemoryStore 或 RedisStore）
            namespace: 可选命名空间，默认沿用当前设置

        Returns:
            bool: 切换是否成功

        Raises:
            ValueError: 当 kv_store 为空时抛出
        """
        if kv_store is None:
            raise ValueError("kv_store cannot be empty, must provide a valid AsyncKeyValue instance")

        ns = namespace or self._namespace

        # 记录旧的缓存层以便迁移数据
        old_cache_layer = getattr(self, "_cache_layer_manager", None)

        # 重新构建 CacheLayer 及相关管理器，确保所有读写都指向新的后端
        from mcpstore.core.cache.cache_layer_manager import CacheLayerManager
        from mcpstore.core.cache.service_entity_manager import ServiceEntityManager
        from mcpstore.core.cache.tool_entity_manager import ToolEntityManager
        from mcpstore.core.cache.state_manager import StateManager as CacheStateManager
        from mcpstore.core.cache.relationship_manager import RelationshipManager
        from mcpstore.core.registry.core_registry.session_manager import SessionManager

        self._kv_store = kv_store
        self._namespace = ns
        self._cache_layer = CacheLayerManager(kv_store, ns)
        self._cache_layer_manager = self._cache_layer

        # 保持同一命名服务实例
        naming_service = self._naming or self._create_naming_service()

        self._cache_service_manager = ServiceEntityManager(self._cache_layer, naming_service)
        self._cache_tool_manager = ToolEntityManager(self._cache_layer, naming_service)
        self._cache_state_manager = CacheStateManager(self._cache_layer)
        self._state_manager = self._cache_state_manager
        self._relation_manager = RelationshipManager(self._cache_layer)

        # 会话管理器依赖新的 cache_layer
        self._session_manager = SessionManager(self._cache_layer, naming_service, ns)
        self.sessions = self._session_manager.sessions

        # 尝试迁移旧缓存中的实体/关系/状态，避免切换后需要重新添加服务
        try:
            if old_cache_layer:
                migrate_entities = 0
                migrate_relations = 0
                migrate_states = 0

                entity_types = ["services", "tools", "agents", "store", "clients"]
                for et in entity_types:
                    data = await old_cache_layer.get_all_entities_async(et)
                    for k, v in (data or {}).items():
                        await self._cache_layer_manager.put_entity(et, k, v)
                        migrate_entities += 1

                relation_types = ["agent_services", "service_tools"]
                for rt in relation_types:
                    data = await old_cache_layer.get_all_relations_async(rt)
                    for k, v in (data or {}).items():
                        await self._cache_layer_manager.put_relation(rt, k, v)
                        migrate_relations += 1

                state_types = ["service_status", "service_metadata"]
                for st in state_types:
                    data = await old_cache_layer.get_all_states_async(st)
                    for k, v in (data or {}).items():
                        await self._cache_layer_manager.put_state(st, k, v)
                        migrate_states += 1

                self._logger.info(
                    "[SWITCH_BACKEND] Migrated cache data to new backend: "
                    "entities=%d relations=%d states=%d namespace=%s backend=%s",
                    migrate_entities,
                    migrate_relations,
                    migrate_states,
                    ns,
                    type(kv_store).__name__,
                )
        except Exception as migrate_err:
            self._logger.warning(
                "[SWITCH_BACKEND] Cache migration failed: %s", migrate_err, exc_info=True
            )

        self._logger.info("Registry backend switched successfully: namespace=%s, backend=%s", ns, type(kv_store).__name__)
        return True

    async def _ensure_agent_entity(self, agent_id: str) -> None:
        """
        确保 Agent 实体存在；若已存在则刷新最后活跃时间。
        """
        if not agent_id:
            return
        try:
            now_ts = int(time.time())
            agent = await self._cache_layer_manager.get_agent(agent_id)
            if agent is None:
                await self._cache_layer_manager.create_agent(
                    agent_id=agent_id,
                    created_time=now_ts,
                    is_global=(agent_id == self._naming.GLOBAL_AGENT_STORE)
                )
                self._logger.info(f"[AGENT] Created agent entity: {agent_id}")
            else:
                await self._cache_layer_manager.update_agent_last_active(agent_id, now_ts)
        except Exception as e:
            self._logger.warning(f"[AGENT] ensure_agent_entity failed for {agent_id}: {e}")

    def _disabled_interface(self, method: str) -> None:
        raise_disabled_interface_error(
            f"ServiceRegistry.{method}",
            "Disabled interface; use core/cache managers and shells.",
        )

    def _create_cache_layer(self, kv_store=None):
        """
        创建缓存层
        
        Args:
            kv_store: AsyncKeyValue 实例，必须提供
            
        Returns:
            传入的 kv_store 实例
            
        Raises:
            RuntimeError: 如果 kv_store 为 None
        """
        if kv_store is None:
            raise RuntimeError(
                f"{ERROR_PREFIX} kv_store parameter cannot be None. "
                "ServiceRegistry must be initialized with a valid AsyncKeyValue instance. "
                "Please use MemoryStore or RedisStore for initialization."
            )
        return kv_store

    def _create_naming_service(self):
        """创建命名服务"""
        # 优先使用真正的 NamingService
        try:
            from mcpstore.core.cache.naming_service import NamingService
            return NamingService()
        except ImportError:
            raise RuntimeError(
                f"{ERROR_PREFIX} NamingService import failed; no fallback is allowed."
            )

    def _run_async(self, coro, op_name: str):
        from mcpstore.core.bridge import get_async_bridge

        return get_async_bridge().run(coro, op_name=op_name)

    def _map_health_status(self, health_status: Any):
        if isinstance(health_status, ServiceConnectionState):
            return health_status
        if isinstance(health_status, str):
            try:
                return ServiceConnectionState(health_status)
            except ValueError as exc:
                raise RuntimeError(
                    f"{ERROR_PREFIX} Invalid service health_status: {health_status}"
                ) from exc
        raise RuntimeError(
            f"{ERROR_PREFIX} Invalid service health_status type: {type(health_status).__name__}"
        )

    def _cache_state_snapshot(self, agent_id: str, service_name: str, state_value: Optional[Any]) -> None:
        """
        维护内存中的运行时状态快照，供共享 client 状态同步和事务快照使用。
        """
        if not agent_id or not service_name:
            return
        if state_value is None:
            agent_states = self.service_states.get(agent_id)
            if agent_states and service_name in agent_states:
                agent_states.pop(service_name, None)
                if not agent_states:
                    self.service_states.pop(agent_id, None)
            return
        mapped_state = self._map_health_status(state_value)
        self.service_states.setdefault(agent_id, {})[service_name] = mapped_state

    def _cache_metadata_snapshot(self, agent_id: str, service_name: str, metadata: Optional[Any]) -> None:
        """
        维护内存中的服务元数据快照。
        """
        if not agent_id or not service_name:
            return
        if metadata is None:
            agent_meta = self.service_metadata.get(agent_id)
            if agent_meta and service_name in agent_meta:
                agent_meta.pop(service_name, None)
                if not agent_meta:
                    self.service_metadata.pop(agent_id, None)
            return
        if isinstance(metadata, ServiceStateMetadata):
            metadata_obj = metadata
        elif hasattr(metadata, "model_dump"):
            metadata_obj = ServiceStateMetadata.model_validate(metadata.model_dump())
        elif isinstance(metadata, dict):
            metadata_obj = ServiceStateMetadata.model_validate(metadata)
        else:
            # 无法识别的类型，直接存储原值，便于调试
            metadata_obj = metadata
        self.service_metadata.setdefault(agent_id, {})[service_name] = metadata_obj

    async def _resolve_global_name_async(self, agent_id: str, service_name: str) -> Optional[str]:
        if not agent_id:
            raise ValueError("Agent ID cannot be empty")
        if not service_name:
            raise ValueError("Service name cannot be empty")

        if agent_id == self._naming.GLOBAL_AGENT_STORE:
            return service_name

        if self._naming.AGENT_SEPARATOR in service_name:
            global_name = service_name
        else:
            services = await self._relation_manager.get_agent_services(agent_id)
            for svc in services:
                if svc.get("service_original_name") == service_name:
                    return svc.get("service_global_name")
            return None

        services = await self._relation_manager.get_agent_services(agent_id)
        for svc in services:
            if svc.get("service_global_name") == global_name:
                return global_name
        return None

    # ========================================
    # 会话管理方法 (委托给SessionManager)
    # ========================================

    async def initialize(self) -> None:
        """初始化所有管理器"""
        self._disabled_interface("initialize")

    async def cleanup(self) -> None:
        """清理所有管理器资源"""
        self._disabled_interface("cleanup")

    def create_session(self, agent_id: str, session_type: str = "default",
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        return self._session_manager.create_session(agent_id, session_type, metadata)

    async def create_session_async(self, agent_id: str, session_type: str = "default",
                                 metadata: Optional[Dict[str, Any]] = None) -> str:
        return await self._session_manager.create_session_async(agent_id, session_type, metadata)

    def get_session(self, agent_id: str, name: str) -> Optional[Any]:
        """
        获取指定agent_id下服务的会话对象

        Args:
            agent_id: Agent ID
            name: 服务名称

        Returns:
            会话对象或None
        """
        return self._session_manager.get_session(agent_id, name)

    def close_session(self, session_id: str) -> bool:
        return self._session_manager.close_session(session_id)

    async def close_session_async(self, session_id: str) -> bool:
        return await self._session_manager.close_session_async(session_id)

    def list_sessions(self, agent_id: Optional[str] = None) -> List[str]:
        return self._session_manager.list_sessions(agent_id)

    def add_tool_to_session(self, session_id: str, tool_name: str) -> bool:
        return self._session_manager.add_tool_to_session(session_id, tool_name)

    def remove_tool_from_session(self, session_id: str, tool_name: str) -> bool:
        return self._session_manager.remove_tool_from_session(session_id, tool_name)

    def get_session_tools(self, session_id: str) -> Set[str]:
        return self._session_manager.get_session_tools(session_id)

    def clear_agent_sessions(self, agent_id: str) -> None:
        raise_disabled_interface_error(
            "ServiceRegistry.clear_agent_sessions",
            "Use session_manager.clear_all_sessions via the cache-backed architecture.",
        )

    def clear(self, agent_id: str) -> bool:
        """
        同步清空指定 Agent 的所有注册信息。
        """
        return self._run_async(
            self.clear_async(agent_id),
            op_name="ServiceRegistry.clear",
        )

    async def clear_async(self, agent_id: str) -> bool:
        """
        异步清空指定 Agent 的所有注册信息。

        Args:
            agent_id: Agent ID
        """
        if not agent_id:
            raise ValueError("Agent ID cannot be empty")

        services = await self._relation_manager.get_agent_services(agent_id)
        client_ids: Set[str] = set()
        seen: Set[str] = set()
        for svc in services:
            # 这里统一使用 service_global_name 作为清理用的标识：
            # - 对 global_agent_store：service_global_name 即“全局视角”ID，避免误用本地名导致关系不匹配
            # - 对普通 agent：remove_service_async(agent_id, global_name) 也能通过关系表验证并安全删除
            service_name = svc.get("service_global_name") or svc.get("service_original_name")
            cid = svc.get("client_id")
            if cid:
                client_ids.add(cid)
            if not service_name or service_name in seen:
                continue
            seen.add(service_name)
            try:
                await self.remove_service_async(agent_id, service_name)
            except Exception as exc:
                self._logger.warning(
                    "Failed to remove service '%s' for agent '%s' during clear_async: %s",
                    service_name,
                    agent_id,
                    exc,
                )

        # 清理客户端实体（避免留下孤立 client 记录）
        try:
            # 关系层可能包含更多 client_id，合并一次
            rel_client_ids = await self.get_agent_clients_async(agent_id)
            client_ids.update(rel_client_ids)
            for cid in client_ids:
                await self._cache_layer_manager.delete_entity("clients", cid)
        except Exception as exc:
            self._logger.warning("Failed to cleanup clients for agent '%s': %s", agent_id, exc)

        self.service_states.pop(agent_id, None)
        self.service_metadata.pop(agent_id, None)
        self.sessions.pop(agent_id, None)
        if self._session_manager:
            self._session_manager.clear_all_sessions(agent_id)
        return True

    # ========================================
    # 服务管理方法 (委托给ServiceManager)
    # ========================================

    def add_service(self, agent_id: str, name: str, session: Any = None,
                   tools: List[tuple] = None, service_config: Dict[str, Any] = None,
                   auto_connect: bool = True) -> bool:
        """
        添加服务

        Args:
            agent_id: Agent ID
            name: 服务名称
            session: 服务会话对象
            tools: 工具列表 [(tool_name, tool_def)]
            service_config: 服务配置
            auto_connect: 是否自动连接

        Returns:
            是否成功添加
        """
        return self._run_async(
            self.add_service_async(
                agent_id=agent_id,
                name=name,
                session=session,
                tools=tools,
                service_config=service_config,
                auto_connect=auto_connect,
            ),
            op_name="ServiceRegistry.add_service",
        )

    async def add_service_async(self, agent_id: str, name: str, session: Any = None,
                               tools: List[tuple] = None, service_config: Dict[str, Any] = None,
                               auto_connect: bool = True, preserve_mappings: bool = False,
                               state: Any = None, client_id: Optional[str] = None) -> bool:
        """
        异步添加服务

        Args:
            agent_id: Agent ID
            name: 服务名称
            session: 服务会话对象
            tools: 工具列表 [(tool_name, tool_def)]
            service_config: 服务配置
            auto_connect: 是否自动连接
            preserve_mappings: 是否保留已有的映射关系
            state: 服务状态（可选）

        Returns:
            是否成功添加
        """
        if not agent_id:
            raise ValueError("Agent ID cannot be empty")
        if not name:
            raise ValueError("Service name cannot be empty")

        tools = tools or []
        service_config = service_config or {}

        # 确保 Agent 实体存在（无论全局还是普通 Agent）
        await self._ensure_agent_entity(agent_id)

        service_global_name = await self._cache_service_manager.create_service(
            agent_id=agent_id,
            original_name=name,
            config=service_config
        )

        existing_client_id = None
        if preserve_mappings:
            services = await self._relation_manager.get_agent_services(agent_id)
            for svc in services:
                if svc.get("service_global_name") == service_global_name or svc.get("service_original_name") == name:
                    existing_client_id = svc.get("client_id")
                    break

        if existing_client_id:
            client_id = existing_client_id
        if not client_id:
            from mcpstore.core.utils.id_generator import ClientIDGenerator
            client_id = ClientIDGenerator.generate_deterministic_id(
                agent_id=agent_id,
                service_name=name,
                service_config=service_config,
                global_agent_store_id=self._naming.GLOBAL_AGENT_STORE,
            )

        # 写入/更新 clients 实体
        import time
        now_ts = int(time.time())
        client_entity = await self._cache_layer_manager.get_entity("clients", client_id)
        if not isinstance(client_entity, dict):
            client_entity = {
                "client_id": client_id,
                "agent_id": agent_id,
                "services": [],
                "created_time": now_ts,
            }
        services_list = client_entity.get("services") or []
        if service_global_name not in services_list:
            services_list.append(service_global_name)
        client_entity.update({
            "agent_id": agent_id,
            "services": services_list,
            "updated_time": now_ts,
        })
        await self._cache_layer_manager.put_entity("clients", client_id, client_entity)

        await self._relation_manager.add_agent_service(
            agent_id=agent_id,
            service_original_name=name,
            service_global_name=service_global_name,
            client_id=client_id
        )

        tools_status = []
        for tool in tools:
            if isinstance(tool, tuple) and len(tool) == 2:
                tool_name, tool_def = tool
            elif isinstance(tool, dict):
                tool_name = tool.get("name")
                tool_def = tool
            else:
                raise ValueError(f"Invalid tool definition: {tool}")

            # 提取工具原始名称（去除服务前缀）
            # 注意：MCP 服务返回的工具名称可能已经带有服务前缀
            # 例如：mcpstore_get_current_weather -> get_current_weather
            from mcpstore.core.logic.tool_logic import ToolLogicCore
            original_tool_name = ToolLogicCore.extract_original_tool_name(
                tool_name, service_global_name
            )

            tool_global_name = await self._cache_tool_manager.create_tool(
                service_global_name=service_global_name,
                service_original_name=name,
                source_agent=agent_id,
                tool_original_name=original_tool_name,
                tool_def=tool_def
            )
            await self._relation_manager.add_service_tool(
                service_global_name=service_global_name,
                service_original_name=name,
                source_agent=agent_id,
                tool_global_name=tool_global_name,
                tool_original_name=original_tool_name
            )
            tools_status.append({
                "tool_global_name": tool_global_name,
                "tool_original_name": original_tool_name,
                "status": "available"
            })

        if state is None:
            from mcpstore.core.models.service import ServiceConnectionState
            state = ServiceConnectionState.STARTUP

        health_status = state.value if hasattr(state, "value") else str(state)
        await self._cache_state_manager.update_service_status(
            service_global_name=service_global_name,
            health_status=health_status,
            tools_status=tools_status
        )
        # 初始化 service_metadata 状态
        try:
            metadata_state = {
                "service_global_name": service_global_name,
                "agent_id": agent_id,
                "created_time": now_ts,
                "state_entered_time": now_ts,
                "reconnect_attempts": 0,
                "last_ping_time": None,
            }
            await self._cache_layer_manager.put_state("service_metadata", service_global_name, metadata_state)
        except Exception as meta_error:
            self._logger.warning(f"[SERVICE_METADATA] init metadata failed for {service_global_name}: {meta_error}")

        self._cache_state_snapshot(agent_id, name, state)

        if session is not None:
            self._session_manager.set_session(agent_id, name, session)

        return True

    async def remove_service_async(self, agent_id: str, name: str) -> Optional[Any]:
        """
        异步移除服务（代理到 ServiceManager）

        Args:
            agent_id: Agent ID
            name: 服务名称

        Returns:
            被移除的会话对象
        """
        if not agent_id:
            raise ValueError("Agent ID cannot be empty")
        if not name:
            raise ValueError("Service name cannot be empty")

        global_name = await self._resolve_global_name_async(agent_id, name)
        if not global_name:
            return None
        self._logger.info(f"[REGISTRY_REMOVE] agent={agent_id} service={name} global={global_name} start")

        tool_relations = await self._relation_manager.get_service_tools(global_name)

        await self._relation_manager.remove_service_cascade(agent_id, global_name)
        await self._cache_layer_manager.delete_entity("services", global_name)
        await self._cache_layer_manager.delete_state("service_status", global_name)
        await self._cache_layer_manager.delete_state("service_metadata", global_name)

        for tool in tool_relations:
            tool_global_name = tool.get("tool_global_name")
            if tool_global_name:
                await self._cache_tool_manager.delete_tool(tool_global_name)

        if self._session_manager:
            self._session_manager.clear_session(agent_id, name)

        self._cache_state_snapshot(agent_id, name, None)
        self._cache_metadata_snapshot(agent_id, name, None)

        remaining = await self._cache_layer_manager.get_entity("services", global_name)
        self._logger.info(f"[REGISTRY_REMOVE] agent={agent_id} global={global_name} removed entity_exists={remaining is not None}")

        return None

    def register_service(self, service_config: Dict[str, Any]) -> bool:
        return self._service_manager.register_service(service_config)

    async def register_service_async(self, service_config: Dict[str, Any]) -> bool:
        return await self._service_manager.register_service_async(service_config)

    def unregister_service(self, service_name: str) -> bool:
        return self._service_manager.unregister_service(service_name)

    async def unregister_service_async(self, service_name: str) -> bool:
        return await self._service_manager.unregister_service_async(service_name)

    def get_service_details(self, agent_id: str, service_name: str) -> Optional[Dict[str, Any]]:
        info = self.get_complete_service_info(agent_id, service_name)
        if not info:
            return None
        return {
            "service_name": info.get("service_original_name"),
            "service_global_name": info.get("service_global_name"),
            "config": info.get("config", {}),
            "state": info.get("state"),
            "state_metadata": info.get("state_metadata"),
            "state_entered_time": info.get("state_entered_time"),
            "last_heartbeat": info.get("last_heartbeat"),
            "client_id": info.get("client_id"),
            "tools": info.get("tools", []),
            "tool_count": info.get("tool_count", 0),
        }

    def get_services_for_agent(self, agent_id: str) -> List[str]:
        return self._run_async(
            self.get_services_for_agent_async(agent_id),
            op_name="ServiceRegistry.get_services_for_agent",
        )

    def is_service_registered(self, service_name: str) -> bool:
        entity = self._run_async(
            self._cache_layer_manager.get_entity("services", service_name),
            op_name="ServiceRegistry.is_service_registered",
        )
        return entity is not None

    def has_service(self, agent_id: str, service_name: str) -> bool:
        """
        检查指定 Agent 是否拥有指定服务

        Args:
            agent_id: Agent ID
            service_name: 服务名称

        Returns:
            服务是否存在
        """
        return self._run_async(
            self.has_service_async(agent_id, service_name),
            op_name="ServiceRegistry.has_service",
        )

    async def has_service_async(self, agent_id: str, service_name: str) -> bool:
        """
        异步检查指定 Agent 是否拥有指定服务

        遵循 "Functional Core, Imperative Shell" 架构原则：
        - 异步外壳直接使用 await 调用异步操作
        - 在异步上下文中必须使用此方法，而非同步版本

        Args:
            agent_id: Agent ID
            service_name: 服务名称

        Returns:
            服务是否存在
        """
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            return False
        entity = await self._cache_layer_manager.get_entity("services", global_name)
        return entity is not None

    async def get_services_for_agent_async(self, agent_id: str) -> List[str]:
        """
        异步获取指定 Agent 的所有服务

        Args:
            agent_id: Agent ID

        Returns:
            服务名称列表
        """
        services = await self._relation_manager.get_agent_services(agent_id)
        return [svc.get("service_original_name") for svc in services if svc.get("service_original_name")]

    def get_all_services(self) -> List[str]:
        services = self._run_async(
            self._cache_layer_manager.get_all_entities_async("services"),
            op_name="ServiceRegistry.get_all_services",
        )
        return list(services.keys())

    def get_service_count(self) -> int:
        return len(self.get_all_services())

    def update_service_config(self, service_name: str, updates: Dict[str, Any]) -> bool:
        return self._run_async(
            self.update_service_config_async(service_name, updates),
            op_name="ServiceRegistry.update_service_config",
        )

    async def update_service_config_async(self, service_name: str, updates: Dict[str, Any]) -> bool:
        if not service_name:
            raise ValueError("Service name cannot be empty")
        if not isinstance(updates, dict):
            raise ValueError("updates must be a dictionary type")

        entity = await self._cache_layer_manager.get_entity("services", service_name)
        if entity is None:
            return False
        config = entity.get("config", {})
        if not isinstance(config, dict):
            config = {}
        config.update(updates)
        entity["config"] = config
        await self._cache_layer_manager.put_entity("services", service_name, entity)
        return True

    def get_service_config(self, service_name: str) -> Optional[Dict[str, Any]]:
        entity = self._run_async(
            self._cache_layer_manager.get_entity("services", service_name),
            op_name="ServiceRegistry.get_service_config",
        )
        if not entity:
            return None
        return entity.get("config")

    def get_service_config_from_cache(self, agent_id: str, service_name: str) -> Optional[Dict[str, Any]]:
        """
        从缓存获取指定 Agent 下的服务配置（同步入口）

        语义：以命名服务解析全局名，再从实体层读取配置，避免绕过注册中心。
        """
        return self._run_async(
            self.get_service_config_from_cache_async(agent_id, service_name),
            op_name="ServiceRegistry.get_service_config_from_cache",
        )

    async def get_service_config_from_cache_async(self, agent_id: str, service_name: str) -> Optional[Dict[str, Any]]:
        """
        从缓存获取指定 Agent 下的服务配置（异步入口）

        - 使用命名服务生成全局名，确保视角一致
        - 通过 CacheLayerManager 读取实体层配置，保持单一数据源
        """
        if not agent_id:
            raise ValueError("agent_id cannot be empty")
        if not service_name:
            raise ValueError("service_name cannot be empty")

        info = await self.get_complete_service_info_async(agent_id, service_name)
        if not info:
            return None

        config = info.get("config")
        if config is None:
            return None
        if not isinstance(config, dict):
            raise RuntimeError(
                f"Service config format is invalid, expected dict, actual type {type(config).__name__} "
                f"(agent_id={agent_id}, service_name={service_name})"
            )

        return config

    def get_service_summary(self, service_name: str) -> Optional[Dict[str, Any]]:
        info = self.get_complete_service_info(self._naming.GLOBAL_AGENT_STORE, service_name)
        if not info:
            return None
        return {
            "service_name": info.get("service_original_name"),
            "service_global_name": info.get("service_global_name"),
            "state": info.get("state"),
            "tool_count": info.get("tool_count", 0),
            "client_id": info.get("client_id"),
        }

    async def get_service_summary_async(self, service_name: str) -> Optional[Dict[str, Any]]:
        info = await self.get_complete_service_info_async(self._naming.GLOBAL_AGENT_STORE, service_name)
        if not info:
            return None
        return {
            "service_name": info.get("service_original_name"),
            "service_global_name": info.get("service_global_name"),
            "state": info.get("state"),
            "tool_count": info.get("tool_count", 0),
            "client_id": info.get("client_id"),
        }

    def get_complete_service_info(self, agent_id: str, service_name: str) -> Optional[Dict[str, Any]]:
        """
        获取服务的完整信息

        Args:
            agent_id: Agent ID
            service_name: 服务名称

        Returns:
            服务完整信息字典
        """
        return self._run_async(
            self.get_complete_service_info_async(agent_id, service_name),
            op_name="ServiceRegistry.get_complete_service_info",
        )

    async def get_complete_service_info_async(self, agent_id: str, service_name: str) -> Optional[Dict[str, Any]]:
        """
        异步获取服务的完整信息

        Args:
            agent_id: Agent ID
            service_name: 服务名称

        Returns:
            服务完整信息字典
        """
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            return None

        entity = await self._cache_layer_manager.get_entity("services", global_name)
        if not entity:
            return None

        config = entity.get("config", {}) if isinstance(entity, dict) else {}
        service_original_name = entity.get("service_original_name", service_name)

        state = None
        status = await self._cache_state_manager.get_service_status(global_name)
        if status is not None:
            health_status = status.health_status if hasattr(status, "health_status") else status.get("health_status")
            state = self._map_health_status(health_status)

        metadata = await self._cache_layer_manager.get_state("service_metadata", global_name)
        metadata_obj = None
        if metadata:
            from mcpstore.core.models.service import ServiceStateMetadata
            metadata_obj = ServiceStateMetadata.model_validate(metadata)

        client_id = None
        agent_services = await self._relation_manager.get_agent_services(agent_id)
        for svc in agent_services:
            if svc.get("service_global_name") == global_name:
                client_id = svc.get("client_id")
                break

        tool_relations = await self._relation_manager.get_service_tools(global_name)
        tool_global_names = [
            tool.get("tool_global_name")
            for tool in tool_relations
            if tool.get("tool_global_name")
        ]
        tool_entities = await self._cache_tool_manager.get_many_tools(tool_global_names) if tool_global_names else []

        tools_info: List[Dict[str, Any]] = []
        if tool_entities:
            from mcpstore.core.logic.tool_logic import ToolInfo as ToolInfoCore
            for tool_entity in tool_entities:
                if tool_entity is None:
                    continue
                entity_dict = tool_entity.to_dict() if hasattr(tool_entity, "to_dict") else tool_entity
                tool_info = ToolInfoCore.from_entity(
                    entity_dict,
                    service_original_name,
                    global_name,
                    client_id=client_id
                )
                tools_info.append(tool_info.to_dict())

        return {
            "service_global_name": global_name,
            "service_original_name": service_original_name,
            "config": config,
            "state": state,
            "state_metadata": metadata_obj,
            "state_entered_time": getattr(metadata_obj, "state_entered_time", None) if metadata_obj else None,
            "last_heartbeat": getattr(metadata_obj, "last_ping_time", None) if metadata_obj else None,
            "client_id": client_id,
            "tools": tools_info,
            "tool_count": len(tool_global_names),
        }

    def get_all_services_complete_info(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        async def _fetch_all():
            effective_agent = agent_id or self._naming.GLOBAL_AGENT_STORE
            services = await self._relation_manager.get_agent_services(effective_agent)
            results: List[Dict[str, Any]] = []
            for svc in services:
                global_name = svc.get("service_global_name")
                if not global_name:
                    continue
                info = await self.get_complete_service_info_async(effective_agent, global_name)
                if info:
                    results.append(info)
            return results

        return self._run_async(_fetch_all(), op_name="ServiceRegistry.get_all_services_complete_info")

    def clear_agent_lifecycle_data(self, agent_id: str) -> bool:
        return self._service_manager.clear_agent_lifecycle_data(agent_id)

    def get_stats(self) -> Dict[str, Any]:
        return self._service_manager.get_stats()

    def is_long_lived_service(self, service_name: str) -> bool:
        return self._service_manager.is_long_lived_service(service_name)

    def mark_as_long_lived(self, agent_id: str, service_name: str):
        return self._service_manager.mark_as_long_lived(agent_id, service_name)

    def set_long_lived_service(self, service_name: str, is_long_lived: bool) -> bool:
        return self._service_manager.set_long_lived_service(service_name, is_long_lived)

    def get_services_by_state(self, states: List[str]) -> List[str]:
        return self._service_manager.get_services_by_state(states)

    def get_healthy_services(self) -> List[str]:
        return self._service_manager.get_healthy_services()

    def get_failed_services(self) -> List[str]:
        return self._service_manager.get_failed_services()

    def get_services_with_tools(self) -> List[str]:
        return self._service_manager.get_services_with_tools()

    def should_cache_aggressively(self, service_name: str) -> bool:
        return self._service_manager.should_cache_aggressively(service_name)

    def remove_service_lifecycle_data(self, service_name: str, agent_id: str) -> bool:
        return self._service_manager.remove_service_lifecycle_data(service_name, agent_id)

    def set_service_lifecycle_data(self, service_name: str, agent_id: str, data: Dict[str, Any]) -> bool:
        return self._service_manager.set_service_lifecycle_data(service_name, agent_id, data)

    # ========================================
    # 客户端映射方法 (委托给MappingManager)
    # ========================================

    async def get_service_client_id_async(self, agent_id: str, service_name: str) -> Optional[str]:
        services = await self._relation_manager.get_agent_services(agent_id)
        for svc in services:
            if svc.get("service_original_name") == service_name or svc.get("service_global_name") == service_name:
                return svc.get("client_id")
        return None

    def get_service_client_id(self, agent_id: str, service_name: str) -> Optional[str]:
        return self._run_async(
            self.get_service_client_id_async(agent_id, service_name),
            op_name="ServiceRegistry.get_service_client_id",
        )

    async def get_agent_clients_async(self, agent_id: str) -> List[str]:
        """
        从 pykv 关系层获取 Agent 的所有客户端
        
        [pykv 唯一真相源] 所有数据必须从 pykv 读取
        
        Args:
            agent_id: Agent ID
            
        Returns:
            客户端ID列表
        """
        services = await self._relation_manager.get_agent_services(agent_id)
        client_ids = {svc.get("client_id") for svc in services if svc.get("client_id")}
        return list(client_ids)

    def get_client_config_from_cache(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        从缓存获取客户端配置

        Args:
            client_id: 客户端ID

        Returns:
            客户端配置或None
        """
        return self._run_async(
            self.get_client_config_from_cache_async(client_id),
            op_name="ServiceRegistry.get_client_config_from_cache",
        )

    async def get_client_config_from_cache_async(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        异步从缓存获取客户端配置

        Args:
            client_id: 客户端ID

        Returns:
            客户端配置或None
        """
        return await self._cache_layer_manager.get_entity("clients", client_id)

    def add_client_config(self, client_id: str, client_config: Dict[str, Any]) -> str:
        if not client_id:
            raise ValueError("client_id cannot be empty")
        if not isinstance(client_config, dict):
            raise ValueError("client_config must be a dictionary type")
        self._run_async(
            self._cache_layer_manager.put_entity("clients", client_id, client_config),
            op_name="ServiceRegistry.add_client_config",
        )
        return client_id

    def set_service_client_mapping(self, agent_id: str, service_name: str, client_id: str) -> bool:
        return self._run_async(
            self.set_service_client_mapping_async(agent_id, service_name, client_id),
            op_name="ServiceRegistry.set_service_client_mapping",
        )

    async def set_service_client_mapping_async(self, agent_id: str, service_name: str, client_id: str) -> bool:
        if not client_id:
            raise ValueError("client_id cannot be empty")
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            global_name = self._naming.generate_service_global_name(service_name, agent_id)

        if self._naming.AGENT_SEPARATOR in service_name:
            service_original_name, _ = self._naming.parse_service_global_name(service_name)
        else:
            service_original_name = service_name

        # 确保 clients 实体存在，并关联当前服务
        import time
        client_entity = await self._cache_layer_manager.get_entity("clients", client_id)
        if not isinstance(client_entity, dict):
            client_entity = {
                "client_id": client_id,
                "agent_id": agent_id,
                "services": [],
                "created_time": int(time.time()),
            }
        services = client_entity.get("services") or []
        if global_name not in services:
            services.append(global_name)
        client_entity.update({
            "agent_id": agent_id,
            "services": services,
            "updated_time": int(time.time()),
        })
        await self._cache_layer_manager.put_entity("clients", client_id, client_entity)

        await self._relation_manager.add_agent_service(
            agent_id=agent_id,
            service_original_name=service_original_name,
            service_global_name=global_name,
            client_id=client_id
        )
        return True

    def remove_service_client_mapping(self, agent_id: str, service_name: str) -> bool:
        return self._run_async(
            self.delete_service_client_mapping_async(agent_id, service_name),
            op_name="ServiceRegistry.remove_service_client_mapping",
        )

    async def delete_service_client_mapping_async(self, agent_id: str, service_name: str) -> bool:
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            global_name = self._naming.generate_service_global_name(service_name, agent_id)
        await self._relation_manager.remove_agent_service(agent_id, global_name)
        return True

    def add_agent_service_mapping(self, agent_id: str, service_name: str, global_name: str) -> bool:
        from mcpstore.core.utils.id_generator import ClientIDGenerator
        client_id = ClientIDGenerator.generate_deterministic_id(
            agent_id=agent_id,
            service_name=service_name,
            service_config={},
            global_agent_store_id=self._naming.GLOBAL_AGENT_STORE,
        )
        self._run_async(
            self._relation_manager.add_agent_service(
                agent_id=agent_id,
                service_original_name=service_name,
                service_global_name=global_name,
                client_id=client_id,
            ),
            op_name="ServiceRegistry.add_agent_service_mapping",
        )
        return True

    def get_global_name_from_agent_service(self, agent_id: str, service_name: str) -> Optional[str]:
        return self._run_async(
            self.get_global_name_from_agent_service_async(agent_id, service_name),
            op_name="ServiceRegistry.get_global_name_from_agent_service",
        )

    async def get_global_name_from_agent_service_async(self, agent_id: str, service_name: str) -> Optional[str]:
        """
        依据 Agent 本地名解析全局服务名。
        优先使用关系表，缺失时回退到命名规则并校验实体存在，确保删除等场景不会因关系缺失而无法解析。
        """
        # 1) 关系表优先
        services = await self._relation_manager.get_agent_services(agent_id)
        for svc in services:
            if svc.get("service_original_name") == service_name or svc.get("service_global_name") == service_name:
                return svc.get("service_global_name")

        # 2) 已是全局名则直接返回
        if self._naming.AGENT_SEPARATOR in service_name:
            return service_name

        # 3) 回退：按命名规则推导，并确认实体存在（避免误生成）
        try:
            candidate = self._naming.generate_service_global_name(service_name, agent_id)
            exists = await self._cache_service_manager.get_service(candidate)
            if exists:
                self._logger.debug(
                    "[NAMING] Fallback global name resolved without relation: agent=%s, local=%s -> %s",
                    agent_id, service_name, candidate
                )
                return candidate
        except Exception as resolve_error:
            self._logger.debug(
                "[NAMING] Failed to resolve fallback global name: agent=%s, local=%s, error=%s",
                agent_id, service_name, resolve_error
            )

        return None

    def get_agent_service_from_global_name(self, global_name: str) -> Optional[Tuple[str, str]]:
        return self._run_async(
            self.get_agent_service_from_global_name_async(global_name),
            op_name="ServiceRegistry.get_agent_service_from_global_name",
        )

    async def get_agent_service_from_global_name_async(self, global_name: str) -> Optional[Tuple[str, str]]:
        if not global_name:
            raise ValueError("Service global name cannot be empty")
        original_name, agent_id = self._naming.parse_service_global_name(global_name)
        services = await self._relation_manager.get_agent_services(agent_id)
        for svc in services:
            if svc.get("service_global_name") == global_name:
                return (agent_id, svc.get("service_original_name") or original_name)
        return None

    async def get_agent_services_async(self, agent_id: str) -> List[str]:
        """
        异步获取指定 Agent 的所有服务（返回全局服务名列表）
        """
        services = await self._relation_manager.get_agent_services(agent_id)
        return [svc.get("service_global_name") for svc in services if svc.get("service_global_name")]

    def get_agent_services(self, agent_id: str) -> List[str]:
        return self._run_async(
            self.get_agent_services_async(agent_id),
            op_name="ServiceRegistry.get_agent_services",
        )

    def is_agent_service(self, agent_id: str, service_name: str) -> bool:
        return self._naming.AGENT_SEPARATOR in service_name

    def remove_agent_service_mapping(self, agent_id: str, service_name: str) -> bool:
        """
        删除 Agent-Service 映射（同步接口）；若在事件循环中则异步调度。
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 无事件循环，直接运行异步方法
            return asyncio.run(self.remove_agent_service_mapping_async(agent_id, service_name))
        else:
            # 已有事件循环，调度异步任务立即返回
            loop.create_task(self.remove_agent_service_mapping_async(agent_id, service_name))
            return True

    async def remove_agent_service_mapping_async(self, agent_id: str, service_name: str) -> bool:
        """
        删除 Agent-Service 映射（异步版本，不做事件循环桥接）
        - 仅清理映射表，不触发关系/状态删除
        """
        try:
            global_name = await self._resolve_global_name_async(agent_id, service_name)
        except Exception:
            global_name = None

        # 清理关系层映射（如果需要）
        if global_name:
            try:
                await self._relation_manager.remove_agent_service(agent_id, global_name)
            except Exception:
                pass

        # 清理映射管理器缓存
        try:
            if self._service_manager and hasattr(self._service_manager, "remove_agent_service_mapping"):
                self._service_manager.remove_agent_service_mapping(agent_id, service_name)
        except Exception:
            pass

        return True

    def clear_agent_mappings(self, agent_id: str) -> bool:
        async def _clear():
            services = await self._relation_manager.get_agent_services(agent_id)
            for svc in services:
                global_name = svc.get("service_global_name")
                if global_name:
                    await self._relation_manager.remove_agent_service(agent_id, global_name)
            return True

        return self._run_async(_clear(), op_name="ServiceRegistry.clear_agent_mappings")

    def clear_all_mappings(self) -> bool:
        return self._disabled_interface("clear_all_mappings")

    def get_mapping_stats(self) -> Dict[str, Any]:
        services = self._run_async(
            self._cache_layer_manager.get_all_entities_async("services"),
            op_name="ServiceRegistry.get_mapping_stats",
        )
        return {
            "services_count": len(services),
            "clients": len(
                self._run_async(
                    self._cache_layer_manager.get_all_entities_async("clients"),
                    op_name="ServiceRegistry.get_mapping_stats.clients",
                )
            ),
        }

    # ========================================
    # 工具管理方法 (委托给ToolManager)
    # ========================================

    def get_tools_for_service(self, agent_id: str, service_name: str) -> List[str]:
        return self._run_async(
            self.get_tools_for_service_async(agent_id, service_name),
            op_name="ServiceRegistry.get_tools_for_service",
        )

    async def get_tools_for_service_async(self, agent_id: str, service_name: str) -> List[str]:
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            return []
        tool_relations = await self._relation_manager.get_service_tools(global_name)
        return [
            tool.get("tool_global_name")
            for tool in tool_relations
            if tool.get("tool_global_name")
        ]

    def get_tool_info(self, agent_id: str, tool_name: str) -> Optional[Dict[str, Any]]:
        return self._run_async(
            self.get_tool_info_async(agent_id, tool_name),
            op_name="ServiceRegistry.get_tool_info",
        )

    async def get_tool_info_async(self, agent_id: str, tool_name: str) -> Optional[Dict[str, Any]]:
        tool_entity = await self._cache_tool_manager.get_tool(tool_name)
        if tool_entity is None:
            return None
        entity_dict = tool_entity.to_dict() if hasattr(tool_entity, "to_dict") else tool_entity
        service_global_name = entity_dict.get("service_global_name")
        client_id = None
        if service_global_name:
            client_id = await self.get_service_client_id_async(agent_id, service_global_name)
        return {
            "name": entity_dict.get("tool_global_name"),
            "display_name": entity_dict.get("tool_original_name"),
            "tool_original_name": entity_dict.get("tool_original_name"),
            "description": entity_dict.get("description", ""),
            "service_name": entity_dict.get("service_original_name"),
            "service_global_name": service_global_name,
            "inputSchema": entity_dict.get("input_schema", {}),
            "client_id": client_id,
        }

    def add_tool_to_service(self, service_name: str, tool_name: str, tool_config: Dict[str, Any]) -> bool:
        return self._tool_manager.add_tool_to_service(service_name, tool_name, tool_config)

    async def add_tool_to_service_async(self, service_name: str, tool_name: str, tool_config: Dict[str, Any]) -> bool:
        return await self._tool_manager.add_tool_to_service_async(service_name, tool_name, tool_config)

    def remove_tool_from_service(self, service_name: str, tool_name: str) -> bool:
        return self._tool_manager.remove_tool_from_service(service_name, tool_name)

    async def remove_tool_from_service_async(self, service_name: str, tool_name: str) -> bool:
        return await self._tool_manager.remove_tool_from_service_async(service_name, tool_name)

    def list_all_tools(self) -> List[str]:
        return self._tool_manager.list_all_tools()

    def search_tools(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self._tool_manager.search_tools(query, filters)

    def get_tools_stats(self) -> Dict[str, Any]:
        return self._tool_manager.get_tools_stats()

    def validate_tool_definition(self, tool_config: Dict[str, Any]) -> bool:
        return self._tool_manager.validate_tool_definition(tool_config)

    def get_tool_names_for_service(self, service_name: str) -> List[str]:
        return self._tool_manager.get_tool_names_for_service(service_name)

    def update_tool_info(self, service_name: str, tool_name: str, updates: Dict[str, Any]) -> bool:
        return self._tool_manager.update_tool_info(service_name, tool_name, updates)

    def clear_service_tools(self, service_name: str) -> bool:
        return self._tool_manager.clear_service_tools(service_name)

    def clear_service_tools_only(self, agent_id: str, service_name: str):
        """
        只清理服务的工具缓存，保留Agent-Client映射关系

        这是优雅修复方案的核心方法：
        - 清理工具缓存和工具-会话映射
        - 保留Agent-Client映射
        - 保留Client配置
        - 保留Service-Client映射

        Args:
            agent_id: Agent ID
            service_name: 服务名称
        """
        try:
            self._logger.debug(
                f"[REGISTRY.CLEAR_TOOLS_ONLY] begin agent={agent_id} service={service_name}")

            # 获取现有会话
            existing_session = self._session_manager.get_session(agent_id, service_name)
            if not existing_session:
                self._logger.debug(f"[CLEAR_TOOLS] no_session service={service_name} skip=True")
                return

            # 只清理工具相关的缓存
            tools_to_remove = []
            all_tool_names = self._session_manager.get_all_tool_names(agent_id)
            for tool_name in all_tool_names:
                tool_session = self._session_manager.get_session_for_tool(agent_id, tool_name)
                if tool_session is existing_session:
                    tools_to_remove.append(tool_name)

            for tool_name in tools_to_remove:
                # 清理工具-会话映射
                self._session_manager.remove_tool_session_mapping(agent_id, tool_name)

            # 清理会话（会被新会话替换）
            self._session_manager.clear_session(agent_id, service_name)

            self._logger.debug(
                f"[CLEAR_TOOLS] cleared_tools service={service_name} count={len(tools_to_remove)} keep_mappings=True")

        except Exception as e:
            self._logger.error(f"[CLEAR_TOOLS] Failed to clear tools {agent_id}:{service_name}: {e}")
            raise

    def has_tools(self, service_name: str) -> bool:
        return self._tool_manager.has_tools(service_name)

    # ========================================
    # 状态管理方法 (委托给StateManager)
    # 注意：方法签名与原始架构保持一致 (agent_id, service_name)
    # ========================================

    def get_service_state(self, agent_id: str, service_name: str) -> Optional[Any]:
        """
        获取服务状态

        Args:
            agent_id: Agent ID
            service_name: 服务名称

        Returns:
            服务状态
        """
        return self._run_async(
            self.get_service_state_async(agent_id, service_name),
            op_name="ServiceRegistry.get_service_state",
        )

    def set_service_state(self, agent_id: str, service_name: str, state: Any) -> bool:
        """
        设置服务状态

        Args:
            agent_id: Agent ID
            service_name: 服务名称
            state: 服务状态

        Returns:
            是否成功
        """
        return self._run_async(
            self.set_service_state_async(agent_id, service_name, state),
            op_name="ServiceRegistry.set_service_state",
        )

    async def set_service_state_async(self, agent_id: str, service_name: str, state: Any) -> bool:
        """
        异步设置服务状态

        Args:
            agent_id: Agent ID
            service_name: 服务名称
            state: 服务状态

        Returns:
            是否成功
        """
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            raise RuntimeError(f"{ERROR_PREFIX} service not found for {agent_id}:{service_name}")

        status = await self._cache_state_manager.get_service_status(global_name)
        tools_status = []
        if status and getattr(status, "tools", None):
            tools_status = [tool.to_dict() for tool in status.tools]

        health_status = state.value if hasattr(state, "value") else str(state)
        await self._cache_state_manager.update_service_status(
            service_global_name=global_name,
            health_status=health_status,
            tools_status=tools_status,
        )
        self._cache_state_snapshot(agent_id, service_name, state)
        return True

    def get_all_service_states(self, agent_id: str) -> Dict[str, Any]:
        """
        获取指定 Agent 的所有服务状态

        Args:
            agent_id: Agent ID

        Returns:
            服务状态字典
        """
        return self._run_async(
            self.get_all_service_states_async(agent_id),
            op_name="ServiceRegistry.get_all_service_states",
        )

    async def get_all_service_states_async(self, agent_id: str) -> Dict[str, Any]:
        services = await self._relation_manager.get_agent_services(agent_id)
        result: Dict[str, Any] = {}
        for svc in services:
            global_name = svc.get("service_global_name")
            original_name = svc.get("service_original_name")
            if not global_name:
                continue
            status = await self._cache_state_manager.get_service_status(global_name)
            if status is None:
                continue
            result[original_name or global_name] = self._map_health_status(status.health_status)
        return result

    def get_services_by_state(self, agent_id: str, states: List[Any]) -> List[str]:
        """
        按状态筛选服务

        Args:
            agent_id: Agent ID
            states: 状态列表

        Returns:
            服务名称列表
        """
        return self._run_async(
            self.get_services_by_state_async(agent_id, states),
            op_name="ServiceRegistry.get_services_by_state",
        )

    async def get_services_by_state_async(self, agent_id: str, states: List[Any]) -> List[str]:
        target_states = {self._map_health_status(state).value if not isinstance(state, str) else state for state in states}
        services = await self._relation_manager.get_agent_services(agent_id)
        matched: List[str] = []
        for svc in services:
            global_name = svc.get("service_global_name")
            original_name = svc.get("service_original_name")
            if not global_name:
                continue
            status = await self._cache_state_manager.get_service_status(global_name)
            if status and status.health_status in target_states:
                matched.append(original_name or global_name)
        return matched

    def clear_service_state(self, agent_id: str, service_name: str) -> bool:
        """
        清除服务状态

        Args:
            agent_id: Agent ID
            service_name: 服务名称

        Returns:
            是否成功
        """
        return self._run_async(
            self.delete_service_state_async(agent_id, service_name),
            op_name="ServiceRegistry.clear_service_state",
        )

    # [已删除] get_service_metadata 同步方法（重复定义）
    # 根据 "pykv 唯一真相数据源" 原则，请使用 get_service_metadata_async 异步方法

    def set_service_metadata(self, agent_id: str, service_name: str, metadata: Any) -> bool:
        """
        设置服务元数据

        Args:
            agent_id: Agent ID
            service_name: 服务名称
            metadata: 服务元数据

        Returns:
            是否成功
        """
        return self._run_async(
            self.set_service_metadata_async(agent_id, service_name, metadata),
            op_name="ServiceRegistry.set_service_metadata",
        )

    async def set_service_metadata_async(self, agent_id: str, service_name: str, metadata: Any) -> bool:
        """
        异步设置服务元数据

        Args:
            agent_id: Agent ID
            service_name: 服务名称
            metadata: 服务元数据

        Returns:
            是否成功
        """
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            raise RuntimeError(f"{ERROR_PREFIX} service not found for {agent_id}:{service_name}")

        if metadata is None:
            return False
        if isinstance(metadata, ServiceStateMetadata):
            metadata_obj = metadata
            metadata_dict = metadata.model_dump(mode="json")
        elif hasattr(metadata, "model_dump"):
            metadata_obj = ServiceStateMetadata.model_validate(metadata.model_dump())
            metadata_dict = metadata.model_dump(mode="json")
        elif isinstance(metadata, dict):
            metadata_obj = ServiceStateMetadata.model_validate(metadata)
            metadata_dict = metadata_obj.model_dump(mode="json")
        else:
            raise ValueError("metadata must be a dictionary or ServiceStateMetadata")

        await self._cache_layer_manager.put_state("service_metadata", global_name, metadata_dict)
        self._cache_metadata_snapshot(agent_id, service_name, metadata_obj)
        return True

    def get_service_status(self, agent_id: str, service_name: str) -> Optional[str]:
        """
        获取服务状态字符串。

        Args:
            agent_id: Agent ID
            service_name: 服务名称

        Returns:
            服务状态字符串
        """
        state = self.get_service_state(agent_id, service_name)
        return state.value if hasattr(state, "value") else state

    def update_service_metadata(self, service_name: str, updates: Dict[str, Any], agent_id: Optional[str] = None) -> bool:
        self._disabled_interface("update_service_metadata")
        return False

    def get_service_metadata_timestamp(self, service_name: str, key: str, agent_id: Optional[str] = None) -> Optional[datetime]:
        self._disabled_interface("get_service_metadata_timestamp")

    def clear_service_metadata(self, service_name: str, keys: Optional[List[str]] = None, agent_id: Optional[str] = None) -> bool:
        self._disabled_interface("clear_service_metadata")
        return False

    def get_all_service_metadata(self, service_name: Optional[str] = None, agent_id: Optional[str] = None) -> Dict[str, Any]:
        self._disabled_interface("get_all_service_metadata")
        return {}

    def cleanup_old_metadata(self, service_name: Optional[str] = None, agent_id: Optional[str] = None,
                           older_than: Optional[datetime] = None) -> int:
        self._disabled_interface("cleanup_old_metadata")
        return 0

    def get_metadata_stats(self) -> Dict[str, Any]:
        self._disabled_interface("get_metadata_stats")
        return {}

    def has_metadata(self, service_name: str, agent_id: Optional[str] = None) -> bool:
        self._disabled_interface("has_metadata")
        return False

    # ========================================
    # 缓存管理方法 (委托给CacheManager)
    # ========================================

    def get_service_names(self) -> List[str]:
        self._disabled_interface("get_service_names")

    async def get_service_names_async(self) -> List[str]:
        self._disabled_interface("get_service_names_async")

    def get_agents_for_service(self, service_name: str) -> List[str]:
        self._disabled_interface("get_agents_for_service")

    async def get_agents_for_service_async(self, service_name: str) -> List[str]:
        self._disabled_interface("get_agents_for_service_async")

    def clear_cache(self) -> bool:
        self._disabled_interface("clear_cache")

    def get_stats(self) -> Dict[str, Any]:
        self._disabled_interface("get_stats")

    # ========================================
    # 持久化管理方法 (委托给PersistenceManager)
    # ========================================

    def save_to_file(self, filepath: str) -> bool:
        self._disabled_interface("save_to_file")

    def load_from_file(self, filepath: str) -> bool:
        self._disabled_interface("load_from_file")

    async def save_services_async(self, filepath: str) -> bool:
        self._disabled_interface("save_services_async")

    async def load_services_async(self, filepath: str) -> bool:
        self._disabled_interface("load_services_async")

    async def save_tools_async(self, filepath: str) -> bool:
        self._disabled_interface("save_tools_async")

    async def load_tools_async(self, filepath: str) -> bool:
        self._disabled_interface("load_tools_async")

    def get_last_save_time(self) -> Optional[datetime]:
        self._disabled_interface("get_last_save_time")

    def get_file_info(self) -> Dict[str, Any]:
        self._disabled_interface("get_file_info")

    def set_unified_config(self, unified_config: Any) -> None:
        """
        设置统一配置管理器（用于 JSON 配置持久化）

        Args:
            unified_config: UnifiedConfigManager 实例
        """
        if unified_config is None:
            raise ValueError("unified_config cannot be empty")
        self._unified_config = unified_config

    async def load_services_from_json_async(self) -> Dict[str, Any]:
        """
        从 mcp.json 读取服务配置并恢复服务实体

        Returns:
            加载结果统计信息
        """
        self._disabled_interface("load_services_from_json_async")

    async def delete_service_state_async(self, agent_id: str, service_name: str) -> bool:
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            return False
        await self._cache_layer_manager.delete_state("service_status", global_name)
        self._cache_state_snapshot(agent_id, service_name, None)
        return True

    async def delete_service_metadata_async(self, agent_id: str, service_name: str) -> bool:
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            return False
        await self._cache_layer_manager.delete_state("service_metadata", global_name)
        self._cache_metadata_snapshot(agent_id, service_name, None)
        return True

    async def get_service_state_async(self, agent_id: str, service_name: str) -> Optional[Any]:
        """
        异步获取服务状态

        使用缓存层状态管理器（cache/state_manager.py）获取状态。
        方法签名：get_service_status(service_global_name)

        Args:
            agent_id: Agent ID
            service_name: 服务名称

        Returns:
            服务状态或None
        """
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            return None
        status = await self._cache_state_manager.get_service_status(global_name)
        if status is None:
            return None
        health_status = status.health_status if hasattr(status, "health_status") else status.get("health_status")
        return self._map_health_status(health_status)

    async def get_service_metadata_async(self, agent_id: str, service_name: str) -> Optional[Any]:
        """
        异步获取服务元数据

        遵循 "pykv 唯一真相数据源" 原则，从 pykv 读取元数据。

        Args:
            agent_id: Agent ID
            service_name: 服务名称

        Returns:
            服务元数据或None
        """
        global_name = await self._resolve_global_name_async(agent_id, service_name)
        if not global_name:
            return None
        metadata = await self._cache_layer_manager.get_state("service_metadata", global_name)
        if not metadata:
            self._cache_metadata_snapshot(agent_id, service_name, None)
            return None
        metadata_obj = ServiceStateMetadata.model_validate(metadata)
        self._cache_metadata_snapshot(agent_id, service_name, metadata_obj)
        return metadata_obj

    def get_service_status(self, agent_id: str, service_name: str) -> Optional[str]:
        """
        获取服务状态字符串。

        Args:
            agent_id: Agent ID
            service_name: 服务名称

        Returns:
            服务状态或None
        """
        state = self.get_service_state(agent_id, service_name)
        return state.value if hasattr(state, "value") else state

    @property
    def kv_store(self):
        """获取KV存储实例（已禁用属性）"""
        raise_disabled_interface_error("ServiceRegistry.kv_store", "Direct kv_store access is disabled.")

    @property
    def naming(self):
        """获取命名服务实例（已禁用属性）"""
        raise_disabled_interface_error("ServiceRegistry.naming", "Direct naming access is disabled.")

    # 新增：支持 unified_sync_manager 的接口
    async def get_all_entities_for_sync(self, entity_type: str) -> Dict[str, Dict[str, Any]]:
        """
        获取所有实体用于同步

        Args:
            entity_type: 实体类型 (如 "services")

        Returns:
            Dict[str, Dict[str, Any]]: 实体数据字典
        """
        return await self._cache_layer_manager.get_all_entities_async(entity_type)

    async def get_all_agent_ids_async(self) -> List[str]:
        """
        异步获取所有 Agent ID 列表。
        """
        agent_ids: Set[str] = set()

        # 1) 直接从 Agent 实体表获取（即使 Agent 暂无服务也能返回）
        agents = await self._cache_layer_manager.get_all_entities_async("agents")
        if isinstance(agents, dict):
            agent_ids.update(agents.keys())

        # 2) 兼容旧数据：从服务实体中的 source_agent 提取
        services = await self._cache_layer_manager.get_all_entities_async("services")
        if isinstance(services, dict):
            service_agents = {
                data.get("source_agent")
                for data in services.values()
                if isinstance(data, dict) and data.get("source_agent")
            }
            agent_ids.update(service_agents)

        # 3) 确保全局 Agent 始终存在
        agent_ids.add(self._naming.GLOBAL_AGENT_STORE)

        # 过滤 None
        agent_ids = {a for a in agent_ids if a}
        return list(agent_ids)

    def get_all_agent_ids(self) -> List[str]:
        """
        获取所有 Agent ID 列表（同步包装）
        """
        return self._run_async(
            self.get_all_agent_ids_async(),
            op_name="ServiceRegistry.get_all_agent_ids",
        )

    def get_all_service_names(self, agent_id: str) -> List[str]:
        """
        获取指定 Agent 的所有服务名称

        Args:
            agent_id: Agent ID

        Returns:
            List[str]: 服务名称列表
        """
        return self._run_async(
            self.get_services_for_agent_async(agent_id),
            op_name="ServiceRegistry.get_all_service_names",
        )

    async def get_all_service_names_async(self, agent_id: str) -> List[str]:
        """
        异步获取指定 Agent 的所有服务名称
        
        [pykv 唯一真相源] 从 pykv 关系层读取，不从内存缓存读取。
        
        Args:
            agent_id: Agent ID

        Returns:
            List[str]: 服务名称列表
        """
        return await self.get_services_for_agent_async(agent_id)
