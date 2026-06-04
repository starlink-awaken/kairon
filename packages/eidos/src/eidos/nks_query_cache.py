# ---
# domain: D-Memory
# layer: organ
# status: active
# ---
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


class BaseMembrane:  # type: ignore[no-redef]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.logger = logging.getLogger(__name__)

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount


try:
    from .query_engine import CallGraphNode, PathResult
except (ImportError, ModuleNotFoundError):

    class PathResult:  # type: ignore[no-redef]
        nodes: list[object]

    class CallGraphNode:  # type: ignore[no-redef]
        entity: Any


"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "Cache expensive graph queries with TTL-based expiration and invalidation"
Summary: "QueryCache - High-performance caching layer for NKS graph queries"
Tags:
- nks
- cache
- query-optimization
- performance
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Query Cache ≡ Module
# 内涵 ≝ {Query, Cache}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, QueryCache)}
# 功能 ⊢ {Query_Cache, Init_Query, Validate_Cache}
# =============================================================================

_log = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """
    Cache entry with metadata for TTL and LRU tracking.

    Attributes:
        key: Cache key (hash of query parameters)
        result: Cached result data
        created_at: Timestamp when entry was created
        ttl: Time-to-live in seconds
        access_count: Number of times entry was accessed
        last_accessed: Timestamp of last access
        entity_tags: Set of entity IDs this cache entry depends on
        relation_tags: Set of relation IDs this cache entry depends on
        size_bytes: Estimated memory size of the entry
    """

    key: str
    result: Any
    created_at: float
    ttl: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    entity_tags: set[str] = field(default_factory=set)
    relation_tags: set[str] = field(default_factory=set)
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Check if cache entry has exceeded its TTL."""
        return time.time() - self.created_at > self.ttl

    def touch(self) -> None:
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1

    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return time.time() - self.created_at


class QueryCache:
    """
    High-performance cache for NKS graph query results.

    Features:
    - TTL-based automatic expiration
    - LRU eviction when max size is reached
    - Dependency-based invalidation (entity/relation aware)
    - Thread-safe concurrent access
    - Memory-efficient storage with size estimation
    - EU-aware operations with metabolic tax

    Cache Strategy:
    - Key: MD5 hash of normalized query parameters
    - TTL: Configurable per-entry (default 300s)
    - Eviction: LRU when max entries exceeded
    - Invalidation: Tag-based for precise cache invalidation
    """

    def __init__(
        self,
        default_ttl: float = 300.0,
        max_size: int = 1000,
        cleanup_interval: float = 60.0,
    ) -> None:
        """
        Initialize QueryCache.

        Args:
            default_ttl: Default TTL in seconds for cache entries
            max_size: Maximum number of entries (LRU eviction)
            cleanup_interval: Interval for background cleanup in seconds
        """
        self.status = "active"

        self.default_ttl = default_ttl
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval

        # Thread-safe cache storage using OrderedDict for LRU
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Statistics tracking
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._invalidations = 0
        self._total_size_bytes = 0

        # Reverse indexes for efficient invalidation
        self._entity_index: dict[str, set[str]] = {}  # entity_id -> set of cache keys
        self._relation_index: dict[str, set[str]] = {}  # relation_id -> set of cache keys

        # Background cleanup state
        self._last_cleanup = time.time()
        self._cleanup_lock = threading.Lock()

        # Deduct initialization energy cost
        self._deduct_metabolic_tax(amount=2.0)

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount

    def _generate_key(
        self,
        query_type: str,
        params: dict[str, Any],
    ) -> str:
        """
        Generate cache key from query parameters.

        Args:
            query_type: Type of query (e.g., 'find_paths', 'get_call_graph')
            params: Query parameters dictionary

        Returns:
            MD5 hash string as cache key
        """
        # Normalize params for consistent hashing
        normalized = json.dumps(params, sort_keys=True, default=str)
        key_data = f"{query_type}:{normalized}"
        return hashlib.md5(key_data.encode()).hexdigest()  # noqa: S324

    def _estimate_size(self, obj: Any) -> int:
        """
        Estimate memory size of cached object in bytes.

        Args:
            obj: Object to estimate size for

        Returns:
            Estimated size in bytes
        """
        try:
            # Use JSON serialization for estimation
            serialized = json.dumps(obj, default=str)
            return len(serialized.encode("utf-8"))
        except (TypeError, ValueError):
            # Fallback: rough estimate based on object representation
            return len(str(obj).encode("utf-8"))

    def _extract_dependencies(self, result: Any) -> tuple[set[str], set[str]]:
        """
        Extract entity and relation IDs from query result for tagging.

        Args:
            result: Query result object

        Returns:
            Tuple of (entity_ids, relation_ids) sets
        """
        entity_ids: set[str] = set()
        relation_ids: set[str] = set()

        if result is None:
            return entity_ids, relation_ids

        # Handle list of results
        if isinstance(result, list):
            for item in result:
                e_ids, r_ids = self._extract_dependencies(item)
                entity_ids.update(e_ids)
                relation_ids.update(r_ids)
            return entity_ids, relation_ids

        # Handle PathResult
        if isinstance(result, PathResult):
            for node in result.nodes:
                if node.entity:
                    entity_ids.add(node.entity.entity_id)
                if node.edge:
                    relation_ids.add(node.edge.relation_id)
            return entity_ids, relation_ids

        # Handle CallGraphNode
        if isinstance(result, CallGraphNode):
            if result.entity:
                entity_ids.add(result.entity.entity_id)
            return entity_ids, relation_ids

        # Handle Entity (duck typing for flexibility)
        if hasattr(result, "entity_id") and not hasattr(result, "source_id"):
            entity_ids.add(result.entity_id)
            return entity_ids, relation_ids

        # Handle Relation (duck typing for flexibility)
        if hasattr(result, "relation_id") and hasattr(result, "source_id"):
            relation_ids.add(result.relation_id)
            return entity_ids, relation_ids

        # Handle tuple (entity, relation) from get_neighbors
        if isinstance(result, tuple) and len(result) == 2:
            e_ids, r_ids = self._extract_dependencies(result[0])
            entity_ids.update(e_ids)
            relation_ids.update(r_ids)
            e_ids, r_ids = self._extract_dependencies(result[1])
            entity_ids.update(e_ids)
            relation_ids.update(r_ids)
            return entity_ids, relation_ids

        # Handle dictionary (e.g., export_subgraph results)
        if isinstance(result, dict):
            for value in result.values():
                e_ids, r_ids = self._extract_dependencies(value)
                entity_ids.update(e_ids)
                relation_ids.update(r_ids)
            return entity_ids, relation_ids

        return entity_ids, relation_ids

    def _add_to_indexes(self, key: str, entity_ids: set[str], relation_ids: set[str]) -> None:
        """
        Add cache key to reverse indexes for efficient invalidation.

        Args:
            key: Cache key
            entity_ids: Set of entity IDs the cache entry depends on
            relation_ids: Set of relation IDs the cache entry depends on
        """
        for entity_id in entity_ids:
            if entity_id not in self._entity_index:
                self._entity_index[entity_id] = set()
            self._entity_index[entity_id].add(key)

        for relation_id in relation_ids:
            if relation_id not in self._relation_index:
                self._relation_index[relation_id] = set()
            self._relation_index[relation_id].add(key)

    def _remove_from_indexes(self, key: str, entry: CacheEntry) -> None:
        """
        Remove cache key from reverse indexes.

        Args:
            key: Cache key
            entry: Cache entry being removed
        """
        for entity_id in entry.entity_tags:
            if entity_id in self._entity_index:
                self._entity_index[entity_id].discard(key)
                if not self._entity_index[entity_id]:
                    del self._entity_index[entity_id]

        for relation_id in entry.relation_tags:
            if relation_id in self._relation_index:
                self._relation_index[relation_id].discard(key)
                if not self._relation_index[relation_id]:
                    del self._relation_index[relation_id]

    def _cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        with self._cleanup_lock:
            expired_keys = []
            with self._lock:
                for key, entry in self._cache.items():
                    if entry.is_expired():
                        expired_keys.append((key, entry))

            # Remove outside iteration to avoid dict change during iteration
            removed = 0
            for key, entry in expired_keys:
                self._remove_entry(key, entry)
                removed += 1

            return removed

    def _remove_entry(self, key: str, entry: CacheEntry) -> None:
        """
        Remove a single cache entry.

        Args:
            key: Cache key
            entry: Cache entry to remove
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._total_size_bytes -= entry.size_bytes
                self._remove_from_indexes(key, entry)

    def _evict_lru(self) -> str | None:
        """
        Evict least recently used entry.

        Returns:
            Key of evicted entry or None if cache is empty
        """
        with self._lock:
            if not self._cache:
                return None

            # OrderedDict maintains insertion order, move_to_end on access
            # So the first item is the LRU
            lru_key = next(iter(self._cache))
            lru_entry = self._cache[lru_key]

            del self._cache[lru_key]
            self._total_size_bytes -= lru_entry.size_bytes
            self._remove_from_indexes(lru_key, lru_entry)
            self._evictions += 1

            return lru_key

    def _maybe_cleanup(self) -> None:
        """Trigger background cleanup if interval has passed."""
        now = time.time()
        if now - self._last_cleanup > self.cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = now

    def get(self, key: str) -> Any | None:
        """
        Get value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        self._maybe_cleanup()

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                self._misses += 1
                self._remove_entry(key, entry)
                return None

            # Update access stats and move to end (MRU position)
            entry.touch()
            self._cache.move_to_end(key)
            self._hits += 1

            # Deduct metabolic tax for cache hit (minimal)
            self._deduct_metabolic_tax(amount=0.01)

            return entry.result

    def set(
        self,
        key: str,
        result: Any,
        ttl: float | None = None,
        entity_tags: set[str] | None = None,
        relation_tags: set[str] | None = None,
    ) -> None:
        """
        Store result in cache with LRU eviction.

        Args:
            key: Cache key
            result: Result to cache
            ttl: Optional custom TTL (uses default if not specified)
            entity_tags: Optional set of entity IDs this result depends on
            relation_tags: Optional set of relation IDs this result depends on
        """
        ttl = ttl if ttl is not None else self.default_ttl

        # Extract dependencies if not provided
        if entity_tags is None or relation_tags is None:
            extracted_entities, extracted_relations = self._extract_dependencies(result)
            entity_tags = entity_tags or extracted_entities
            relation_tags = relation_tags or extracted_relations

        # Estimate size
        size_bytes = self._estimate_size(result)

        with self._lock:
            # If key exists, update it
            if key in self._cache:
                old_entry = self._cache[key]
                self._total_size_bytes -= old_entry.size_bytes
                self._remove_from_indexes(key, old_entry)

            # Check if we need to evict (LRU)
            while len(self._cache) >= self.max_size:
                self._evict_lru()

            # Create new entry
            entry = CacheEntry(
                key=key,
                result=result,
                created_at=time.time(),
                ttl=ttl,
                entity_tags=entity_tags,
                relation_tags=relation_tags,
                size_bytes=size_bytes,
            )

            # Store in cache (OrderedDict maintains insertion order)
            self._cache[key] = entry
            self._total_size_bytes += size_bytes

            # Add to indexes for invalidation
            self._add_to_indexes(key, entity_tags, relation_tags)

        # Deduct metabolic tax for cache write
        self._deduct_metabolic_tax(amount=0.05)

    def invalidate(
        self,
        entity_ids: list[str] | None = None,
        relation_ids: list[str] | None = None,
    ) -> int:
        """
        Invalidate cache entries related to specific entities/relations.

        This performs tag-based invalidation, removing all cache entries
        that depend on the specified entities or relations.

        Args:
            entity_ids: List of entity IDs to invalidate
            relation_ids: List of relation IDs to invalidate

        Returns:
            Number of cache entries invalidated
        """
        keys_to_invalidate: set[str] = set()

        with self._lock:
            # Collect keys from entity index
            if entity_ids:
                for entity_id in entity_ids:
                    if entity_id in self._entity_index:
                        keys_to_invalidate.update(self._entity_index[entity_id])

            # Collect keys from relation index
            if relation_ids:
                for relation_id in relation_ids:
                    if relation_id in self._relation_index:
                        keys_to_invalidate.update(self._relation_index[relation_id])

        # Remove collected entries
        invalidated = 0
        for key in keys_to_invalidate:
            entry = None
            with self._lock:
                entry = self._cache.get(key)
            if entry:
                self._remove_entry(key, entry)
                invalidated += 1

        self._invalidations += invalidated

        # Deduct metabolic tax proportional to invalidations
        if invalidated > 0:
            self._deduct_metabolic_tax(amount=0.02 * invalidated)

        return invalidated

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries with keys matching a pattern.

        Args:
            pattern: Substring to match in cache keys

        Returns:
            Number of entries invalidated
        """
        keys_to_remove: list[tuple[str, CacheEntry]] = []

        with self._lock:
            for key, entry in self._cache.items():
                if pattern in key:
                    keys_to_remove.append((key, entry))

        invalidated = 0
        for key, entry in keys_to_remove:
            self._remove_entry(key, entry)
            invalidated += 1

        self._invalidations += invalidated
        return invalidated

    def invalidate_all(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._entity_index.clear()
            self._relation_index.clear()
            self._total_size_bytes = 0
            self._invalidations += count

        # Deduct metabolic tax for bulk operation
        self._deduct_metabolic_tax(amount=1.0)

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache metrics:
            - hit_rate: Cache hit rate (0.0 - 1.0)
            - hits: Total cache hits
            - misses: Total cache misses
            - size: Current number of entries
            - max_size: Maximum cache size
            - total_size_bytes: Total memory usage
            - evictions: Number of LRU evictions
            - invalidations: Number of invalidations
            - default_ttl: Default TTL setting
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            return {
                "hit_rate": round(hit_rate, 4),
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "max_size": self.max_size,
                "utilization": len(self._cache) / self.max_size if self.max_size > 0 else 0,
                "total_size_bytes": self._total_size_bytes,
                "total_size_mb": round(self._total_size_bytes / (1024 * 1024), 2),
                "evictions": self._evictions,
                "invalidations": self._invalidations,
                "default_ttl": self.default_ttl,
                "entity_index_size": len(self._entity_index),
                "relation_index_size": len(self._relation_index),
            }

    def ping(self) -> bool:
        """Health check for QueryCache."""
        try:
            stats = self.get_stats()
            return stats is not None
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return False

    def generate_cache_key(
        self,
        query_type: str,
        **kwargs: Any,
    ) -> str:
        """
        Public method to generate cache key for query parameters.

        Args:
            query_type: Type of query
            **kwargs: Query parameters

        Returns:
            Cache key string
        """
        return self._generate_key(query_type, kwargs)


# Backward-compatible re-export: CachingQueryEngine has been extracted to its
# own module for maintainability.  All existing imports continue to work.
# We use __getattr__ (PEP 562) to avoid a circular import when
# caching_query_engine is imported before query_cache has finished loading.
def __getattr__(name: str) -> Any:
    if name == "CachingQueryEngine":
        try:
            from .caching_query_engine import CachingQueryEngine
        except (ImportError, ModuleNotFoundError):

            class CachingQueryEngine:  # type: ignore[no-redef]
                pass

        return CachingQueryEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
