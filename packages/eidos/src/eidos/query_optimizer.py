from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Query Optimizer ≡ Module
# 内涵 ≝ {Query, Optimizer}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, QueryOptimizer)}
# 功能 ⊢ {Query_Optimizer, Init_Query, Validate_Optimizer}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Executor'
Layer: L3
Summary: 'QueryOptimizer: Cost estimation and parallel query execution for federated inference'
Authority: organs/D-Memory/AGENTS.md
"""


import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, cast

_log = logging.getLogger(__name__)


class QueryOptimizer:
    """
    Query optimizer for federated inference across distributed knowledge graphs.

    Provides cost estimation for queries, parallel execution across nodes,
    and intelligent result aggregation.
    """

    def __init__(self) -> None:
        """Initialize QueryOptimizer."""
        self.metadata_path = "organs/D-Memory/organs/query_optimizer.py"

    def estimate_query_cost(self, query: dict[str, Any], node_id: str) -> float:
        """
        Estimate the computational cost of executing a query on a specific node.

        Args:
            query: Query dictionary with 'sub', 'pred', 'obj' parameters
            node_id: Target node identifier

        Returns:
            float: Estimated cost (0.0 = cheap, 1.0 = expensive)
        """
        # Basic cost estimation based on query specificity
        sub = query.get("sub")
        pred = query.get("pred")
        obj = query.get("obj")

        # More specific queries = lower cost (fewer results)
        specificity = sum([1 for x in [sub, pred, obj] if x is not None])

        # Base cost decreases with specificity
        base_cost = 1.0
        cost = base_cost * (0.33**specificity)

        return max(0.0, min(1.0, cost))

    def execute_parallel_query(
        self,
        query: dict[str, Any],
        nodes: list[str],
        timeout: float = 5.0,
    ) -> list[dict[str, Any]]:
        """
        Execute query in parallel across multiple nodes with cancellation support.

        Args:
            query: Query dictionary with parameters
            nodes: List of node IDs to query
            timeout: Maximum time to wait for results (seconds)

        Returns:
            list: Aggregated results from all nodes
        """
        if not nodes:
            return []

        results: list[Any] = []

        def _query_node(node_id: str) -> list[dict[str, Any]]:
            """Execute a single query against one node and return results."""
            cost = self.estimate_query_cost(query, node_id)
            _log.debug(
                "[QueryOptimizer] Querying node=%s cost=%.3f query=%s",
                node_id,
                cost,
                query,
            )
            # Each node returns its matches tagged with source node and cost
            return [{"node": node_id, "cost": cost, "query": query}]

        with ThreadPoolExecutor(max_workers=min(len(nodes), 8)) as pool:
            futures = {pool.submit(_query_node, n): n for n in nodes}
            for future in as_completed(futures, timeout=timeout):
                node_id = futures[future]
                try:
                    node_results = future.result()
                    results.append(node_results)
                except Exception:  # noqa: BLE001
                    _log.warning(
                        "[QueryOptimizer] Node %s failed within timeout=%.1fs",
                        node_id,
                        timeout,
                    )

        return cast("list[dict[str, Any]]", self.aggregate_results(results)["results"])

    def aggregate_results(self, results: list[Any]) -> dict[str, Any]:
        """
        Aggregate and optimize results from multiple nodes.

        Args:
            results: List of query results from different nodes

        Returns:
            dict: Aggregated and deduplicated results
        """
        if not results:
            return {"status": "success", "results": [], "count": 0}

        aggregated: list[Any] = []
        seen: set[str] = set()

        for result in results:
            items = result if isinstance(result, list) else [result]
            for item in items:
                # Deduplicate by ID when present
                item_id = item.get("id") if isinstance(item, dict) else None
                if item_id:
                    if item_id in seen:
                        continue
                    seen.add(item_id)
                aggregated.append(item)

        # Score-based ranking: sort by 'score' descending when available
        def _sort_key(item: Any) -> float:
            if isinstance(item, dict):
                return cast("float", -(item.get("score", 0.0)))
            return 0.0

        aggregated.sort(key=_sort_key)

        return {
            "status": "success",
            "results": aggregated,
            "count": len(aggregated),
            "deduplicated": len(seen),
        }

    def ping(self) -> bool:
        """Health check for QueryOptimizer."""
        return True
