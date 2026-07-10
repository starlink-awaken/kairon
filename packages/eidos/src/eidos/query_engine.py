"""Graph query engine for knowledge graph traversal.

Provides node/edge storage with basic query capabilities. Advanced
features (path finding, centrality, community detection) are planned.
"""

from __future__ import annotations

from typing import Any


class CallGraphNode:
    """A node in the call graph."""

    def __init__(self, id: str, name: str = "", node_type: str = "function") -> None:
        self.id = id
        self.name = name
        self.node_type = node_type
        self.metadata: dict[str, Any] = {}


class CallGraphEdge:
    """An edge in the call graph."""

    def __init__(self, source: str, target: str, relation: str = "calls") -> None:
        self.source = source
        self.target = target
        self.relation = relation


class GraphQueryEngine:
    """Basic graph query engine."""

    def __init__(self) -> None:
        self._nodes: dict[str, CallGraphNode] = {}
        self._edges: list[CallGraphEdge] = []

    def add_node(self, node: CallGraphNode) -> None:
        self._nodes[node.id] = node

    def add_edge(self, edge: CallGraphEdge) -> None:
        self._edges.append(edge)

    def query(self, node_type: str = "", limit: int = 100) -> list[CallGraphNode]:
        """Query nodes by type."""
        nodes = [n for n in self._nodes.values() if not node_type or n.node_type == node_type]
        return nodes[:limit]

    def get_neighbors(self, node_id: str) -> list[str]:
        """Get neighboring node IDs."""
        return [e.target for e in self._edges if e.source == node_id]


__all__ = ["CallGraphNode", "CallGraphEdge", "GraphQueryEngine"]
