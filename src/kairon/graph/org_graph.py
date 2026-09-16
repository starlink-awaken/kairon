"""org_graph.py — 组织人脉图谱：单位-人物-来件关系网络与沟通偏好建模。

在 KEMS-v2 KnowledgeGraph 基础上扩展组织关系子图，支持：
- 三类节点：单位(organization)、人物(person)、来件(document)
- 三类关系：任职(holds_position)、来件(sent_document)、沟通(communicated)
- 基于时间衰减（半衰期 365 天）与沟通频次的关系权重
- JSONL 持久化与增量更新

BET-Y2Q1-T7-01 交付面。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator


# ── Time-decay constants ──

HALF_LIFE_DAYS = 365  # 关系权重半衰期（天）
DECAY_LN2 = math.log(2.0)


# ── Entity types ──


class OrgNodeType(str, Enum):
    """组织人脉图谱节点类型。"""

    ORGANIZATION = "organization"  # 单位/部门
    PERSON = "person"  # 关键人物/联系人
    DOCUMENT = "document"  # 来件/公文/邮件


class OrgRelationType(str, Enum):
    """组织人脉图谱关系类型。"""

    HOLDS_POSITION = "holds_position"  # 人物在单位任职
    SENT_DOCUMENT = "sent_document"  # 单位/人物发来文件
    COMMUNICATED = "communicated"  # 沟通交互记录


# ── Data classes ──


@dataclass
class OrgNode:
    """组织人脉图谱节点。"""

    id: str
    node_type: OrgNodeType
    name: str
    title: str = ""  # 职位（人物）或文号（来件）
    summary: str = ""  # 摘要/偏好描述
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def search_text(self) -> str:
        """Combined text for text matching."""
        parts = [self.name, self.title, self.summary, " ".join(self.tags)]
        return " ".join(p for p in parts if p)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["node_type"] = self.node_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OrgNode:
        d = dict(d)
        d["node_type"] = OrgNodeType(d["node_type"])
        return cls(**d)


@dataclass
class OrgRelation:
    """组织人脉图谱关系（带时间戳与频次）。"""

    source_id: str
    target_id: str
    relation: OrgRelationType
    weight: float = 1.0
    first_contact: str = ""  # ISO date
    last_contact: str = ""  # ISO date
    frequency: int = 1  # 沟通频次
    metadata: dict[str, Any] = field(default_factory=dict)

    def effective_weight(self, reference_date: datetime | None = None) -> float:
        """计算时间衰减后的有效权重。

        公式: weight * frequency * exp(-ln2 * elapsed_days / half_life)
        """
        if not self.last_contact:
            return self.weight * self.frequency

        ref = reference_date or datetime.now(timezone.utc)
        try:
            last = datetime.fromisoformat(self.last_contact)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed = (ref - last).total_seconds() / 86400.0
        except (ValueError, TypeError):
            return self.weight * self.frequency

        if elapsed < 0:
            elapsed = 0.0
        decay = math.exp(-DECAY_LN2 * elapsed / HALF_LIFE_DAYS)
        return self.weight * self.frequency * decay

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["relation"] = self.relation.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OrgRelation:
        d = dict(d)
        d["relation"] = OrgRelationType(d["relation"])
        return cls(**d)


# ── Tokenizer (reuse pattern from kems_v2) ──


def _tokenize(text: str) -> list[str]:
    """Simple CJK-aware tokenizer."""
    text = unicodedata.normalize("NFKC", text).lower()
    tokens: list[str] = []
    current: list[str] = []
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(ch)
        elif ch.isalnum():
            current.append(ch)
        else:
            if current:
                tokens.append("".join(current))
                current = []
    if current:
        tokens.append("".join(current))
    return tokens


# ── OrgGraph ──


class OrgGraph:
    """组织人脉图谱：单位-人物-来件关系网络。

    支持 BM25 风格文本检索、多跳关系遍历、时间衰减权重。
    持久化格式与 KEMS-v2 KnowledgeGraph 兼容（JSONL）。
    """

    def __init__(self) -> None:
        self._nodes: dict[str, OrgNode] = {}
        self._relations: list[OrgRelation] = []
        self._outgoing: dict[str, list[OrgRelation]] = defaultdict(list)
        self._incoming: dict[str, list[OrgRelation]] = defaultdict(list)
        self._token_index: dict[str, set[str]] = defaultdict(set)

    # ── Node operations ──

    def add_node(self, node: OrgNode) -> None:
        """Add or update a node."""
        self._nodes[node.id] = node
        for token in _tokenize(node.search_text):
            self._token_index[token].add(node.id)

    def get_node(self, node_id: str) -> OrgNode | None:
        """Retrieve a node by ID."""
        return self._nodes.get(node_id)

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its relations."""
        if node_id not in self._nodes:
            return False
        node = self._nodes.pop(node_id)
        for token in _tokenize(node.search_text):
            self._token_index.get(token, set()).discard(node_id)
        self._relations = [
            r for r in self._relations
            if r.source_id != node_id and r.target_id != node_id
        ]
        self._outgoing.pop(node_id, None)
        self._incoming.pop(node_id, None)
        return True

    def list_nodes(
        self,
        node_type: OrgNodeType | None = None,
        tags: list[str] | None = None,
    ) -> list[OrgNode]:
        """List nodes, optionally filtered by type and/or tags."""
        result = list(self._nodes.values())
        if node_type is not None:
            result = [n for n in result if n.node_type == node_type]
        if tags:
            tag_set = set(tags)
            result = [n for n in result if tag_set.intersection(n.tags)]
        return result

    # ── Relation operations ──

    def add_relation(self, relation: OrgRelation) -> None:
        """Add a directed relation between two nodes."""
        if relation.source_id not in self._nodes:
            raise ValueError(f"source node not found: {relation.source_id}")
        if relation.target_id not in self._nodes:
            raise ValueError(f"target node not found: {relation.target_id}")
        self._relations.append(relation)
        self._outgoing[relation.source_id].append(relation)
        self._incoming[relation.target_id].append(relation)

    def update_communication(self, source_id: str, target_id: str, timestamp: str = "") -> None:
        """Increment communication frequency and update last_contact timestamp."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        for rel in self._relations:
            if (rel.source_id == source_id and rel.target_id == target_id
                    and rel.relation == OrgRelationType.COMMUNICATED):
                rel.frequency += 1
                rel.last_contact = ts
                return
        # No existing relation: create one with default weight
        self.add_relation(OrgRelation(
            source_id=source_id,
            target_id=target_id,
            relation=OrgRelationType.COMMUNICATED,
            weight=1.0,
            first_contact=ts,
            last_contact=ts,
            frequency=1,
        ))

    def get_neighbors(
        self,
        node_id: str,
        direction: str = "out",
        relation: OrgRelationType | None = None,
    ) -> list[OrgRelation]:
        """Get relations connected to a node."""
        edges: list[OrgRelation] = []
        if direction in ("out", "both"):
            edges.extend(self._outgoing.get(node_id, []))
        if direction in ("in", "both"):
            edges.extend(self._incoming.get(node_id, []))
        if relation is not None:
            edges = [e for e in edges if e.relation == relation]
        return edges

    # ── Text search ──

    def search(self, query: str, top_k: int = 10) -> list[tuple[OrgNode, float]]:
        """BM25-style text search over node content."""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores: dict[str, float] = defaultdict(float)
        for token in query_tokens:
            matching_ids = self._token_index.get(token, set())
            for nid in matching_ids:
                scores[nid] += 1.0

        ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        result: list[tuple[OrgNode, float]] = []
        for nid, score in ranked[:top_k]:
            node = self._nodes.get(nid)
            if node is not None:
                result.append((node, score))
        return result

    # ── Graph traversal ──

    def bfs(
        self,
        start_id: str,
        max_hops: int = 2,
        relation: OrgRelationType | None = None,
    ) -> dict[str, int]:
        """BFS from start_id, returning {node_id: hop_distance}."""
        if start_id not in self._nodes:
            return {}
        visited: dict[str, int] = {start_id: 0}
        frontier = [start_id]
        for hop in range(1, max_hops + 1):
            next_frontier: list[str] = []
            for nid in frontier:
                for rel in self.get_neighbors(nid, direction="out", relation=relation):
                    if rel.target_id not in visited:
                        visited[rel.target_id] = hop
                        next_frontier.append(rel.target_id)
            frontier = next_frontier
        return visited

    def network_view(self, query: str, max_hops: int = 2) -> dict[str, Any]:
        """Return a structured network view for a query.

        Finds matching nodes via text search, then expands via BFS
        to return a subgraph with effective weights.
        """
        matches = self.search(query, top_k=5)
        if not matches:
            return {"query": query, "nodes": [], "relations": [], "match_count": 0}

        all_nodes: dict[str, OrgNode] = {}
        all_relations: list[dict[str, Any]] = {}

        for match_node, score in matches:
            all_nodes[match_node.id] = match_node
            reachable = self.bfs(match_node.id, max_hops=max_hops)
            for nid in reachable:
                if nid not in all_nodes:
                    all_nodes[nid] = self._nodes[nid]

        # Collect relations between matched nodes
        for nid in all_nodes:
            for rel in self.get_neighbors(nid, direction="out"):
                if rel.target_id in all_nodes:
                    key = f"{rel.source_id}->{rel.target_id}:{rel.relation.value}"
                    if key not in all_relations:
                        all_relations[key] = {
                            "source_id": rel.source_id,
                            "target_id": rel.target_id,
                            "relation": rel.relation.value,
                            "weight": rel.weight,
                            "frequency": rel.frequency,
                            "effective_weight": round(rel.effective_weight(), 4),
                            "last_contact": rel.last_contact,
                        }

        return {
            "query": query,
            "match_count": len(matches),
            "nodes": [
                {
                    "id": n.id,
                    "type": n.node_type.value,
                    "name": n.name,
                    "title": n.title,
                    "tags": n.tags,
                }
                for n in all_nodes.values()
            ],
            "relations": list(all_relations.values()),
        }

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        """Graph statistics."""
        type_counts: dict[str, int] = defaultdict(int)
        for n in self._nodes.values():
            type_counts[n.node_type.value] += 1
        rel_counts: dict[str, int] = defaultdict(int)
        for rel in self._relations:
            rel_counts[rel.relation.value] += 1
        return {
            "total_nodes": len(self._nodes),
            "total_relations": len(self._relations),
            "node_types": dict(type_counts),
            "relation_types": dict(rel_counts),
            "avg_out_degree": len(self._relations) / max(len(self._nodes), 1),
        }

    # ── Persistence ──

    def save(self, path: str | Path) -> None:
        """Save graph to JSONL."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for node in self._nodes.values():
                record = {"_t": "node", **node.to_dict()}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            for rel in self._relations:
                record = {"_t": "relation", **rel.to_dict()}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> OrgGraph:
        """Load graph from JSONL file."""
        graph = cls()
        path = Path(path)
        if not path.exists():
            return graph
        with path.open("r", encoding="utf-8") as f:
            # First pass: load all nodes
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                t = record.pop("_t", None)
                if t == "node":
                    graph.add_node(OrgNode.from_dict(record))
            # Second pass: load relations
            f.seek(0)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                t = record.pop("_t", None)
                if t == "relation":
                    graph.add_relation(OrgRelation.from_dict(record))
        return graph

    def content_digest(self) -> str:
        """SHA-256 digest of graph content."""
        h = hashlib.sha256()
        for node in sorted(self._nodes.values(), key=lambda n: n.id):
            h.update(node.id.encode())
            h.update(node.name.encode())
        for rel in sorted(
            self._relations,
            key=lambda r: (r.source_id, r.target_id, r.relation.value),
        ):
            h.update(f"{rel.source_id}:{rel.target_id}:{rel.relation.value}".encode())
        return h.hexdigest()

    # ── Factory helpers ──

    @classmethod
    def demo(cls) -> OrgGraph:
        """Create a demo graph with sample data for testing."""
        g = cls()

        # Sample organizations
        g.add_node(OrgNode(
            id="org-mwr",
            node_type=OrgNodeType.ORGANIZATION,
            name="水利部",
            tags=["central_gov", "water_resources"],
        ))
        g.add_node(OrgNode(
            id="org-mwr-yz",
            node_type=OrgNodeType.ORGANIZATION,
            name="水利部淮河水利委员会",
            tags=["river_basin", "huaihe"],
        ))

        # Sample persons
        g.add_node(OrgNode(
            id="person-zhang",
            node_type=OrgNodeType.PERSON,
            name="张三",
            title="淮河水利委员会主任",
            summary="关注防洪工程与水资源管理，偏好数据驱动的决策报告",
            tags=["decision_maker", "huaihe"],
        ))
        g.add_node(OrgNode(
            id="person-li",
            node_type=OrgNodeType.PERSON,
            name="李四",
            title="水利部水资源司副司长",
            summary="侧重节水政策与跨流域调水",
            tags=["policy_maker"],
        ))

        # Sample document
        g.add_node(OrgNode(
            id="doc-2024-038",
            node_type=OrgNodeType.DOCUMENT,
            name="关于淮河流域防洪工程验收的函",
            title="水建管〔2024〕38号",
            summary="淮河水利委员会提交防洪工程竣工验收申请",
            tags=["acceptance", "huaihe"],
        ))

        # Relations
        g.add_relation(OrgRelation(
            source_id="person-zhang",
            target_id="org-mwr-yz",
            relation=OrgRelationType.HOLDS_POSITION,
            weight=1.0,
        ))
        g.add_relation(OrgRelation(
            source_id="person-li",
            target_id="org-mwr",
            relation=OrgRelationType.HOLDS_POSITION,
            weight=1.0,
        ))
        g.add_relation(OrgRelation(
            source_id="org-mwr-yz",
            target_id="doc-2024-038",
            relation=OrgRelationType.SENT_DOCUMENT,
            weight=1.0,
        ))
        g.add_relation(OrgRelation(
            source_id="person-zhang",
            target_id="org-mwr",
            relation=OrgRelationType.COMMUNICATED,
            weight=1.0,
            first_contact="2024-03-01T10:00:00+00:00",
            last_contact="2024-06-15T14:30:00+00:00",
            frequency=5,
        ))

        return g


__all__ = [
    "HALF_LIFE_DAYS",
    "COMMUNICATED",
    "OrgGraph",
    "OrgNode",
    "OrgNodeType",
    "OrgRelation",
    "OrgRelationType",
]

# Module-level constants for convenience
COMMUNICATED = OrgRelationType.COMMUNICATED
