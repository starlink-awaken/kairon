"""Query cache — in-memory cache for graph query results.

TODO: implement full caching with TTL, invalidation, and persistence.
"""

from __future__ import annotations

import time
from typing import Any


class QueryCache:
    """In-memory query result cache with TTL support."""

    def __init__(self, ttl: float = 300.0) -> None:
        self._ttl = ttl
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Get a cached value by key. Returns None if missing or expired."""
        if key in self._cache:
            ts, value = self._cache[key]
            if time.monotonic() - ts < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set a cached value with optional per-entry TTL."""
        self._cache[key] = (time.monotonic(), value)

    def invalidate(self, key: str) -> None:
        """Invalidate a specific cache entry."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()


__all__ = [
    "QueryCache",
]
