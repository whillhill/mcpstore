"""
MCPStore Common Response Models

Unified response model import center.
"""

# ==================== Core Response Models ====================

# Response builders

# Response decorators

# Error code enumeration

# ==================== Compatibility exports (some older models) ====================
from typing import Optional, Any, List, Dict, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar('T')

class ListResponse(BaseModel, Generic[T]):
    """List response model"""
    success: bool = Field(..., description="Whether operation was successful")
    message: Optional[str] = Field(None, description="Response message")
    items: List[T] = Field(..., description="Data item list")
    total: int = Field(..., description="Total count")

class DataResponse(BaseModel, Generic[T]):
    """Data response model"""
    success: bool = Field(..., description="Whether operation was successful")
    message: Optional[str] = Field(None, description="Response message")
    data: T = Field(..., description="Response data")

class RegistrationResponse(BaseModel):
    """Service registration response"""
    success: bool = Field(..., description="Whether operation was successful")
    message: str = Field(..., description="Response message")
    service_name: Optional[str] = Field(None, description="Registered service name")

class ExecutionResponse(BaseModel):
    """Tool execution response"""
    success: bool = Field(..., description="Whether operation was successful")
    message: Optional[str] = Field(None, description="Response message")
    result: Optional[Any] = Field(None, description="Execution result")
    error: Optional[str] = Field(None, description="Error message")

class ConfigResponse(BaseModel):
    """Configuration operation response"""
    success: bool = Field(..., description="Whether operation was successful")
    message: str = Field(..., description="Response message")
    config: Optional[Dict[str, Any]] = Field(None, description="Configuration data")

class HealthResponse(BaseModel):
    """Health check response"""
    success: bool = Field(..., description="Whether operation was successful")
    status: str = Field(..., description="Health status")
    services: Optional[Dict[str, str]] = Field(None, description="Service status mapping")
