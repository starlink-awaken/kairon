"""Graph store — entity and relation data models for NKS pipeline.

TODO: implement full graph storage backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CandidateEntity:
    """A candidate entity extracted during NKS pipeline processing."""
    entity_id: str
    name: str
    properties: dict = field(default_factory=dict)
    source_file: str = ""
    embedding: list[float] | None = None


@dataclass
class CandidateRelation:
    """A candidate relation extracted during NKS pipeline processing."""
    source_id: str
    target_id: str
    relation_type: str
    properties: dict = field(default_factory=dict)
    source_file: str = ""
    weight: float = 1.0


@dataclass
class Entity:
    """A knowledge graph entity."""
    id: str
    name: str
    entity_type: str = ""
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class Relation:
    """A knowledge graph relation."""
    id: str
    source_id: str
    target_id: str
    relation_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0


class GraphStore:
    """Graph store interface for NKS pipeline.

    TODO: implement full graph storage backend.
    """

    def __init__(self, db_path: str = "") -> None:
        self.db_path = db_path

    def query(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Query entities/relations from the graph store."""
        return []

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to the graph store."""

    def add_relation(self, relation: Relation) -> None:
        """Add a relation to the graph store."""


__all__ = [
    "CandidateEntity",
    "CandidateRelation",
    "Entity",
    "Relation",
    "GraphStore",
]
