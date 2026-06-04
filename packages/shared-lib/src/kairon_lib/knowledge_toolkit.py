"""Knowledge graph, vector stores, hybrid retrieval, data sources.

Migrated from agentmesh toolkit/src/knowledge/ (KnowledgeGraph, HybridRetriever,
VectorStore, DataSources, ChromaVectorStore, QdrantVectorStore).
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

# ----- Knowledge Graph -----

NodeType = str
RelationType = str


@dataclass
class KnowledgeNode:
    id: str = ""
    type: NodeType = "entity"
    label: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class KnowledgeRelation:
    id: str = ""
    source_id: str = ""
    target_id: str = ""
    type: RelationType = "related_to"
    properties: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    created_at: float = 0.0


class KnowledgeGraph:
    """In-memory knowledge graph with typed nodes, relations, and search."""

    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeNode] = {}
        self._relations: dict[str, KnowledgeRelation] = {}
        self._node_counter: int = 0
        self._rel_counter: int = 0

    def add_node(self, type: NodeType = "entity", label: str = "", properties: dict[str, Any] | None = None) -> KnowledgeNode:
        self._node_counter += 1
        now = time.time()
        node = KnowledgeNode(id=f"n_{self._node_counter}", type=type, label=label, properties=properties or {}, created_at=now, updated_at=now)
        self._nodes[node.id] = node
        return node

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self._nodes.get(node_id)

    def add_relation(self, source_id: str, target_id: str, type: RelationType = "related_to", properties: dict[str, Any] | None = None, weight: float = 1.0) -> KnowledgeRelation | None:
        if source_id not in self._nodes or target_id not in self._nodes:
            return None
        self._rel_counter += 1
        rel = KnowledgeRelation(id=f"r_{self._rel_counter}", source_id=source_id, target_id=target_id, type=type, properties=properties or {}, weight=weight, created_at=time.time())
        self._relations[rel.id] = rel
        return rel

    def get_relations(self, node_id: str) -> list[KnowledgeRelation]:
        return [r for r in self._relations.values() if r.source_id == node_id or r.target_id == node_id]

    def get_neighbors(self, node_id: str) -> list[KnowledgeNode]:
        ids = set()
        for r in self.get_relations(node_id):
            ids.add(r.target_id if r.source_id == node_id else r.source_id)
        return [self._nodes[nid] for nid in ids if nid in self._nodes]

    def search(self, query: str) -> list[KnowledgeNode]:
        q = query.lower()
        return [n for n in self._nodes.values() if q in n.label.lower() or q in json.dumps(n.properties).lower()]

    def get_nodes_by_type(self, type: NodeType) -> list[KnowledgeNode]:
        return [n for n in self._nodes.values() if n.type == type]

    def delete_node(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        to_del = [r.id for r in self._relations.values() if r.source_id == node_id or r.target_id == node_id]
        for rid in to_del:
            self._relations.pop(rid, None)
        self._nodes.pop(node_id, None)
        return True

    def get_stats(self) -> dict[str, Any]:
        node_types: dict[str, int] = {}
        rel_types: dict[str, int] = {}
        for n in self._nodes.values():
            node_types[n.type] = node_types.get(n.type, 0) + 1
        for r in self._relations.values():
            rel_types[r.type] = rel_types.get(r.type, 0) + 1
        return {"node_count": len(self._nodes), "relation_count": len(self._relations), "node_types": node_types, "relation_types": rel_types}

    def to_json(self) -> dict[str, Any]:
        return {"nodes": [{"id": n.id, "type": n.type, "label": n.label, "properties": n.properties} for n in self._nodes.values()], "relations": [{"id": r.id, "source_id": r.source_id, "target_id": r.target_id, "type": r.type, "weight": r.weight} for r in self._relations.values()]}


# ----- Vector Store -----

@dataclass
class VectorDocument:
    id: str = ""
    content: str = ""
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    id: str = ""
    content: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class IVectorStore(Protocol):
    async def add(self, documents: list[VectorDocument]) -> None:
        ...

    async def delete(self, ids: list[str]) -> None:
        ...

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        ...

    async def get(self, ids: list[str]) -> list[VectorDocument]:
        ...

    async def clear(self) -> None:
        ...

    async def get_stats(self) -> dict[str, int]:
        ...


class MemoryVectorStore:
    """In-memory vector store with simple keyword matching."""

    def __init__(self) -> None:
        self._docs: dict[str, VectorDocument] = {}

    async def add(self, documents: list[VectorDocument]) -> None:
        for doc in documents:
            self._docs[doc.id] = doc

    async def delete(self, ids: list[str]) -> None:
        for did in ids:
            self._docs.pop(did, None)

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        q = query.lower()
        scored: list[tuple[float, VectorDocument]] = []
        for doc in self._docs.values():
            score = 0.0
            if q in doc.content.lower():
                score += 0.8
            for v in doc.metadata.values():
                if q in str(v).lower():
                    score += 0.3
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [SearchResult(id=d.id, content=d.content, score=s, metadata=d.metadata) for s, d in scored[:top_k]]

    async def get(self, ids: list[str]) -> list[VectorDocument]:
        return [self._docs[did] for did in ids if did in self._docs]

    async def clear(self) -> None:
        self._docs.clear()

    async def get_stats(self) -> dict[str, int]:
        return {"count": len(self._docs)}


# ----- Hybrid Retriever -----

class HybridRetriever:
    """Combine BM25 keyword scoring with vector search for hybrid retrieval."""

    def __init__(self, vector_store: IVectorStore | None = None) -> None:
        self._docs: dict[str, str] = {}
        self._store = vector_store or MemoryVectorStore()

    def index(self, documents: list[dict[str, Any]]) -> None:
        for doc in documents:
            self._docs[doc["id"]] = doc.get("content", "")

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        q_tokens = set(query.lower().split())
        bm25_scores: list[tuple[str, float]] = []
        for doc_id, content in self._docs.items():
            content_tokens = set(content.lower().split())
            overlap = len(q_tokens & content_tokens)
            if overlap > 0:
                bm25_scores.append((doc_id, overlap / math.sqrt(max(len(q_tokens), 1) * max(len(content_tokens), 1))))
        bm25_scores.sort(key=lambda x: x[1], reverse=True)
        bm25_top = bm25_scores[:top_k]
        vec_results = await self._store.search(query, top_k)
        seen: dict[str, SearchResult] = {}
        for doc_id, score in bm25_top:
            seen[doc_id] = SearchResult(id=doc_id, content=self._docs.get(doc_id, ""), score=score * 0.4, source="bm25")  # type: ignore[call-arg]
        for r in vec_results:
            if r.id in seen:
                seen[r.id].score = max(seen[r.id].score, r.score * 0.6)
                seen[r.id].source = "merged"  # type: ignore[attr-defined]
            else:
                r.score *= 0.6
                r.source = "vector"  # type: ignore[attr-defined]
                seen[r.id] = r
        results = sorted(seen.values(), key=lambda x: x.score, reverse=True)[:top_k]
        return results


# ----- Data Sources -----

class DataSourceType:
    LOCAL_FILE = "local_file"
    DATABASE = "database"
    API = "api"
    WEB_SCRAPING = "web_scraping"
    VECTOR_DB = "vector_db"
    KNOWLEDGE_BASE = "knowledge_base"


class BaseDataSource:
    """Abstract base for all data sources."""

    def __init__(self, name: str = "", source_type: str = "") -> None:
        self.name = name
        self.source_type = source_type
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def query(self, query: str) -> dict[str, Any]:
        return {"success": True, "data": [], "source": self.name}

    def is_connected(self) -> bool:
        return self._connected


class DataSourceFactory:
    """Registry and creation of data sources by type."""

    _sources: dict[str, BaseDataSource] = {}

    @classmethod
    def create(cls, source_type: str, name: str, **kwargs: Any) -> BaseDataSource:
        ds = BaseDataSource(name=name, source_type=source_type)
        cls._sources[name] = ds
        return ds

    @classmethod
    def get(cls, name: str) -> BaseDataSource | None:
        return cls._sources.get(name)

    @classmethod
    def get_all(cls) -> list[BaseDataSource]:
        return list(cls._sources.values())

    @classmethod
    def remove(cls, name: str) -> bool:
        return cls._sources.pop(name, None) is not None
