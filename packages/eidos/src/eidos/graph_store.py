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
    confidence: float = 1.0


@dataclass
class Entity:
    """A knowledge graph entity."""

    id: str
    name: str = ""
    entity_type: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    source_files: list[str] = field(default_factory=list)
    merged_from: list[str] = field(default_factory=list)
    created_at: str = ""
    confidence: float = 1.0
    timestamp: str = ""
    entity_id: str = ""
    is_canonical: bool = True

    def __post_init__(self) -> None:
        if self.entity_id and not self.id:
            self.id = self.entity_id
        elif self.id and not self.entity_id:
            self.entity_id = self.id


@dataclass
class Relation:
    """A knowledge graph relation."""

    id: str = ""
    source_id: str = ""
    target_id: str = ""
    relation_type: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    source_files: list[str] = field(default_factory=list)
    confidence: float = 1.0
    relation_id: str = ""
    merged_from: list[str] = field(default_factory=list)
    created_at: str = ""
    is_canonical: bool = True


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

    def ping(self) -> bool:
        """Check if the graph store is reachable."""
        return True

    def get_relations_for_entity(self, entity_id: str, direction: str | None = None) -> list[Relation]:
        """Get all relations for a given entity."""
        return []

    def search_entities(self, limit: int = 100, name_pattern: str | None = None) -> list[Entity]:
        """Search entities in the graph store."""
        return []

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID (stub)."""
        return None

    def get_relation(self, relation_id: str) -> Relation | None:
        """Get a relation by ID (stub)."""
        return None

    def clear_candidates(self, source_file: str = "") -> None:
        """Clear candidate entities/relations (stub)."""

    def add_candidate_entity(self, entity: Any) -> None:
        """Add a candidate entity (stub)."""

    def add_candidate_relation(self, relation: Any) -> None:
        """Add a candidate relation (stub)."""

    def get_candidate_entities(self, *args: Any, **kwargs: Any) -> list[Any]:
        """Get candidate entities (stub)."""
        return []

    def get_candidate_relations(self, *args: Any, **kwargs: Any) -> list[Any]:
        """Get candidate relations (stub)."""
        return []

    def _get_connection(self) -> None:
        """Get DB connection (stub)."""
        return None


__all__ = [
    "CandidateEntity",
    "CandidateRelation",
    "Entity",
    "Relation",
    "GraphStore",
]
