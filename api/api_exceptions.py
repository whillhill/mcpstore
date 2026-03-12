"""
MCPStore API Unified Exception Handling
Provides comprehensive exception handling and error response formatting
"""

import logging
import traceback
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Union, List

from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

# Import unified exception system
from mcpstore import MCPStoreException, ErrorCode, ValidationException
# Import new response models
from mcpstore import APIResponse, ResponseBuilder

# Setup logger
logger = logging.getLogger(__name__)

# === Exception classes are now imported from mcpstore.core.exceptions ===
# No need to redefine them here

# === Error response formatting (using new architecture) ===

def format_error_response(
    error: Union[MCPStoreException, Exception],
    include_stack_trace: bool = False
) -> APIResponse:
    """Format error response (using new APIResponse model)"""

    if isinstance(error, MCPStoreException):
        # Build details, may include stack trace
        details = {**error.details, "error_id": error.error_id}
        if include_stack_trace and error.stack_trace:
            details["stack_trace"] = error.stack_trace

        return ResponseBuilder.error(
            code=error.error_code,
            message=error.message,
            field=error.field,
            details=details
        )
    else:
        # Standard exception handling
        details = {
            "error_id": str(uuid.uuid4())[:8],
            "error_type": type(error).__name__
        }
        if include_stack_trace:
            details["stack_trace"] = traceback.format_exc()

        return ResponseBuilder.error(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(error) or "Internal server error",
            details=details
        )

# === Exception Handlers ===

async def mcpstore_exception_handler(request: Request, exc: MCPStoreException):
    """MCPStore exception handler (using new response format)"""
    logger.error(
        f"MCPStore error [{exc.error_id}]: {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "error_id": exc.error_id,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    response = format_error_response(exc, include_stack_trace=False)
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(exclude_none=True)
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Request validation exception handler (using new response format)"""
    # Convert to ErrorDetail list
    error_details = []
    for error in exc.errors():
        field = " -> ".join([str(loc) for loc in error["loc"] if loc != "body"])
        error_details.append({
            "code": ErrorCode.INVALID_PARAMETER.value,
            "message": error["msg"],
            "field": field,
            "details": {"type": error["type"]}
        })
    
    logger.warning(
        f"Validation error: {len(error_details)} errors",
        extra={
            "errors": error_details,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    response = ResponseBuilder.errors(
        message=f"Request validation failed ({len(error_details)} errors)",
        errors=error_details
    )
    
    return JSONResponse(
        status_code=422,
        content=response.model_dump(exclude_none=True)
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP exception handler (using new response format)"""
    logger.warning(
        f"HTTP error: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method
        }
    )

    # Map HTTP status codes to error codes
    error_code_map = {
        404: ErrorCode.SERVICE_NOT_FOUND,
        401: ErrorCode.AUTHENTICATION_REQUIRED,
        403: ErrorCode.AUTHORIZATION_FAILED,
        400: ErrorCode.INVALID_REQUEST,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
    }
    error_code = error_code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    
    response = ResponseBuilder.error(
        code=error_code,
        message=exc.detail or "HTTP error",
        details={"http_status": exc.status_code}
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(exclude_none=True)
    )

async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler (using new response format)"""
    error_id = str(uuid.uuid4())[:8]
    logger.error(
        f"Unhandled exception [{error_id}]: {str(exc)}",
        extra={
            "error_id": error_id,
            "path": request.url.path,
            "method": request.method,
            "stack_trace": traceback.format_exc()
        },
        exc_info=True
    )
    
    response = ResponseBuilder.error(
        code=ErrorCode.INTERNAL_ERROR,
        message="Internal server error",
        details={
            "error_id": error_id,
            "error_type": type(exc).__name__
        }
    )
    
    return JSONResponse(
        status_code=500,
        content=response.model_dump(exclude_none=True)
    )

# === Exception Handling Decorators ===

def handle_api_exceptions(func):
    """API exception handling decorator (enhanced version)"""
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            
            # If result is already APIResponse, return directly
            if isinstance(result, APIResponse):
                return result

            # Otherwise wrap as success response
            return ResponseBuilder.success(
                message="Operation completed successfully",
                data=result if isinstance(result, (dict, list)) else {"result": result}
            )

        except MCPStoreException:
            # MCPStore exceptions already contain sufficient information, raise directly
            raise

        except HTTPException:
            # HTTPException should be passed through directly, not wrapped
            raise

        except RequestValidationError:
            # FastAPI validation errors, let global handler process
            raise

        except ValidationError as e:
            # Pydantic validation error
            raise ValidationException(
                message=f"Data validation error: {str(e)}",
                details={"validation_errors": e.errors()}
            )

        except ValueError as e:
            # Value error
            raise ValidationException(message=str(e))

        except KeyError as e:
            # Key error
            raise ValidationException(
                message=f"Missing required field: {str(e)}",
                field=str(e)
            )

        except AttributeError as e:
            # Attribute error
            raise MCPStoreException(
                message=f"Attribute error: {str(e)}",
                error_code=ErrorCode.INTERNAL_ERROR,
                details={"attribute": str(e)}
            )

        except Exception as e:
            # All other exceptions
            error_id = str(uuid.uuid4())[:8]
            logger.error(
                f"Unhandled API exception [{error_id}]: {str(e)}",
                extra={
                    "error_id": error_id,
                    "function": func.__name__,
                    "stack_trace": traceback.format_exc()
                },
                exc_info=True
            )

            raise MCPStoreException(
                message=f"Internal server error [{error_id}]",
                error_code=ErrorCode.INTERNAL_ERROR,
                details={
                    "function": func.__name__,
                    "type": type(e).__name__
                },
                stack_trace=traceback.format_exc()
            )
    
    return wrapper

# === Error Monitoring and Reporting ===

class ErrorMonitor:
    """Error monitor"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.recent_errors: List[Dict[str, Any]] = []
        self.max_recent_errors = 100
    
    def record_error(self, error: Union[MCPStoreException, Exception], context: Optional[Dict[str, Any]] = None):
        """Record error"""
        # Handle ErrorCode enum
        if isinstance(error, MCPStoreException):
            error_code = error.error_code
        else:
            error_code = ErrorCode.INTERNAL_ERROR.value

        # Update error count
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1

        # Record recent error
        error_info = {
            "error_id": getattr(error, 'error_id', str(uuid.uuid4())[:8]),
            "error_code": error_code,
            "message": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            "context": context or {}
        }

        self.recent_errors.append(error_info)

        # Keep recent errors list within limits
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors = self.recent_errors[-self.max_recent_errors:]

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_counts": self.error_counts,
            "recent_errors": self.recent_errors[-10:],  # Last 10 errors
            "unique_error_codes": len(self.error_counts)
        }

    def clear_stats(self):
        """Clear statistics"""
        self.error_counts.clear()
        self.recent_errors.clear()

# Global error monitor instance
error_monitor = ErrorMonitor()
