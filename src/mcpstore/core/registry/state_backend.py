"""
Deprecated state backend (stub).

This file is intentionally minimal to keep older imports from breaking while
explicitly directing callers to the new cache-layer architecture
(`mcpstore.core.cache.*`). Any attempt to instantiate or use the classes here
will raise a RuntimeError.
"""

import logging

logger = logging.getLogger(__name__)


class RegistryStateBackend:
    """Disabled interface stub."""

    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - disabled stub
        raise RuntimeError(
            "RegistryStateBackend is deprecated and no longer supported. "
            "Use CacheLayerManager with cache/state_manager.py instead."
        )


class KVRegistryStateBackend(RegistryStateBackend):
    """Disabled KV-backed implementation stub."""

    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - disabled stub
        super().__init__(*args, **kwargs)
