"""
Simple in-memory TTL cache.
Thread-safe for single-process deployments.
Swap the body of get/set for Redis calls to scale horizontally.
"""
from datetime import datetime
from typing import Any, Optional

from app.core.config import settings

_store: dict[str, dict] = {}


def get(key: str) -> Optional[Any]:
    """Return cached value if it exists and hasn't expired, else None."""
    entry = _store.get(key)
    if entry is None:
        return None
    age = (datetime.now() - entry["ts"]).total_seconds()
    if age > settings.cache_ttl_seconds:
        del _store[key]
        return None
    return entry["data"]


def set(key: str, data: Any) -> None:  # noqa: A001
    """Store a value with the current timestamp."""
    _store[key] = {"data": data, "ts": datetime.now()}


def clear() -> None:
    """Wipe the entire cache (used in tests)."""
    _store.clear()
