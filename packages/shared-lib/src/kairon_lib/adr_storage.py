from __future__ import annotations

"""
---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Updated: 2026-03-08
Authority: 4
Keywords: [adr, decision, sqlite, governance, persistence]
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# SQLiteADRStorage ≡ Organ
# 内涵 ≝ {id, title, status, context, decision, consequences, author}
# 外延 ≝ {a | a ∈ D-Governance ∧ adr_record(a)}
# 功能 ⊢ {CreateADR, GetADR, ListADRs, UpdateADR, TransitionADR, SearchADR}
# =============================================================================

import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from nucleus.Z_Microkernel.utilities.sqlite_utils import managed_connection

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ADR status constants
# ---------------------------------------------------------------------------

ADR_DRAFT = "DRAFT"
ADR_REVIEW = "REVIEW"
ADR_DECIDED = "DECIDED"
ADR_ACCEPTED = "ACCEPTED"  # Alias for DECIDED — same semantic, alternate vocabulary
ADR_SUPERSEDED = "SUPERSEDED"

_VALID_STATUSES: frozenset[str] = frozenset({ADR_DRAFT, ADR_REVIEW, ADR_DECIDED, ADR_ACCEPTED, ADR_SUPERSEDED})

# Allowed forward/backward transitions.
# ACCEPTED is treated as an alias for DECIDED (both have identical transition rules).
# DECIDED/ACCEPTED → REVIEW is a "re-evaluation" path: a previously decided ADR
# may need to go back for re-review when new information changes the context.
_TRANSITIONS: dict[str, frozenset[str]] = {
    ADR_DRAFT: frozenset({ADR_REVIEW}),
    ADR_REVIEW: frozenset({ADR_DECIDED, ADR_ACCEPTED, ADR_DRAFT}),
    ADR_DECIDED: frozenset({ADR_SUPERSEDED, ADR_REVIEW}),  # re-evaluation path
    ADR_ACCEPTED: frozenset({ADR_SUPERSEDED, ADR_REVIEW}),  # same as DECIDED
    ADR_SUPERSEDED: frozenset(),
}

# ---------------------------------------------------------------------------
# ADRRecord dataclass
# ---------------------------------------------------------------------------


@dataclass
class ADRRecord:
    """Represents a single Architecture Decision Record."""

    id: str
    title: str
    status: str  # DRAFT | REVIEW | DECIDED | SUPERSEDED
    context: str
    decision: str
    consequences: str
    author: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "context": self.context,
            "decision": self.decision,
            "consequences": self.consequences,
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# SQLiteADRStorage
# ---------------------------------------------------------------------------


class SQLiteADRStorage:
    """SQLite-backed storage for Architecture Decision Records (ADRs).

    Lifecycle:  DRAFT → REVIEW → DECIDED → SUPERSEDED

    DB path (default): ``data/db/governance/adrs.db``
    resolved relative to ``$BOS_ROOT`` (or ``.`` if unset).

    Full-text search is provided via SQLite FTS5; falls back to LIKE on
    environments where FTS5 is unavailable.
    """

    _DEFAULT_DB: str = "data/db/governance/adrs.db"
    _lock: threading.Lock = threading.Lock()

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._fts_available: bool = True  # updated in _init_db
        self._init_db()
        _log.debug("[SQLiteADRStorage] db=%s fts=%s", self._db_path, self._fts_available)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return managed_connection(conn)

    def _init_db(self) -> None:
        with self._connect() as conn:
            # Main ADR table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS adrs (
                    id           TEXT PRIMARY KEY,
                    title        TEXT NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'DRAFT',
                    context      TEXT NOT NULL DEFAULT '',
                    decision     TEXT NOT NULL DEFAULT '',
                    consequences TEXT NOT NULL DEFAULT '',
                    author       TEXT NOT NULL DEFAULT '@Prime',
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                )
                """
            )
            # FTS5 full-text search table
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS adrs_fts
                    USING fts5(
                        id UNINDEXED,
                        title,
                        context,
                        decision,
                        consequences,
                        content='adrs',
                        content_rowid='rowid'
                    )
                    """
                )
                # Sync triggers
                conn.executescript(
                    """
                    CREATE TRIGGER IF NOT EXISTS adrs_fts_ai
                    AFTER INSERT ON adrs BEGIN
                        INSERT INTO adrs_fts(rowid, id, title, context, decision, consequences)
                        VALUES (new.rowid, new.id, new.title, new.context, new.decision, new.consequences);
                    END;

                    CREATE TRIGGER IF NOT EXISTS adrs_fts_au
                    AFTER UPDATE ON adrs BEGIN
                        INSERT INTO adrs_fts(adrs_fts, rowid, id, title, context, decision, consequences)
                        VALUES ('delete', old.rowid, old.id, old.title, old.context, old.decision, old.consequences);
                        INSERT INTO adrs_fts(rowid, id, title, context, decision, consequences)
                        VALUES (new.rowid, new.id, new.title, new.context, new.decision, new.consequences);
                    END;

                    CREATE TRIGGER IF NOT EXISTS adrs_fts_ad
                    AFTER DELETE ON adrs BEGIN
                        INSERT INTO adrs_fts(adrs_fts, rowid, id, title, context, decision, consequences)
                        VALUES ('delete', old.rowid, old.id, old.title, old.context, old.decision, old.consequences);
                    END;
                    """
                )
            except sqlite3.OperationalError:
                _log.warning("[SQLiteADRStorage] FTS5 unavailable; falling back to LIKE search")
                self._fts_available = False

            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ADRRecord:
        return ADRRecord(
            id=row["id"],
            title=row["title"],
            status=row["status"],
            context=row["context"],
            decision=row["decision"],
            consequences=row["consequences"],
            author=row["author"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        title: str,
        context: str,
        author: str = "@Prime",
    ) -> ADRRecord:
        """Create a new ADR in DRAFT status and return it."""
        now = self._now()
        adr_id = f"ADR-{uuid.uuid4().hex[:8].upper()}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO adrs
                    (id, title, status, context, decision, consequences, author, created_at, updated_at)
                VALUES (?, ?, 'DRAFT', ?, '', '', ?, ?, ?)
                """,
                (adr_id, title, context, author, now, now),
            )
            conn.commit()
        record = self.get(adr_id)
        assert record is not None
        return record

    def get(self, adr_id: str) -> ADRRecord | None:
        """Retrieve an ADR by ID, or *None* if not found."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM adrs WHERE id = ?", (adr_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def list(self, status: str | None = None) -> list[ADRRecord]:
        """Return all ADRs, optionally filtered by *status*."""
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM adrs WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM adrs ORDER BY created_at DESC").fetchall()
        return [self._row_to_record(r) for r in rows]

    def update(
        self,
        adr_id: str,
        decision: str = "",
        consequences: str = "",
    ) -> bool:
        """Set *decision* and/or *consequences* on an existing ADR."""
        now = self._now()
        with self._lock, self._connect() as conn:
            res = conn.execute(
                """
                UPDATE adrs
                SET decision = ?, consequences = ?, updated_at = ?
                WHERE id = ?
                """,
                (decision, consequences, now, adr_id),
            )
            conn.commit()
        return res.rowcount > 0

    def transition(self, adr_id: str, new_status: str) -> bool:
        """Advance the ADR to *new_status* if the transition is allowed.

        *new_status* is normalised to upper-case before validation so that
        callers may pass ``"accepted"``, ``"Decided"``, etc.

        Valid transitions::

            DRAFT → REVIEW → DECIDED → SUPERSEDED
            DRAFT → REVIEW → ACCEPTED → SUPERSEDED  (ACCEPTED is an alias for DECIDED)
            REVIEW → DRAFT          (send back for rework)
            DECIDED → REVIEW        (re-evaluation when new information emerges)
            ACCEPTED → REVIEW       (re-evaluation — same as DECIDED)
        """
        new_status = new_status.upper()
        if new_status not in _VALID_STATUSES:
            _log.warning("[SQLiteADRStorage] Unknown status: %s", new_status)
            return False
        record = self.get(adr_id)
        if record is None:
            return False
        allowed = _TRANSITIONS.get(record.status, frozenset())
        if new_status not in allowed:
            _log.warning(
                "[SQLiteADRStorage] Transition %s → %s not allowed",
                record.status,
                new_status,
            )
            return False
        now = self._now()
        with self._lock, self._connect() as conn:
            res = conn.execute(
                "UPDATE adrs SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, adr_id),
            )
            conn.commit()
        return res.rowcount > 0

    def search(self, query: str) -> list[ADRRecord]:
        """Full-text search across title/context/decision/consequences.

        Uses FTS5 when available; falls back to LIKE on all text columns.
        """
        with self._connect() as conn:
            if self._fts_available:
                try:
                    rows = conn.execute(
                        """
                        SELECT adrs.* FROM adrs
                        JOIN adrs_fts ON adrs.rowid = adrs_fts.rowid
                        WHERE adrs_fts MATCH ?
                        ORDER BY rank
                        """,
                        (query,),
                    ).fetchall()
                    return [self._row_to_record(r) for r in rows]
                except sqlite3.OperationalError:
                    self._fts_available = False

            # LIKE fallback
            like = f"%{query}%"
            rows = conn.execute(
                """
                SELECT * FROM adrs
                WHERE title LIKE ?
                   OR context LIKE ?
                   OR decision LIKE ?
                   OR consequences LIKE ?
                ORDER BY created_at DESC
                """,
                (like, like, like, like),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]
