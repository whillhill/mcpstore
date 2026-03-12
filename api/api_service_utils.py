"""
MCPStore API Service Utilities
公共服务操作工具模块，用于消除重复代码
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from mcpstore import MCPStore
from .api_exceptions import (
    MCPStoreException, ErrorCode, error_monitor
)

logger = logging.getLogger(__name__)


class ServiceOperationHelper:
    """服务操作辅助类，提供通用的服务操作方法（分片文件已废弃）"""

    # 分片文件已废弃：保留其他通用方法（如 get_service_details 等）

    

    
    @staticmethod
    async def get_service_details(
        store: MCPStore,
        service_name: str,
        context_type: str = "store",
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取服务详细信息的通用方法
        
        Args:
            store: MCPStore 实例
            service_name: 服务名称
            context_type: 上下文类型 ("store" 或 "agent")
            agent_id: Agent ID（仅在 context_type 为 "agent" 时需要）
        """
        try:
            # 统一使用 pykv 作为唯一数据源
            if context_type == "store":
                target_agent_id = store.orchestrator.client_manager.global_agent_store_id
            elif context_type == "agent":
                if not agent_id:
                    raise ValueError("agent_id is required for agent context")
                target_agent_id = agent_id
            else:
                raise ValueError(f"Invalid context_type: {context_type}")

            complete_info = await store.registry.get_complete_service_info_async(target_agent_id, service_name)
            if not complete_info:
                raise MCPStoreException(
                    message=f"Service '{service_name}' not found",
                    error_code=ErrorCode.SERVICE_NOT_FOUND,
                    details={"service_name": service_name, "context_type": context_type}
                )

            config = complete_info.get("config", {}) or {}
            state = complete_info.get("state")
            status_str = state.value if hasattr(state, "value") else (str(state) if state else "unknown")

            raw_tools = complete_info.get("tools") or []
            tools_info = []
            for tool in raw_tools:
                if hasattr(tool, "model_dump"):
                    tools_info.append(tool.model_dump())
                elif hasattr(tool, "dict"):
                    tools_info.append(tool.dict())
                elif isinstance(tool, dict):
                    tools_info.append(tool)
                else:
                    tools_info.append({"name": str(tool)})

            service_details = {
                "name": complete_info.get("service_original_name") or service_name,
                "status": status_str,
                "transport": config.get("transport", "unknown"),
                "client_id": complete_info.get("client_id"),
                "url": config.get("url"),
                "command": config.get("command"),
                "args": config.get("args"),
                "env": config.get("env"),
                "tool_count": len(tools_info),
                "is_active": status_str not in ["disconnected", "circuit_open"],
                "config": config,
                "tools": tools_info,
            }

            metadata = complete_info.get("state_metadata")
            if metadata:
                service_details["lifecycle"] = {
                    "consecutive_successes": getattr(metadata, "consecutive_successes", 0),
                    "consecutive_failures": getattr(metadata, "consecutive_failures", 0),
                    "last_ping_time": getattr(metadata, "last_ping_time", None).isoformat()
                    if getattr(metadata, "last_ping_time", None)
                    else None,
                    "error_message": getattr(metadata, "error_message", None),
                    "reconnect_attempts": getattr(metadata, "reconnect_attempts", 0),
                    "state_entered_time": getattr(metadata, "state_entered_time", None).isoformat()
                    if getattr(metadata, "state_entered_time", None)
                    else None,
                }

            return service_details
            
        except Exception as e:
            error_monitor.record_error(e, {
                "operation": "get_service_details",
                "service_name": service_name,
                "context_type": context_type,
                "agent_id": agent_id
            })
            raise
    
    @staticmethod
    async def get_config_with_timeout(
        context,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        带超时的配置获取方法
        
        Args:
            context: 上下文对象
            timeout: 超时时间（秒）
        """
        try:
            # 使用 asyncio.wait_for 实现超时控制
            return await asyncio.wait_for(
                context.bridge_execute(context.get_config_async()),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise MCPStoreException(
                message="Configuration retrieval timed out",
                error_code=ErrorCode.CONFIG_ERROR,
                details={"timeout": timeout, "operation": "get_config_async"}
            )
        except Exception as e:
            raise MCPStoreException(
                message=f"Failed to retrieve configuration: {str(e)}",
                error_code=ErrorCode.CONFIG_ERROR,
                details={"error": str(e)}
            )
    
    @staticmethod
    async def update_config_with_timeout(
        context,
        config_data: Dict[str, Any],
        timeout: float = 30.0
    ) -> bool:
        """
        带超时的配置更新方法
        
        Args:
            context: 上下文对象
            config_data: 配置数据
            timeout: 超时时间（秒）
        """
        try:
            # 使用 asyncio.wait_for 实现超时控制
            return await asyncio.wait_for(
                context.bridge_execute(context.update_config_async(config_data)),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise MCPStoreException(
                message="Configuration update timed out",
                error_code=ErrorCode.CONFIG_UPDATE_FAILED,
                details={"timeout": timeout, "operation": "update_config_async"}
            )
        except Exception as e:
            raise MCPStoreException(
                message=f"Failed to update configuration: {str(e)}",
                error_code=ErrorCode.CONFIG_UPDATE_FAILED,
                details={"error": str(e)}
            )


