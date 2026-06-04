"""Simple knowledge graph for in-memory graph operations.

Provides GraphNode, GraphEdge, KnowledgeGraph for basic graph traversal,
and HybridRetriever for search with vector similarity.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """A node in the knowledge graph."""

    id: str
    type: str = "default"
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A directed edge between two nodes."""

    source: str
    target: str
    type: str = "related"
    weight: float = 1.0


class KnowledgeGraph:
    """In-memory directed knowledge graph with weighted edges."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, list[GraphEdge]] = {}
        self._reverse: dict[str, list[GraphEdge]] = {}

    def add_node(self, node: GraphNode) -> None:
        """Add a node, replacing any existing node with the same id."""
        self._nodes[node.id] = node
        self._edges.setdefault(node.id, [])
        self._reverse.setdefault(node.id, [])

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge, creating source/target nodes if missing."""
        for node_id in (edge.source, edge.target):
            if node_id not in self._nodes:
                self.add_node(GraphNode(id=node_id))
        self._edges[edge.source].append(edge)
        self._reverse[edge.target].append(edge)

    def get_node(self, node_id: str) -> GraphNode | None:
        """Retrieve a node by id, or return None."""
        return self._nodes.get(node_id)

    def get_neighbors(
        self, node_id: str, edge_type: str | None = None
    ) -> list[tuple[str, float]]:
        """Return (neighbor_id, weight) pairs for outgoing edges."""
        neighbors: list[tuple[str, float]] = []
        for edge in self._edges.get(node_id, []):
            if edge_type is None or edge.type == edge_type:
                neighbors.append((edge.target, edge.weight))
        return neighbors

    def find_shortest_path(
        self, source: str, target: str
    ) -> list[str] | None:
        """Dijkstra shortest path. Returns node ids or None if unreachable."""
        if source not in self._nodes or target not in self._nodes:
            return None
        distances: dict[str, float] = {source: 0.0}
        prev: dict[str, str | None] = {source: None}
        pq: list[tuple[float, str]] = [(0.0, source)]

        while pq:
            dist, node = heapq.heappop(pq)
            if node == target:
                path: list[str] = []
                while node is not None:
                    path.append(node)
                    node = prev[node]  # type: ignore[assignment]
                return list(reversed(path))
            if dist > distances.get(node, math.inf):
                continue
            for neighbor, weight in self.get_neighbors(node):
                new_dist = dist + weight
                if new_dist < distances.get(neighbor, math.inf):
                    distances[neighbor] = new_dist
                    prev[neighbor] = node
                    heapq.heappush(pq, (new_dist, neighbor))
        return None

    def to_json(self) -> dict[str, Any]:
        """Serialize graph to a JSON-compatible dict."""
        return {
            "nodes": [
                {"id": n.id, "type": n.type, "properties": dict(n.properties)}
                for n in self._nodes.values()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "type": e.type, "weight": e.weight}
                for edges in self._edges.values()
                for e in edges
            ],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> KnowledgeGraph:
        """Deserialize from a JSON-compatible dict."""
        g = cls()
        for nd in data.get("nodes", []):
            g.add_node(GraphNode(id=nd["id"], type=nd.get("type", "default"), properties=nd.get("properties", {})))
        for ed in data.get("edges", []):
            g.add_edge(GraphEdge(source=ed["source"], target=ed["target"], type=ed.get("type", "related"), weight=ed.get("weight", 1.0)))
        return g


class HybridRetriever:
    """Search nodes by combining vector similarity with graph traversal."""

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def _simple_hash_embed(self, text: str, dim: int = 64) -> list[float]:
        """Produce a deterministic float vector from text."""
        vec = [0.0] * dim
        for i, ch in enumerate(text):
            vec[i % dim] += (ord(ch) / 127.0) * ((-1) ** (i // dim))
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        return dot

    def search(
        self,
        nodes: list[GraphNode],
        query: str,
        max_results: int = 5,
    ) -> list[GraphNode]:
        """Return top-k nodes sorted by cosine similarity to query."""
        query_vec = self._simple_hash_embed(query)
        scored: list[tuple[float, GraphNode]] = []
        for node in nodes:
            node_text = f"{node.id} {node.type} {node.properties}"
            node_vec = self._simple_hash_embed(node_text)
            sim = self._cosine_sim(query_vec, node_vec)
            scored.append((sim, node))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in scored[:max_results]]
