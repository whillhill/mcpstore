"""
MCPStore API Decorators and Utility Functions
Contains exception handling, validation helpers, and lightweight wrappers.
（已移除性能/监控相关逻辑）
"""

import logging
from functools import wraps
from typing import Optional, List

from fastapi import HTTPException
from pydantic import ValidationError

from mcpstore import APIResponse
# 导入统一的异常处理系统
from .api_exceptions import (
    MCPStoreException, ValidationException, ErrorCode,
    error_monitor
)

logger = logging.getLogger(__name__)


# === Decorator functions ===

def handle_exceptions(func):
    """统一的异常处理装饰器（使用增强版异常处理系统）"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            # If result is already APIResponse, return directly
            if isinstance(result, APIResponse):
                return result
            # Otherwise wrap as APIResponse
            return APIResponse(success=True, data=result)
        except MCPStoreException:
            # MCPStore 异常已经包含足够信息，直接抛出
            raise
        except HTTPException:
            # HTTPException 应该直接传递，不要包装
            raise
        except ValidationError as e:
            # Pydantic 验证错误
            raise ValidationException(
                message=f"Data validation error: {str(e)}",
                details={"validation_errors": e.errors()}
            )
        except ValueError as e:
            # 值错误
            raise ValidationException(message=str(e))
        except KeyError as e:
            # 键错误
            raise ValidationException(
                message=f"Missing required field: {str(e)}",
                field=str(e)
            )
        except Exception as e:
            # 记录未处理的异常
            error_monitor.record_error(e, {"function": func.__name__})
            logger.error(f"Unhandled exception in {func.__name__}: {str(e)}", exc_info=True)
            raise MCPStoreException(
                message=f"Internal server error in {func.__name__}",
                error_code=ErrorCode.INTERNAL_ERROR,
                details={
                    "function": func.__name__,
                    "type": type(e).__name__
                }
            )
    return wrapper

def monitor_api_performance(func):
    """API performance monitoring decorator"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)

    return wrapper

# === 验证函数 ===

def validate_agent_id(agent_id: str):
    """验证 agent_id"""
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")
    if not isinstance(agent_id, str):
        raise HTTPException(status_code=400, detail="Invalid agent_id format")

    # 检查agent_id格式：只允许字母、数字、下划线、连字符
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', agent_id):
        raise HTTPException(status_code=400, detail="Invalid agent_id format: only letters, numbers, underscore and hyphen allowed")

    # 检查长度
    if len(agent_id) > 100:
        raise HTTPException(status_code=400, detail="agent_id too long (max 100 characters)")

def validate_service_names(service_names: Optional[List[str]]):
    """验证 service_names"""
    if service_names and not isinstance(service_names, list):
        raise HTTPException(status_code=400, detail="Invalid service_names format")
    if service_names and not all(isinstance(name, str) for name in service_names):
        raise HTTPException(status_code=400, detail="All service names must be strings")
