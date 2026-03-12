
from fastapi import APIRouter

from .api_agent import agent_router
from .api_cache import router as cache_router
# Import all sub-route modules
from .api_store import store_router

# Import dependency injection functions (maintain compatibility)

# Create main router
router = APIRouter()

# Register all sub-routes
# Store-level operation routes
router.include_router(store_router, tags=["Store Operations"])

# Agent-level operation routes
router.include_router(agent_router, tags=["Agent Operations"])

# Cache read-only routes
router.include_router(cache_router, tags=["Cache"])

# Maintain backward compatibility - export commonly used functions and classes
# This way existing import statements can still work normally

# Route statistics information (for debugging)
def get_route_info():
    """Get route statistics information"""
    total_routes = len(router.routes)
    store_routes = len(store_router.routes)
    agent_routes = len(agent_router.routes)
    cache_routes = len(cache_router.routes)

    return {
        "total_routes": total_routes,
        "store_routes": store_routes,
        "agent_routes": agent_routes,
        "cache_routes": cache_routes,
        "modules": {
            "api_store.py": f"{store_routes} routes",
            "api_agent.py": f"{agent_routes} routes",
            "api_cache.py": f"{cache_routes} routes",
        }
    }

# Health check endpoint (simple root path check)
@router.get("/", tags=["System"])
async def api_root():
    """API root path - system information"""
    from mcpstore import ResponseBuilder
    
    route_info = get_route_info()
    
    return ResponseBuilder.success(
        message="MCPStore API is running",
        data={
            "service": "MCPStore API",
            "version": "0.6.0",
            "status": "operational",
            "endpoints": {
                "store": route_info.get("store_routes", 0),
                "agent": route_info.get("agent_routes", 0),
                "system": 2
            },
            "documentation": {
                "swagger": "/docs",
                "redoc": "/redoc",
                "openapi": "/openapi.json"
            }
        }
    )
