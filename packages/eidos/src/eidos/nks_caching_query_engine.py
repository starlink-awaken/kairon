# ---
# domain: D-Memory
# layer: organ
# status: active
# ---
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from eidos.graph_store import Entity, Relation
from eidos.query_cache import QueryCache
from eidos.query_engine import CallGraphNode, CentralityScore, GraphQueryEngine, PathResult

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "Caching wrapper for GraphQueryEngine with per-query-type TTL"
Summary: "CachingQueryEngine - Transparent caching proxy for NKS graph queries"
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
# Caching Query Engine ≡ Engine
# 内涵 ≝ {Caching, Query, Engine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CachingQueryEngine)}
# 功能 ⊢ {Caching_Query, Query_Engine, Engine_Init}
# =============================================================================

_log = logging.getLogger(__name__)


class CachingQueryEngine:
    """
    Wrapper for GraphQueryEngine that adds intelligent caching.

    This wrapper intercepts all query methods and caches their results,
    providing significant performance improvements for repeated queries.

    Features:
    - Automatic cache key generation from query parameters
    - Dependency tracking for precise invalidation
    - Configurable TTL per query type
    - Cache bypass option for real-time requirements

    Example:
        engine = GraphQueryEngine(store)
        cache = QueryCache()
        caching_engine = CachingQueryEngine(engine, cache)

        # First call - executes query and caches result
        paths = caching_engine.find_paths("A", "B", max_depth=3)

        # Second call - returns cached result instantly
        paths = caching_engine.find_paths("A", "B", max_depth=3)
    """

    # TTL configurations per query type (can be customized)
    TTL_CONFIG: dict[str, float] = {
        "find_paths": 300.0,
        "find_shortest_path": 300.0,
        "get_call_graph": 180.0,
        "get_call_chain": 300.0,
        "find_orphans": 600.0,
        "find_leaf_functions": 600.0,
        "find_entry_points": 600.0,
        "get_centrality_scores": 300.0,
        "get_most_connected": 300.0,
        "find_cycles": 300.0,
        "get_neighbors": 120.0,
        "get_common_neighbors": 120.0,
        "export_subgraph": 180.0,
    }

    def __init__(
        self,
        engine: GraphQueryEngine,
        cache: QueryCache,
        default_bypass: bool = False,
    ) -> None:
        """
        Initialize CachingQueryEngine.

        Args:
            engine: GraphQueryEngine instance to wrap
            cache: QueryCache instance for storing results
            default_bypass: If True, bypass cache by default
        """
        super().__init__()
        self.engine = engine
        self.cache = cache
        self.default_bypass = default_bypass

    def _get_cache_key(self, query_type: str, **kwargs: Any) -> str:
        """Generate cache key for query."""
        return self.cache.generate_cache_key(query_type, **kwargs)

    def _execute_with_cache(
        self,
        query_type: str,
        method: Callable[..., object],
        bypass_cache: bool = False,
        **kwargs: Any,
    ) -> Any:
        """
        Execute query with caching support.

        Args:
            query_type: Type of query for TTL lookup
            method: Actual method to call on engine
            bypass_cache: If True, skip cache lookup and store
            **kwargs: Query parameters

        Returns:
            Query result (from cache or fresh)
        """
        if bypass_cache or self.default_bypass:
            return method(**kwargs)

        cache_key = self._get_cache_key(query_type, **kwargs)

        # Try to get from cache
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Execute query
        result = method(**kwargs)

        # Cache result with appropriate TTL
        ttl = self.TTL_CONFIG.get(query_type, 300.0)
        self.cache.set(cache_key, result, ttl=ttl)

        return result

    # === Path Finding Methods ===

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
        relation_types: list[str] | None = None,
        max_paths: int = 10,
        bypass_cache: bool = False,
    ) -> list[PathResult]:
        """
        Find paths between entities with caching.

        Args:
            source_id: Starting entity ID
            target_id: Target entity ID
            max_depth: Maximum search depth
            relation_types: Optional relation type filter
            max_paths: Maximum number of paths
            bypass_cache: If True, skip cache

        Returns:
            List of PathResult objects
        """
        return self._execute_with_cache(
            "find_paths",
            lambda **kw: self.engine.find_paths(**kw),
            bypass_cache=bypass_cache,
            source_id=source_id,
            target_id=target_id,
            max_depth=max_depth,
            relation_types=relation_types,
            max_paths=max_paths,
        )

    def find_shortest_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 10,
        relation_types: list[str] | None = None,
        bypass_cache: bool = False,
    ) -> PathResult | None:
        """
        Find shortest path with caching.

        Args:
            source_id: Starting entity ID
            target_id: Target entity ID
            max_depth: Maximum search depth
            relation_types: Optional relation type filter
            bypass_cache: If True, skip cache

        Returns:
            PathResult or None
        """
        return self._execute_with_cache(
            "find_shortest_path",
            lambda **kw: self.engine.find_shortest_path(**kw),
            bypass_cache=bypass_cache,
            source_id=source_id,
            target_id=target_id,
            max_depth=max_depth,
            relation_types=relation_types,
        )

    # === Call Graph Methods ===

    def get_call_graph(
        self,
        function_id: str,
        depth: int = 2,
        direction: str = "both",
        relation_types: list[str] | None = None,
        bypass_cache: bool = False,
    ) -> dict[str, CallGraphNode]:
        """
        Generate call graph with caching.

        Args:
            function_id: Center function entity ID
            depth: Traversal depth
            direction: Relation direction
            relation_types: Relation type filter
            bypass_cache: If True, skip cache

        Returns:
            Dictionary of entity_id -> CallGraphNode
        """
        return self._execute_with_cache(
            "get_call_graph",
            lambda **kw: self.engine.get_call_graph(**kw),
            bypass_cache=bypass_cache,
            function_id=function_id,
            depth=depth,
            direction=direction,
            relation_types=relation_types,
        )

    def get_call_chain(
        self,
        caller_id: str,
        callee_id: str,
        max_depth: int = 10,
        bypass_cache: bool = False,
    ) -> list[str] | None:
        """
        Find call chain with caching.

        Args:
            caller_id: Starting function ID
            callee_id: Target function ID
            max_depth: Maximum search depth
            bypass_cache: If True, skip cache

        Returns:
            List of entity IDs or None
        """
        return self._execute_with_cache(
            "get_call_chain",
            lambda **kw: self.engine.get_call_chain(**kw),
            bypass_cache=bypass_cache,
            caller_id=caller_id,
            callee_id=callee_id,
            max_depth=max_depth,
        )

    # === Analysis Methods ===

    def find_orphans(
        self,
        entity_types: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        bypass_cache: bool = False,
    ) -> list[Entity]:
        """
        Find orphaned entities with caching.

        Args:
            entity_types: Optional entity type filter
            exclude_patterns: Optional name patterns to exclude
            bypass_cache: If True, skip cache

        Returns:
            List of orphaned entities
        """
        return self._execute_with_cache(
            "find_orphans",
            lambda **kw: self.engine.find_orphans(**kw),
            bypass_cache=bypass_cache,
            entity_types=entity_types,
            exclude_patterns=exclude_patterns,
        )

    def find_leaf_functions(
        self,
        bypass_cache: bool = False,
    ) -> list[Entity]:
        """
        Find leaf functions with caching.

        Args:
            bypass_cache: If True, skip cache

        Returns:
            List of leaf function entities
        """
        return self._execute_with_cache(
            "find_leaf_functions",
            lambda **kw: self.engine.find_leaf_functions(),
            bypass_cache=bypass_cache,
        )

    def find_entry_points(
        self,
        bypass_cache: bool = False,
    ) -> list[Entity]:
        """
        Find entry points with caching.

        Args:
            bypass_cache: If True, skip cache

        Returns:
            List of entry point entities
        """
        return self._execute_with_cache(
            "find_entry_points",
            lambda **kw: self.engine.find_entry_points(),
            bypass_cache=bypass_cache,
        )

    def get_centrality_scores(
        self,
        top_n: int = 50,
        entity_types: list[str] | None = None,
        bypass_cache: bool = False,
    ) -> list[CentralityScore]:
        """
        Calculate centrality scores with caching.

        Args:
            top_n: Return top N results
            entity_types: Optional entity type filter
            bypass_cache: If True, skip cache

        Returns:
            List of CentralityScore objects
        """
        return self._execute_with_cache(
            "get_centrality_scores",
            lambda **kw: self.engine.get_centrality_scores(**kw),
            bypass_cache=bypass_cache,
            top_n=top_n,
            entity_types=entity_types,
        )

    def get_most_connected(
        self,
        top_n: int = 10,
        bypass_cache: bool = False,
    ) -> list[CentralityScore]:
        """
        Get most connected entities with caching.

        Args:
            top_n: Number of results
            bypass_cache: If True, skip cache

        Returns:
            List of CentralityScore objects
        """
        return self._execute_with_cache(
            "get_most_connected",
            lambda **kw: self.engine.get_most_connected(**kw),
            bypass_cache=bypass_cache,
            top_n=top_n,
        )

    def find_cycles(
        self,
        start_id: str,
        max_depth: int = 10,
        relation_types: list[str] | None = None,
        bypass_cache: bool = False,
    ) -> list[PathResult]:
        """
        Find cyclic dependencies with caching.

        Args:
            start_id: Starting entity ID
            max_depth: Maximum search depth
            relation_types: Optional relation type filter
            bypass_cache: If True, skip cache

        Returns:
            List of cyclic PathResult objects
        """
        return self._execute_with_cache(
            "find_cycles",
            lambda **kw: self.engine.find_cycles(**kw),
            bypass_cache=bypass_cache,
            start_id=start_id,
            max_depth=max_depth,
            relation_types=relation_types,
        )

    def get_neighbors(
        self,
        entity_id: str,
        direction: str = "both",
        relation_types: list[str] | None = None,
        bypass_cache: bool = False,
    ) -> list[tuple[Entity, Relation]]:
        """
        Get neighbors with caching.

        Args:
            entity_id: Center entity ID
            direction: Relation direction
            relation_types: Optional relation type filter
            bypass_cache: If True, skip cache

        Returns:
            List of (entity, relation) tuples
        """
        return self._execute_with_cache(
            "get_neighbors",
            lambda **kw: self.engine.get_neighbors(**kw),
            bypass_cache=bypass_cache,
            entity_id=entity_id,
            direction=direction,
            relation_types=relation_types,
        )

    def get_common_neighbors(
        self,
        entity_id1: str,
        entity_id2: str,
        bypass_cache: bool = False,
    ) -> list[Entity]:
        """
        Find common neighbors with caching.

        Args:
            entity_id1: First entity ID
            entity_id2: Second entity ID
            bypass_cache: If True, skip cache

        Returns:
            List of common neighbor entities
        """
        return self._execute_with_cache(
            "get_common_neighbors",
            lambda **kw: self.engine.get_common_neighbors(**kw),
            bypass_cache=bypass_cache,
            entity_id1=entity_id1,
            entity_id2=entity_id2,
        )

    def export_subgraph(
        self,
        center_id: str,
        depth: int = 2,
        direction: str = "both",
        bypass_cache: bool = False,
    ) -> dict[str, Any]:
        """
        Export subgraph with caching.

        Args:
            center_id: Center entity ID
            depth: Traversal depth
            direction: Relation direction
            bypass_cache: If True, skip cache

        Returns:
            Dictionary with 'nodes' and 'edges'
        """
        return self._execute_with_cache(
            "export_subgraph",
            lambda **kw: self.engine.export_subgraph(**kw),
            bypass_cache=bypass_cache,
            center_id=center_id,
            depth=depth,
            direction=direction,
        )

    def invalidate_entity(self, entity_id: str) -> int:
        """
        Invalidate all cache entries related to an entity.

        Args:
            entity_id: Entity ID to invalidate

        Returns:
            Number of entries invalidated
        """
        return self.cache.invalidate(entity_ids=[entity_id])

    def invalidate_relation(self, relation_id: str) -> int:
        """
        Invalidate all cache entries related to a relation.

        Args:
            relation_id: Relation ID to invalidate

        Returns:
            Number of entries invalidated
        """
        return self.cache.invalidate(relation_ids=[relation_id])

    def invalidate_entities(self, entity_ids: list[str]) -> int:
        """
        Invalidate cache entries for multiple entities.

        Args:
            entity_ids: List of entity IDs

        Returns:
            Number of entries invalidated
        """
        return self.cache.invalidate(entity_ids=entity_ids)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()

    def ping(self) -> bool:
        """Health check."""
        return self.engine.ping() and self.cache.ping()
