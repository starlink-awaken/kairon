"""Versioned, evidence-backed persistence for the KEMS knowledge graph.

The store intentionally uses a small relational schema.  SQLite is the local
implementation; the domain objects and SQL boundaries are portable to the
production PostgreSQL adapter described in the KEMS production plan.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ReviewState = Literal["machine", "pending", "human_verified", "rejected"]


@dataclass(frozen=True)
class GraphEntity:
    entity_id: str
    entity_type: str
    canonical_name: str
    source_document_id: str
    source_version_id: str
    evidence_span: str
    confidence: float
    review_state: ReviewState = "machine"
    valid_from: str | None = None
    valid_to: str | None = None
    created_by_run: str | None = None


@dataclass(frozen=True)
class GraphRelation:
    relation_id: str
    subject_id: str
    predicate: str
    object_id: str
    source_document_id: str
    source_version_id: str
    evidence_refs: tuple[str, ...]
    confidence: float
    review_state: ReviewState = "machine"
    valid_from: str | None = None
    valid_to: str | None = None
    created_by_run: str | None = None


@dataclass(frozen=True)
class EvidenceSpan:
    evidence_id: str
    document_id: str
    version_id: str
    locator: str
    quote: str
    extractor: str
    confidence: float
    created_by_run: str | None = None


@dataclass(frozen=True)
class DocumentVersion:
    document_id: str
    version_id: str
    source_sha256: str
    domain: str
    text: str
    sensitivity: str = "internal"
    review_state: ReviewState = "pending"
    run_id: str | None = None


class GraphStore:
    """SQLite graph store with idempotent writes and explicit provenance."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS document_versions (
                    document_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    text TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    review_state TEXT NOT NULL,
                    run_id TEXT,
                    PRIMARY KEY (document_id, version_id),
                    UNIQUE (source_sha256)
                );
                CREATE TABLE IF NOT EXISTS evidence_spans (
                    evidence_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    extractor TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    created_by_run TEXT,
                    FOREIGN KEY (document_id, version_id)
                        REFERENCES document_versions(document_id, version_id)
                );
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    source_document_id TEXT NOT NULL,
                    source_version_id TEXT NOT NULL,
                    evidence_span TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    review_state TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    created_by_run TEXT,
                    FOREIGN KEY (source_document_id, source_version_id)
                        REFERENCES document_versions(document_id, version_id)
                );
                CREATE TABLE IF NOT EXISTS relations (
                    relation_id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL REFERENCES entities(entity_id),
                    predicate TEXT NOT NULL,
                    object_id TEXT NOT NULL REFERENCES entities(entity_id),
                    source_document_id TEXT NOT NULL,
                    source_version_id TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    review_state TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    created_by_run TEXT,
                    FOREIGN KEY (source_document_id, source_version_id)
                        REFERENCES document_versions(document_id, version_id)
                );
                CREATE TABLE IF NOT EXISTS extraction_runs (
                    run_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    source_sha256 TEXT,
                    model_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS review_decisions (
                    decision_id TEXT PRIMARY KEY,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name);
                CREATE INDEX IF NOT EXISTS idx_entities_source ON entities(source_document_id, source_version_id);
                CREATE INDEX IF NOT EXISTS idx_relations_subject ON relations(subject_id);
                CREATE INDEX IF NOT EXISTS idx_relations_object ON relations(object_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_document ON evidence_spans(document_id, version_id);
                """
            )

    def put_document_version(self, document: DocumentVersion) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO document_versions
                (document_id, version_id, source_sha256, domain, text, sensitivity, review_state, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id, version_id) DO UPDATE SET
                    text=excluded.text, sensitivity=excluded.sensitivity,
                    review_state=excluded.review_state, run_id=excluded.run_id""",
                tuple(document.__dict__.values()),
            )

    def add_evidence(self, evidence: EvidenceSpan) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO evidence_spans
                (evidence_id, document_id, version_id, locator, quote, extractor, confidence, created_by_run)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evidence_id) DO UPDATE SET quote=excluded.quote,
                    locator=excluded.locator, confidence=excluded.confidence""",
                tuple(evidence.__dict__.values()),
            )

    def add_entity(self, entity: GraphEntity) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET canonical_name=excluded.canonical_name,
                    confidence=excluded.confidence, review_state=excluded.review_state,
                    valid_to=excluded.valid_to""",
                tuple(entity.__dict__.values()),
            )

    def add_relation(self, relation: GraphRelation) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO relations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(relation_id) DO UPDATE SET evidence_refs=excluded.evidence_refs,
                    confidence=excluded.confidence, review_state=excluded.review_state,
                    valid_to=excluded.valid_to""",
                (
                    relation.relation_id,
                    relation.subject_id,
                    relation.predicate,
                    relation.object_id,
                    relation.source_document_id,
                    relation.source_version_id,
                    json.dumps(relation.evidence_refs),
                    relation.confidence,
                    relation.review_state,
                    relation.valid_from,
                    relation.valid_to,
                    relation.created_by_run,
                ),
            )

    def record_extraction_run(
        self,
        *,
        run_id: str,
        scenario_id: str,
        source_sha256: str | None,
        model_id: str,
        status: str,
        evidence_refs: Iterable[str],
        created_at: str,
    ) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO extraction_runs VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET status=excluded.status,
                    evidence_refs=excluded.evidence_refs""",
                (run_id, scenario_id, source_sha256, model_id, status, json.dumps(list(evidence_refs)), created_at),
            )

    def record_review(
        self,
        *,
        decision_id: str,
        target_type: str,
        target_id: str,
        decision: str,
        reviewer: str,
        reason: str,
        created_at: str,
    ) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO review_decisions VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_id) DO UPDATE SET decision=excluded.decision,
                    reason=excluded.reason""",
                (decision_id, target_type, target_id, decision, reviewer, reason, created_at),
            )

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
        return dict(row) if row else None

    def list_evidence(self, document_id: str, version_id: str) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM evidence_spans WHERE document_id = ? AND version_id = ? ORDER BY evidence_id",
                (document_id, version_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def export_snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """Return a deterministic, redaction-ready graph snapshot."""
        self.initialize()
        with self._connect() as connection:
            result: dict[str, list[dict[str, Any]]] = {}
            for table in ("document_versions", "evidence_spans", "entities", "relations"):
                rows = connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                result[table] = [dict(row) for row in rows]
        return result
