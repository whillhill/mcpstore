"""
Cache API routes

只读缓存访问接口，支持 Store/Agent 视角。
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Query

from mcpstore import ResponseBuilder, timed_response
from .api_decorators import validate_agent_id
from .api_dependencies import get_store

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_types(type_param: Optional[str]) -> List[str]:
    if not type_param:
        return []
    if isinstance(type_param, str):
        return [t.strip() for t in type_param.split(",") if t.strip()]
    if isinstance(type_param, list):
        return [t for t in type_param if isinstance(t, str) and t.strip()]
    return []

def _summary(data: List[dict], cache) -> dict:
    counts: dict = {}
    for item in data or []:
        t = item.get("_type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return {
        "scope": cache.get_scope() if hasattr(cache, "get_scope") else None,
        "backend": cache.get_backend_type() if hasattr(cache, "get_backend_type") else None,
        "counts": counts,
    }


# === Store-level cache ===
@router.get("/for_store/find_cache/read_entities", response_model=None)
@timed_response
async def store_cache_entities(type: Optional[str] = Query(None), key: Optional[str] = None):
    store = get_store()
    cache = store.find_cache()
    types = _parse_types(type) or None
    data = await cache.read_entity_async(types, key)
    return ResponseBuilder.success(
        message=f"Retrieved {len(data)} entities",
        data={"items": data, "summary": _summary(data, cache)}
    )


@router.get("/for_store/find_cache/read_relations", response_model=None)
@timed_response
async def store_cache_relations(type: Optional[str] = Query(None), key: Optional[str] = None):
    store = get_store()
    cache = store.find_cache()
    types = _parse_types(type) or None
    data = await cache.read_relation_async(types, key)
    return ResponseBuilder.success(
        message=f"Retrieved {len(data)} relations",
        data={"items": data, "summary": _summary(data, cache)}
    )


@router.get("/for_store/find_cache/read_states", response_model=None)
@timed_response
async def store_cache_states(type: Optional[str] = Query(None), key: Optional[str] = None):
    store = get_store()
    cache = store.find_cache()
    types = _parse_types(type) or None
    data = await cache.read_state_async(types, key)
    return ResponseBuilder.success(
        message=f"Retrieved {len(data)} states",
        data={"items": data, "summary": _summary(data, cache)}
    )


@router.get("/for_store/find_cache/read_events", response_model=None)
@timed_response
async def store_cache_events(type: Optional[str] = Query(None), key: Optional[str] = None):
    store = get_store()
    cache = store.find_cache()
    types = _parse_types(type) or None
    data = await cache.read_event_async(types, key)
    return ResponseBuilder.success(
        message=f"Retrieved {len(data)} events",
        data={"items": data, "summary": _summary(data, cache)}
    )


@router.get("/for_store/find_cache/inspect_cache", response_model=None)
@timed_response
async def store_cache_inspect():
    store = get_store()
    cache = store.find_cache()
    data = await cache.inspect_async()
    return ResponseBuilder.success(message="Cache inspect", data=data)


@router.get("/for_store/find_cache/dump_cache", response_model=None)
@timed_response
async def store_cache_dump():
    store = get_store()
    cache = store.find_cache()
    data = await cache.dump_all_async()
    return ResponseBuilder.success(message="Cache dump", data=data)


# === Agent-level cache ===
@router.get("/for_agent/{agent_id}/find_cache/read_entities", response_model=None)
@timed_response
async def agent_cache_entities(agent_id: str, type: Optional[str] = Query(None), key: Optional[str] = None):
    validate_agent_id(agent_id)
    store = get_store()
    cache = store.for_agent(agent_id).find_cache()
    types = _parse_types(type) or None
    data = await cache.read_entity_async(types, key)
    return ResponseBuilder.success(
        message=f"Retrieved {len(data)} entities for agent '{agent_id}'",
        data={"items": data, "summary": _summary(data, cache)}
    )


@router.get("/for_agent/{agent_id}/find_cache/read_relations", response_model=None)
@timed_response
async def agent_cache_relations(agent_id: str, type: Optional[str] = Query(None), key: Optional[str] = None):
    validate_agent_id(agent_id)
    store = get_store()
    cache = store.for_agent(agent_id).find_cache()
    types = _parse_types(type) or None
    data = await cache.read_relation_async(types, key)
    return ResponseBuilder.success(
        message=f"Retrieved {len(data)} relations for agent '{agent_id}'",
        data={"items": data, "summary": _summary(data, cache)}
    )


@router.get("/for_agent/{agent_id}/find_cache/read_states", response_model=None)
@timed_response
async def agent_cache_states(agent_id: str, type: Optional[str] = Query(None), key: Optional[str] = None):
    validate_agent_id(agent_id)
    store = get_store()
    cache = store.for_agent(agent_id).find_cache()
    types = _parse_types(type) or None
    data = await cache.read_state_async(types, key)
    return ResponseBuilder.success(
        message=f"Retrieved {len(data)} states for agent '{agent_id}'",
        data={"items": data, "summary": _summary(data, cache)}
    )


@router.get("/for_agent/{agent_id}/find_cache/read_events", response_model=None)
@timed_response
async def agent_cache_events(agent_id: str, type: Optional[str] = Query(None), key: Optional[str] = None):
    validate_agent_id(agent_id)
    store = get_store()
    cache = store.for_agent(agent_id).find_cache()
    types = _parse_types(type) or None
    data = await cache.read_event_async(types, key)
    return ResponseBuilder.success(
        message=f"Retrieved {len(data)} events for agent '{agent_id}'",
        data={"items": data, "summary": _summary(data, cache)}
    )


@router.get("/for_agent/{agent_id}/find_cache/inspect_cache", response_model=None)
@timed_response
async def agent_cache_inspect(agent_id: str):
    validate_agent_id(agent_id)
    store = get_store()
    cache = store.for_agent(agent_id).find_cache()
    data = await cache.inspect_async()
    return ResponseBuilder.success(message=f"Cache inspect for agent '{agent_id}'", data=data)


@router.get("/for_agent/{agent_id}/find_cache/dump_cache", response_model=None)
@timed_response
async def agent_cache_dump(agent_id: str):
    validate_agent_id(agent_id)
    store = get_store()
    cache = store.for_agent(agent_id).find_cache()
    data = await cache.dump_all_async()
    return ResponseBuilder.success(message=f"Cache dump for agent '{agent_id}'", data=data)
