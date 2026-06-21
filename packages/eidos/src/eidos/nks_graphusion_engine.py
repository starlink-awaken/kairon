from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from eidos.graph_store import (  # type: ignore[import-not-found]
    CandidateEntity,
    CandidateRelation,
    Entity,
    GraphStore,
    Relation,
)

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "Fusion must be idempotent and preserve all source information"
Summary: "GraphusionEngine - Layer S: Knowledge graph fusion and merging"
Tags:
- nks
- knowledge-fusion
- entity-merging
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Graphusion Engine ≡ Engine
# 内涵 ≝ {Graphusion, Engine}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, GraphusionEngine)}
# 功能 ⊢ {Graphusion_Engine, Init_Graphusion, Validate_Engine}
# =============================================================================

_log = logging.getLogger(__name__)


@dataclass
class FusionResult:
    """Result of a fusion operation."""

    entities_merged: int = 0
    entities_created: int = 0
    relations_merged: int = 0
    relations_created: int = 0
    conflicts_resolved: int = 0
    duration_seconds: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ConflictResolution:
    """Record of a conflict resolution."""

    conflict_type: str  # 'entity_name', 'entity_property', 'relation'
    item_id: str
    description: str
    resolution: str  # 'keep_canonical', 'merge', 'create_new'
    timestamp: float = field(default_factory=time.time)


class EntityMatcher:
    """Strategy for matching candidate entities to canonical entities."""

    @staticmethod
    def exact_name_match(candidate: CandidateEntity, canonical: Entity) -> float:
        """Exact name match returns 1.0."""
        return 1.0 if candidate.name.lower() == canonical.name.lower() else 0.0

    @staticmethod
    def fuzzy_name_match(candidate: CandidateEntity, canonical: Entity, threshold: float = 0.8) -> float:
        """
        Fuzzy name match using Levenshtein-like comparison.

        Simple implementation - for production use difflib or similar.
        """
        cand_name = candidate.name.lower()
        canon_name = canonical.name.lower()

        # Simple character overlap ratio
        cand_chars = set(cand_name)
        canon_chars = set(canon_name)

        if not cand_chars or not canon_chars:
            return 0.0

        intersection = cand_chars & canon_chars
        union = cand_chars | canon_chars
        overlap = len(intersection) / len(union)

        return overlap if overlap >= threshold else 0.0

    @staticmethod
    def embedding_similarity(candidate: CandidateEntity, canonical: Entity, threshold: float = 0.85) -> float:
        """Compare entity embeddings if available."""
        if not candidate.embedding or "embedding" not in canonical.properties:
            return 0.0

        cand_emb = candidate.embedding
        canon_emb = canonical.properties["embedding"]

        if len(cand_emb) != len(canon_emb):
            return 0.0

        # Cosine similarity
        dot = sum(a * b for a, b in zip(cand_emb, canon_emb, strict=False))
        norm_a = sum(a * a for a in cand_emb) ** 0.5
        norm_b = sum(b * b for b in canon_emb) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        similarity = dot / (norm_a * norm_b)
        return similarity if similarity >= threshold else 0.0


class GraphusionEngine:
    """
    GraphusionEngine - Layer S of NKS

    Handles the fusion of candidate knowledge (from extractors) into
    the canonical global knowledge graph. Implements conflict detection,
    entity merging, and relation resolution.
    """

    def __init__(self, graph_store: GraphStore) -> None:
        """
        Initialize GraphusionEngine.

        Args:
            graph_store: GraphStore instance for persistence
        """

        self.graph_store = graph_store
        self.matcher = EntityMatcher()
        self._deduct_metabolic_tax(amount=5.0)

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount

    def _generate_entity_id(self, name: str) -> str:
        """Generate a stable canonical entity ID from name."""
        return hashlib.sha256(name.lower().encode()).hexdigest()[:16]

    def _generate_relation_id(self, source_id: str, target_id: str, relation_type: str) -> str:
        """Generate a stable relation ID."""
        input_str = f"{source_id}:{target_id}:{relation_type}"
        return hashlib.sha256(input_str.encode()).hexdigest()[:16]

    def find_best_match(
        self, candidate: CandidateEntity, match_strategies: list[Callable] | None = None
    ) -> Entity | None:
        """
        Find the best matching canonical entity for a candidate.

        Args:
            candidate: Candidate entity to match
            match_strategies: List of matching functions (default: exact + fuzzy)

        Returns:
            Best matching Entity or None
        """
        if match_strategies is None:
            match_strategies = [
                self.matcher.exact_name_match,
                lambda c, e: self.matcher.fuzzy_name_match(c, e, threshold=0.8),
            ]

        # Search canonical entities by name
        canonical_entities = self.graph_store.search_entities(name_pattern=f"%{candidate.name}%", limit=50)

        best_match = None
        best_score = 0.0

        for canonical in canonical_entities:
            for strategy in match_strategies:
                score = strategy(candidate, canonical)
                if score > best_score:
                    best_score = score
                    best_match = canonical

        # Return only if confidence is high enough
        return best_match if best_score >= 0.8 else None

    def merge_entity(self, candidate: CandidateEntity, canonical: Entity) -> Entity:
        """
        Merge a candidate entity into a canonical entity.

        Strategy:
        - Keep canonical name
        - Merge properties (candidate overrides if not present)
        - Track source files
        - Record merged_from

        Args:
            candidate: Candidate entity to merge
            canonical: Canonical entity to merge into

        Returns:
            Updated canonical Entity
        """
        merged_properties = canonical.properties.copy()

        # Merge properties
        for key, value in candidate.properties.items():
            if key not in merged_properties:
                merged_properties[key] = value

        # Track source
        if candidate.source_file not in canonical.source_files:
            canonical.source_files.append(candidate.source_file)

        # Record merge
        if candidate.entity_id not in canonical.merged_from:
            canonical.merged_from.append(candidate.entity_id)

        # Create merged entity
        merged = Entity(
            entity_id=canonical.entity_id,
            name=canonical.name,
            properties=merged_properties,
            source_files=canonical.source_files,
            merged_from=canonical.merged_from,
            is_canonical=True,
            created_at=canonical.created_at,
        )

        # Update in store
        self.graph_store.add_entity(merged)

        return merged

    def create_canonical_entity(self, candidate: CandidateEntity) -> Entity:
        """
        Create a new canonical entity from a candidate.

        Args:
            candidate: Candidate entity

        Returns:
            New canonical Entity
        """
        entity_id = self._generate_entity_id(candidate.name)

        return Entity(
            entity_id=entity_id,
            name=candidate.name,
            properties=candidate.properties.copy(),
            source_files=[candidate.source_file] if candidate.source_file else [],
            merged_from=[],
            is_canonical=True,
            created_at=str(time.time()),
        )

    def resolve_relation(self, candidate: CandidateRelation, entity_id_map: dict[str, str]) -> Relation | None:
        """
        Resolve a candidate relation to canonical entity IDs.

        Args:
            candidate: Candidate relation
            entity_id_map: Mapping from candidate entity IDs to canonical IDs

        Returns:
            Canonical Relation or None if entities don't exist
        """
        # Get canonical entity IDs
        source_canonical_id = entity_id_map.get(candidate.source_id)
        target_canonical_id = entity_id_map.get(candidate.target_id)

        if not source_canonical_id or not target_canonical_id:
            return None

        # Check if entities exist
        if not self.graph_store.get_entity(source_canonical_id):
            return None
        if not self.graph_store.get_entity(target_canonical_id):
            return None

        # Check if relation already exists
        existing_relations = self.graph_store.get_relations_for_entity(source_canonical_id, direction="outgoing")

        for existing in existing_relations:
            if existing.target_id == target_canonical_id and existing.relation_type == candidate.relation_type:
                # Merge with existing
                merged_properties = existing.properties.copy()
                for key, value in candidate.properties.items():
                    if key not in merged_properties:
                        merged_properties[key] = value

                # Track source file
                if candidate.source_file not in existing.source_files:
                    existing.source_files.append(candidate.source_file)

                # Update confidence (max of both)
                existing.confidence = max(existing.confidence, candidate.confidence)

                updated = Relation(
                    relation_id=existing.relation_id,
                    source_id=existing.source_id,
                    target_id=existing.target_id,
                    relation_type=existing.relation_type,
                    properties=merged_properties,
                    source_files=existing.source_files,
                    confidence=existing.confidence,
                    is_canonical=True,
                    created_at=existing.created_at,
                )

                self.graph_store.add_relation(updated)
                return updated

        # Create new relation
        relation_id = self._generate_relation_id(source_canonical_id, target_canonical_id, candidate.relation_type)

        return Relation(
            relation_id=relation_id,
            source_id=source_canonical_id,
            target_id=target_canonical_id,
            relation_type=candidate.relation_type,
            properties=candidate.properties.copy(),
            source_files=[candidate.source_file] if candidate.source_file else [],
            confidence=candidate.confidence,
            is_canonical=True,
            created_at=str(time.time()),
        )

    def fuse(
        self,
        source_file: str | None = None,
        match_strategies: list[Callable] | None = None,
        verbose: bool = False,
    ) -> FusionResult:
        """
        Perform complete fusion of candidate entities and relations.

        Args:
            source_file: Optional filter for specific source file
            match_strategies: Optional custom matching strategies
            verbose: Enable verbose logging

        Returns:
            FusionResult with statistics
        """
        start_time = time.time()
        result = FusionResult()
        entity_id_map: dict[str, str] = {}

        # Get candidate entities
        candidates = self.graph_store.get_candidate_entities(source_file)

        if verbose:
            _log.info("Found {len(candidates)} candidate entities")

        # Phase 1: Fuse entities
        for candidate in candidates:
            best_match = self.find_best_match(candidate, match_strategies)

            if best_match:
                # Merge into existing canonical entity
                merged = self.merge_entity(candidate, best_match)
                entity_id_map[candidate.entity_id] = merged.entity_id
                result.entities_merged += 1

                if verbose:
                    _log.info("  Merged: {candidate.name} -> {merged.name}")
            else:
                # Create new canonical entity
                new_entity = self.create_canonical_entity(candidate)
                self.graph_store.add_entity(new_entity)
                entity_id_map[candidate.entity_id] = new_entity.entity_id
                result.entities_created += 1

                if verbose:
                    _log.info("  Created: {new_entity.name}")

        # Phase 2: Fuse relations
        candidate_relations = self.graph_store.get_candidate_relations(source_file)

        if verbose:
            _log.info("Found {len(candidate_relations)} candidate relations")

        for candidate_rel in candidate_relations:
            canonical_rel = self.resolve_relation(candidate_rel, entity_id_map)

            if canonical_rel:
                # Check if it's new or merged
                existing = self.graph_store.get_relation(canonical_rel.relation_id)
                if existing and existing.created_at < canonical_rel.created_at:
                    result.relations_merged += 1
                    if verbose:
                        _log.info("  Merged relation: {candidate_rel.relation_type}")
                else:
                    result.relations_created += 1
                    if verbose:
                        _log.info("  Created relation: {candidate_rel.relation_type}")

        # Cleanup
        if source_file:
            self.graph_store.clear_candidates(source_file)

        result.duration_seconds = time.time() - start_time

        return result

    def fuse_batch(
        self,
        candidates: list[CandidateEntity],
        relations: list[CandidateRelation],
        match_strategies: list[Callable] | None = None,
    ) -> FusionResult:
        """
        Fuse a batch of candidates (bypass GraphStore storage).

        Useful for real-time fusion without persistence overhead.

        Args:
            candidates: List of candidate entities
            relations: List of candidate relations
            match_strategies: Optional custom matching strategies

        Returns:
            FusionResult with statistics
        """
        start_time = time.time()
        result = FusionResult()
        entity_id_map: dict[str, str] = {}

        # Phase 1: Fuse entities
        for candidate in candidates:
            best_match = self.find_best_match(candidate, match_strategies)

            if best_match:
                merged = self.merge_entity(candidate, best_match)
                entity_id_map[candidate.entity_id] = merged.entity_id
                result.entities_merged += 1
            else:
                new_entity = self.create_canonical_entity(candidate)
                self.graph_store.add_entity(new_entity)
                entity_id_map[candidate.entity_id] = new_entity.entity_id
                result.entities_created += 1

        # Phase 2: Fuse relations
        for candidate_rel in relations:
            canonical_rel = self.resolve_relation(candidate_rel, entity_id_map)

            if canonical_rel:
                existing = self.graph_store.get_relation(canonical_rel.relation_id)
                if existing and existing.created_at < canonical_rel.created_at:
                    result.relations_merged += 1
                else:
                    result.relations_created += 1

        result.duration_seconds = time.time() - start_time

        return result

    def ping(self) -> bool:
        """Health check for GraphusionEngine."""
        try:
            return self.graph_store.ping()
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return False
