"""
Data Space Management Module
Handles data space related functionality for MCPStore
"""

import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


from pathlib import Path
import json

class DataSpaceManagerMixin:
    """Data Space Management Mixin"""

    def get_data_space_info(self) -> Optional[Dict[str, Any]]:
        """
        Get data space information

        Returns:
            Dict: Data space information, returns None if data space is not used
        """
        if self._data_space_manager:
            return self._data_space_manager.get_workspace_info()
        return None

    def get_workspace_dir(self) -> Optional[str]:
        """
        Get workspace directory path

        Returns:
            str: Workspace directory path, returns None if data space is not used
        """
        if self._data_space_manager:
            return str(self._data_space_manager.workspace_dir)
        return None

    def is_using_data_space(self) -> bool:
        """
        Check if data space is being used

        Returns:
            bool: Whether data space is being used
        """
        return self._data_space_manager is not None

    async def _add_service(self, service_names: List[str], agent_id: Optional[str]) -> bool:
        """Internal method: batch add services, store level supports full registration, agent level supports specified service registration"""
        # store level
        if agent_id is None:
            if not service_names:
                # Full registration: use unified synchronization mechanism
                if hasattr(self.orchestrator, 'sync_manager') and self.orchestrator.sync_manager:
                    sync_results = await self.orchestrator.sync_manager.sync_global_agent_store_from_mcp_json()
                    return bool(sync_results.get("added") or sync_results.get("updated"))
                else:
                    logger.warning("Unified sync manager not available, skipping full registration")
                    return False
            else:
                # Read service configuration from cache and follow unified cache-first process
                try:
                    mcp_config = {"mcpServers": {}}
                    cache_agent_id = self.client_manager.global_agent_store_id
                    missing = []
                    for name in service_names:
                        svc_cfg = await self.registry.get_service_config_from_cache_async(cache_agent_id, name)
                        if not svc_cfg:
                            missing.append(name)
                        else:
                            mcp_config["mcpServers"][name] = svc_cfg
                    if missing:
                        logger.error(f"The following services were not found in cache configuration: {missing}")
                        return False
                    await self.for_store().add_service_async(mcp_config)
                    return True
                except Exception as e:
                    logger.error(f"Failed to add service via cache: {e}")
                    return False
        # agent级别
        else:
            if service_names:
                try:
                    mcp_config = {"mcpServers": {}}
                    cache_agent_id = agent_id
                    missing = []
                    for name in service_names:
                        svc_cfg = await self.registry.get_service_config_from_cache_async(cache_agent_id, name)
                        if not svc_cfg:
                            missing.append(name)
                        else:
                            mcp_config["mcpServers"][name] = svc_cfg
                    if missing:
                        logger.error(f"Agent({agent_id}) the following services were not found in cache: {missing}")
                        return False
                    await self.for_agent(agent_id).add_service_async(mcp_config)
                    return True
                except Exception as e:
                    logger.error(f"Agent failed to add service via cache: {e}")
                    return False
            else:
                logger.warning(f"Agent {agent_id} level does not support full registration")
                return False

    async def add_service(self, service_names: Optional[List[str]] = None, agent_id: Optional[str] = None, **kwargs) -> bool:
        if service_names is None:
            service_names = kwargs.get("service_names")
        if not isinstance(service_names, list):
            return False
        return await self._add_service(service_names, agent_id)


class DataSpaceManager:
    """最小实现：用于数据空间初始化与信息查询（单一数据源模式）"""

    def __init__(self, mcp_json_path: str):
        self.mcp_json_path = Path(mcp_json_path).resolve()
        self.workspace_dir = self.mcp_json_path.parent
        logger.info(f"DataSpaceManager initialized for workspace: {self.workspace_dir}")

    def initialize_workspace(self) -> bool:
        """确保工作目录存在，并保证 mcp.json 存在且格式基本正确"""
        try:
            # 创建目录
            self.workspace_dir.mkdir(parents=True, exist_ok=True)

            # 如果没有 mcp.json，创建基础结构
            if not self.mcp_json_path.exists():
                self.mcp_json_path.write_text(json.dumps({"mcpServers": {}}, indent=2, ensure_ascii=False), encoding="utf-8")
                logger.info(f"Created new MCP JSON file: {self.mcp_json_path}")
            else:
                # 简单结构校验：必须是 dict 且包含 mcpServers 字段
                try:
                    data = json.loads(self.mcp_json_path.read_text(encoding="utf-8"))
                    if not isinstance(data, dict) or "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
                        # 备份并重建
                        backup = self.mcp_json_path.with_suffix(self.mcp_json_path.suffix + ".bak")
                        backup.write_text(self.mcp_json_path.read_text(encoding="utf-8"), encoding="utf-8")
                        self.mcp_json_path.write_text(json.dumps({"mcpServers": {}}, indent=2, ensure_ascii=False), encoding="utf-8")
                        logger.warning(f"Invalid mcp.json structure fixed, backup saved: {backup}")
                except Exception as e:
                    # 读取失败则直接重建
                    backup = self.mcp_json_path.with_suffix(self.mcp_json_path.suffix + ".bak")
                    try:
                        backup.write_text(self.mcp_json_path.read_text(encoding="utf-8"), encoding="utf-8")
                    except Exception:
                        pass
                    self.mcp_json_path.write_text(json.dumps({"mcpServers": {}}, indent=2, ensure_ascii=False), encoding="utf-8")
                    logger.warning(f"Recreated invalid mcp.json, reason: {e}")

            return True
        except Exception as e:
            logger.error(f"Failed to initialize workspace: {e}")
            return False

    def get_workspace_info(self) -> Dict[str, Any]:
        """返回工作区信息"""
        return {
            "workspace_dir": str(self.workspace_dir),
            "mcp_json_path": str(self.mcp_json_path),
            "mcp_json_exists": self.mcp_json_path.exists(),
        }

    def get_file_path(self, relative_path: str) -> Path:
        """
        获取工作空间内文件的完整路径

        Args:
            relative_path: 相对于工作空间的路径

        Returns:
            Path: 完整的文件路径
        """
        return self.workspace_dir / relative_path
