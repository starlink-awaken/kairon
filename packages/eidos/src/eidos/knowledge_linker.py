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
# Knowledge Linker ≡ Module
# 内涵 ≝ {Knowledge, Linker}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, KnowledgeLinker)}
# 功能 ⊢ {Knowledge_Linker, Init_Knowledge, Validate_Linker}
# =============================================================================

# ---
# domain: D-Memory
# layer: organ
# status: active
# ---

import logging
import time
from collections import deque
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)

__all__ = ["KnowledgeNode", "KnowledgeLink", "KnowledgeLinker"]


@dataclass
class KnowledgeNode:
    node_id: str
    content: str
    node_type: str = "fact"
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class KnowledgeLink:
    source: str
    target: str
    relation: str
    strength: float = 1.0
    metadata: dict = field(default_factory=dict)


class KnowledgeLinker:
    """Graph-based knowledge linking engine for D-Memory."""

    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeNode] = {}
        self._links: list[KnowledgeLink] = []

    # -- Node operations -----------------------------------------------------

    def add_node(self, node: KnowledgeNode) -> None:
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self._nodes.get(node_id)

    def search_nodes(self, query: str) -> list[KnowledgeNode]:
        q = query.lower()
        return [n for n in self._nodes.values() if q in n.content.lower()]

    # -- Link operations -----------------------------------------------------

    def add_link(self, link: KnowledgeLink) -> None:
        self._links.append(link)

    def get_links_from(self, node_id: str) -> list[KnowledgeLink]:
        return [lk for lk in self._links if lk.source == node_id]

    def get_links_to(self, node_id: str) -> list[KnowledgeLink]:
        return [lk for lk in self._links if lk.target == node_id]

    # -- Graph traversal -----------------------------------------------------

    def _adjacency(self) -> dict[str, set[str]]:
        adj: dict[str, set[str]] = {nid: set() for nid in self._nodes}
        for lk in self._links:
            adj.setdefault(lk.source, set()).add(lk.target)
            adj.setdefault(lk.target, set()).add(lk.source)
        return adj

    def find_path(self, source: str, target: str) -> list[str] | None:
        if source not in self._nodes or target not in self._nodes:
            return None
        if source == target:
            return [source]
        adj = self._adjacency()
        visited: set[str] = {source}
        queue: deque[list[str]] = deque([[source]])
        while queue:
            path = queue.popleft()
            for neighbour in adj.get(path[-1], set()):
                if neighbour == target:
                    return path + [neighbour]
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(path + [neighbour])
        return None

    def get_related(self, node_id: str, max_depth: int = 2) -> list[str]:
        if node_id not in self._nodes:
            return []
        adj = self._adjacency()
        visited: set[str] = {node_id}
        frontier: set[str] = {node_id}
        for _ in range(max_depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                for neighbour in adj.get(nid, set()):
                    if neighbour not in visited:
                        visited.add(neighbour)
                        next_frontier.add(neighbour)
            frontier = next_frontier
        visited.discard(node_id)
        return sorted(visited)

    def get_clusters(self) -> list[list[str]]:
        adj = self._adjacency()
        visited: set[str] = set()
        clusters: list[list[str]] = []
        for nid in self._nodes:
            if nid in visited:
                continue
            component: list[str] = []
            queue: deque[str] = deque([nid])
            while queue:
                cur = queue.popleft()
                if cur in visited:
                    continue
                visited.add(cur)
                component.append(cur)
                for nb in adj.get(cur, set()):
                    if nb not in visited:
                        queue.append(nb)
            clusters.append(sorted(component))
        return clusters

    def get_hub_nodes(self, min_connections: int = 3) -> list[str]:
        adj = self._adjacency()
        return sorted(nid for nid, neighbours in adj.items() if len(neighbours) >= min_connections)
