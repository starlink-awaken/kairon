from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
"""
---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Updated: 2026-03-10
Authority: 4
Keywords: [retrospective, lessons, governance, sqlite, reflection]
---

RetrospectiveEngine — records and queries project retrospectives.
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# RetrospectiveEngine ≡ Organ
# 内涵 ≝ {id, iteration_id, what_worked, what_failed, lessons, recommendations}
# 外延 ≝ {e | e ∈ D-Governance ∧ retro_entry(e)}
# 功能 ⊢ {Record, Get, ListRecent, Search, GenerateSummary}
# =============================================================================
import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kairon_lib._compat import managed_connection

_log = logging.getLogger(__name__)

__all__ = [
    "RetrospectiveEntry",
    "RetrospectiveEngine",
    "record_reflection_retrospective",
]

# ---------------------------------------------------------------------------
# RetrospectiveEntry dataclass
# ---------------------------------------------------------------------------


@dataclass
class RetrospectiveEntry:
    """A single retrospective record linked to a CognitiveLoop iteration."""

    id: str
    iteration_id: str
    what_worked: list[str]
    what_failed: list[str]
    lessons: list[str]
    recommendations: list[str]
    created_at: str


# ---------------------------------------------------------------------------
# RetrospectiveEngine
# ---------------------------------------------------------------------------


class RetrospectiveEngine:
    """Records and queries project retrospectives.

    Persists entries to SQLite at ``data/db/organs/governance/retrospective.db``.
    Supports full-text search, recency listing, and summary generation.
    """

    _DEFAULT_DB: str = "data/db/organs/governance/retrospective.db"

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._lock: threading.Lock = threading.Lock()
        self._init_db()
        _log.debug("[RetrospectiveEngine] db=%s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return managed_connection(conn)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS retrospectives (
                    id               TEXT PRIMARY KEY,
                    iteration_id     TEXT NOT NULL DEFAULT '',
                    what_worked_json TEXT NOT NULL DEFAULT '[]',
                    what_failed_json TEXT NOT NULL DEFAULT '[]',
                    lessons_json     TEXT NOT NULL DEFAULT '[]',
                    recommendations_json TEXT NOT NULL DEFAULT '[]',
                    created_at       TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_retro_created ON retrospectives(created_at DESC)")

    def _row_to_entry(self, row: sqlite3.Row) -> RetrospectiveEntry:
        import json

        return RetrospectiveEntry(
            id=row["id"],
            iteration_id=row["iteration_id"],
            what_worked=json.loads(row["what_worked_json"]),
            what_failed=json.loads(row["what_failed_json"]),
            lessons=json.loads(row["lessons_json"]),
            recommendations=json.loads(row["recommendations_json"]),
            created_at=row["created_at"],
        )

    def _persist(self, entry: RetrospectiveEntry) -> None:
        import json

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO retrospectives
                        (id, iteration_id, what_worked_json, what_failed_json,
                         lessons_json, recommendations_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.iteration_id,
                        json.dumps(entry.what_worked),
                        json.dumps(entry.what_failed),
                        json.dumps(entry.lessons),
                        json.dumps(entry.recommendations),
                        entry.created_at,
                    ),
                )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        iteration_id: str,
        what_worked: list[str],
        what_failed: list[str],
        lessons: list[str],
        recommendations: list[str],
    ) -> RetrospectiveEntry:
        """Create and persist a new retrospective entry.

        Args:
            iteration_id:    Linked CognitiveLoop iteration UUID (may be empty).
            what_worked:     List of things that went well.
            what_failed:     List of things that went wrong.
            lessons:         Distilled lessons learned.
            recommendations: Actionable recommendations for future iterations.

        Returns:
            The newly created RetrospectiveEntry.
        """
        entry = RetrospectiveEntry(
            id=str(uuid.uuid4()),
            iteration_id=iteration_id,
            what_worked=list(what_worked),
            what_failed=list(what_failed),
            lessons=list(lessons),
            recommendations=list(recommendations),
            created_at=datetime.now(UTC).isoformat(),
        )
        self._persist(entry)
        _log.debug("[RetrospectiveEngine] recorded entry id=%s", entry.id)
        return entry

    def get(self, entry_id: str) -> RetrospectiveEntry | None:
        """Fetch a single entry by its UUID, or None if not found."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM retrospectives WHERE id = ?", (entry_id,)).fetchone()
        return self._row_to_entry(row) if row else None

    def list_recent(self, limit: int = 10) -> list[RetrospectiveEntry]:
        """Return up to *limit* entries ordered newest-first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM retrospectives ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def search(self, query: str) -> list[RetrospectiveEntry]:
        """Search entries whose lessons or recommendations contain *query*.

        Uses case-insensitive LIKE across lessons_json and recommendations_json.
        Returns newest-first results.
        """
        if not query or not query.strip():
            return []

        pattern = f"%{query.strip()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM retrospectives
                WHERE  lessons_json         LIKE ?
                    OR recommendations_json LIKE ?
                    OR what_worked_json     LIKE ?
                    OR what_failed_json     LIKE ?
                ORDER BY created_at DESC
                """,
                (pattern, pattern, pattern, pattern),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def generate_summary(self, limit: int = 5) -> dict:
        """Aggregate insights from the most recent *limit* entries.

        Returns a dict with:
            total         — number of entries considered
            lessons       — deduplicated list of all lessons
            recommendations — deduplicated list of all recommendations
            top_worked    — most common "what worked" items
            top_failed    — most common "what failed" items
        """
        entries = self.list_recent(limit=limit)

        all_lessons: list[str] = []
        all_recommendations: list[str] = []
        all_worked: list[str] = []
        all_failed: list[str] = []

        for entry in entries:
            all_lessons.extend(entry.lessons)
            all_recommendations.extend(entry.recommendations)
            all_worked.extend(entry.what_worked)
            all_failed.extend(entry.what_failed)

        def _deduplicate(items: list[str]) -> list[str]:
            seen: set[str] = set()
            result: list[str] = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
            return result

        return {
            "total": len(entries),
            "lessons": _deduplicate(all_lessons),
            "recommendations": _deduplicate(all_recommendations),
            "top_worked": _deduplicate(all_worked),
            "top_failed": _deduplicate(all_failed),
        }


def record_reflection_retrospective(
    *,
    iteration_id: str,
    what_worked: list[str],
    what_failed: list[str],
    lessons: list[str],
    recommendations: list[str],
    fallback_dir: Path | str | None = None,
) -> bool:
    """Persist reflection retrospectives through the governance owner seam."""
    try:
        RetrospectiveEngine().record(
            iteration_id=iteration_id,
            what_worked=what_worked,
            what_failed=what_failed,
            lessons=lessons,
            recommendations=recommendations,
        )
        return True
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        _log.debug("RetrospectiveEngine failed: %s", exc)

    if fallback_dir is None:
        return True

    fallback_path = Path(fallback_dir) / "retrospective_fallback.json"
    fallback = {
        "timestamp": datetime.now(UTC).isoformat(),
        "iteration_id": iteration_id,
        "what_worked": what_worked,
        "what_failed": what_failed,
    }
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_text(
        json.dumps(fallback, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return True
