from __future__ import annotations

"""System architecture modeling tools — C4Model and ADRManager.

Migrated from agentmesh/packages/toolkit/src/architecture/.
FormalMethod moved to formal_method.py.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# C4 Model
# ---------------------------------------------------------------------------

class C4ElementType(Enum):
    CONTEXT = "context"
    CONTAINER = "container"
    COMPONENT = "component"
    CODE = "code"


@dataclass
class C4Element:
    id: str
    type: C4ElementType
    name: str
    description: str
    technology: str | None = None
    children: list[C4Element] = field(default_factory=list)


@dataclass
class C4Relation:
    source_id: str
    target_id: str
    description: str
    technology: str | None = None


class C4Model:
    """C4 architecture diagram builder (Context/Container/Component)."""

    def __init__(self, title: str = "System Architecture", description: str = "") -> None:
        self._title = title
        self._description = description
        self._elements: dict[str, C4Element] = {}
        self._relations: list[C4Relation] = []

    @staticmethod
    def _slug(name: str) -> str:
        return re.sub(r"\s+", "-", name.lower())

    def add_context(self, name: str, description: str, technology: str | None = None) -> C4Model:
        self._elements[f"context-{self._slug(name)}"] = C4Element(
            id=f"context-{self._slug(name)}", type=C4ElementType.CONTEXT, name=name, description=description, technology=technology,
        )
        return self

    def add_container(self, name: str, description: str, technology: str | None = None) -> C4Model:
        self._elements[f"container-{self._slug(name)}"] = C4Element(
            id=f"container-{self._slug(name)}", type=C4ElementType.CONTAINER, name=name, description=description, technology=technology,
        )
        return self

    def add_component(self, name: str, description: str, technology: str | None = None, container_id: str | None = None) -> C4Model:
        el = C4Element(id=f"component-{self._slug(name)}", type=C4ElementType.COMPONENT, name=name, description=description, technology=technology)
        if container_id and container_id in self._elements:
            self._elements[container_id].children.append(el)
        self._elements[el.id] = el
        return self

    def add_relation(self, source: str, target: str, description: str, technology: str | None = None) -> C4Model:
        slug = self._slug
        sid = next((eid for eid in self._elements if slug(source) in eid), None)
        tid = next((eid for eid in self._elements if slug(target) in eid), None)
        if sid is None or tid is None:
            raise ValueError(f"Element not found: {source if sid is None else target}")
        self._relations.append(C4Relation(sid, tid, description, technology))
        return self

    def to_json(self) -> dict[str, Any]:
        return {"title": self._title, "description": self._description, "elements": [e.__dict__ for e in self._elements.values()], "relations": [r.__dict__ for r in self._relations]}


# ---------------------------------------------------------------------------
# ADR Manager
# ---------------------------------------------------------------------------

class ADRStatus(Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


@dataclass
class ADRRecord:
    id: str
    title: str
    status: ADRStatus
    context: str
    decision: str
    consequences: list[str]
    supersedes: str | None = None
    superseded_by: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    author: str | None = None
    tags: list[str] = field(default_factory=list)


class ADRManager:
    """Architecture Decision Record lifecycle manager."""

    def __init__(self) -> None:
        self._records: dict[str, ADRRecord] = {}

    def create(self, record: ADRRecord) -> ADRRecord:
        if record.supersedes and record.supersedes in self._records:
            self._records[record.supersedes].status = ADRStatus.SUPERSEDED
            self._records[record.supersedes].superseded_by = record.id
        self._records[record.id] = record
        return record

    def get(self, id: str) -> ADRRecord | None:
        return self._records.get(id)

    def delete(self, id: str) -> bool:
        return self._records.pop(id, None) is not None

    def list_all(self) -> list[ADRRecord]:
        return list(self._records.values())

    def search(self, keyword: str | None = None, status: ADRStatus | None = None, tags: list[str] | None = None) -> list[ADRRecord]:
        results = list(self._records.values())
        if status is not None:
            results = [r for r in results if r.status == status]
        if tags:
            results = [r for r in results if any(t in r.tags for t in tags)]
        if keyword:
            kw = keyword.lower()
            results = [r for r in results if kw in r.title.lower() or kw in r.context.lower() or kw in r.decision.lower()]
        return results

    def get_active(self) -> list[ADRRecord]:
        return [r for r in self._records.values() if r.status in (ADRStatus.PROPOSED, ADRStatus.ACCEPTED)]

    def get_latest(self, count: int = 10) -> list[ADRRecord]:
        return sorted(self._records.values(), key=lambda r: r.created_at, reverse=True)[:count]
