from __future__ import annotations

"""
---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Updated: 2026-03-08
Authority: 4
Keywords: [harvest, scheduler, knowledge, freshness, sqlite, governance]
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# HarvestScheduler ≡ Organ
# 内涵 ≝ {source_type, source_id, content_hash, freshness_score, tags, summary}
# 外延 ≝ {h | h ∈ D-Governance ∧ knowledge_item(h)}
# 功能 ⊢ {HarvestADRs, HarvestRetrospectives, GetFresh, GetStale, UpdateScores,
#          Search, Schedule, GetScheduledTasks, RunDueTasks, DisableTask, EnableTask}
# =============================================================================

import hashlib
import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nucleus.Z_Microkernel.utilities.sqlite_utils import managed_connection

_log = logging.getLogger(__name__)

_HARVEST_SCHEDULER_SETUP_ERRORS = (
    AttributeError,
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    sqlite3.Error,
)
_HARVEST_SCHEDULER_KNOWLEDGE_STORE_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    sqlite3.Error,
)
_HARVEST_SCHEDULER_SOURCE_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    sqlite3.Error,
)
_HARVEST_SCHEDULER_TASK_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    sqlite3.Error,
)
_HARVEST_SCHEDULER_EVOLVER_LOAD_ERRORS = (
    AttributeError,
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_HARVEST_SCHEDULER_EVOLVER_SOLIDIFY_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_HARVEST_SCHEDULER_SUPPORTED_ERROR_MODULE_PREFIXES = (
    "builtins",
    "sqlite3",
    "organs.D_Harvest",
)


def _is_supported_harvest_scheduler_error(exc: BaseException) -> bool:
    """Allow only known builtin/sqlite3/D_Harvest failures to degrade gracefully."""

    exc_module = type(exc).__module__
    return any(
        exc_module == prefix or exc_module.startswith(f"{prefix}.")
        for prefix in _HARVEST_SCHEDULER_SUPPORTED_ERROR_MODULE_PREFIXES
    )


# ---------------------------------------------------------------------------
# HarvestEntry dataclass
# ---------------------------------------------------------------------------


@dataclass
class HarvestEntry:
    """Represents a harvested knowledge item from a B-OS organ."""

    id: str
    source_type: str  # "adr", "retrospective", "committee_decision", "metric"
    source_id: str  # ID of the original source record
    content_hash: str  # SHA-256 of content for deduplication
    extracted_at: str  # ISO-8601 UTC
    freshness_score: float  # 0.0-1.0, decays over time
    tags: list[str]
    summary: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "content_hash": self.content_hash,
            "extracted_at": self.extracted_at,
            "freshness_score": self.freshness_score,
            "tags": self.tags,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# KnowledgeFreshness
# ---------------------------------------------------------------------------


class KnowledgeFreshness:
    """Computes freshness score for knowledge items.

    Score = base_score * decay_factor ^ days_since_creation
    decay_factor = 0.95 by default (5% decay per day)
    Result is clamped to [0.0, 1.0].
    """

    def compute(
        self,
        created_at: str,
        base_score: float = 1.0,
        decay_factor: float = 0.95,
    ) -> float:
        """Compute freshness for an item created at *created_at* (ISO-8601).

        Parameters
        ----------
        created_at:   ISO-8601 timestamp of when the knowledge was created
        base_score:   starting score before decay (default 1.0)
        decay_factor: per-day decay multiplier (default 0.95)

        Returns
        -------
        float in [0.0, 1.0]
        """
        try:
            created_dt = datetime.fromisoformat(created_at)
            # Ensure timezone-aware comparison
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=UTC)
            now = datetime.now(UTC)
            days = max(0.0, (now - created_dt).total_seconds() / 86400.0)
            score = base_score * (decay_factor**days)
            return float(min(1.0, max(0.0, score)))
        except (ValueError, OSError) as exc:
            _log.warning("[KnowledgeFreshness] could not parse timestamp '%s': %s", created_at, exc)
            return 0.0


# ---------------------------------------------------------------------------
# HarvestScheduler
# ---------------------------------------------------------------------------


class HarvestScheduler:
    """Harvests and indexes knowledge from B-OS organs.

    Polls ADR storage, retrospective entries, and committee decisions.
    Deduplicates via content hash (SHA-256).

    SQLite at ``data/db/organs/governance/harvest.db``.
    Thread-safe; per-instance Lock.
    """

    _DEFAULT_DB: str = "data/db/organs/governance/harvest.db"
    _DEFAULT_ADR_DB: str = "data/db/governance/adrs.db"
    _DEFAULT_RETRO_DB: str = "data/db/organs/governance/retrospective.db"
    _lock: threading.Lock

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._freshness = KnowledgeFreshness()
        self._init_db()
        _log.debug("[HarvestScheduler] db=%s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return managed_connection(conn)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS harvest_entries (
                    id              TEXT PRIMARY KEY,
                    source_type     TEXT NOT NULL,
                    source_id       TEXT NOT NULL,
                    content_hash    TEXT NOT NULL UNIQUE,
                    extracted_at    TEXT NOT NULL,
                    freshness_score REAL NOT NULL DEFAULT 1.0,
                    tags            TEXT NOT NULL DEFAULT '[]',
                    summary         TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_harvest_source_type  ON harvest_entries(source_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_harvest_freshness    ON harvest_entries(freshness_score)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_harvest_extracted_at ON harvest_entries(extracted_at)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_harvests (
                    id              TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    target          TEXT NOT NULL,
                    interval_hours  REAL NOT NULL,
                    last_run_at     TEXT,
                    next_run_at     TEXT NOT NULL,
                    enabled         INTEGER NOT NULL DEFAULT 1,
                    created_at      TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_next_run ON scheduled_harvests(next_run_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_enabled ON scheduled_harvests(enabled)")
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def _row_to_entry(self, row: sqlite3.Row) -> HarvestEntry:
        return HarvestEntry(
            id=row["id"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            content_hash=row["content_hash"],
            extracted_at=row["extracted_at"],
            freshness_score=row["freshness_score"],
            tags=json.loads(row["tags"]),
            summary=row["summary"],
        )

    def _upsert_entry(
        self,
        source_type: str,
        source_id: str,
        content: str,
        tags: list[str],
        summary: str,
    ) -> HarvestEntry | None:
        """Insert entry if not already present (dedup by content_hash).

        Returns the new HarvestEntry, or None if it was already known.
        """
        content_hash = self._hash(content)
        now = self._now()
        initial_score = self._freshness.compute(now)

        entry = HarvestEntry(
            id=str(uuid.uuid4()),
            source_type=source_type,
            source_id=source_id,
            content_hash=content_hash,
            extracted_at=now,
            freshness_score=initial_score,
            tags=tags,
            summary=summary,
        )
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO harvest_entries
                        (id, source_type, source_id, content_hash, extracted_at, freshness_score, tags, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.source_type,
                        entry.source_id,
                        entry.content_hash,
                        entry.extracted_at,
                        entry.freshness_score,
                        json.dumps(entry.tags),
                        entry.summary,
                    ),
                )
                conn.commit()
                return entry
            except sqlite3.IntegrityError:
                # Duplicate content_hash — already indexed
                return None

    # ------------------------------------------------------------------
    # Harvest methods
    # ------------------------------------------------------------------

    def harvest_adrs(self, limit: int = 50) -> list[HarvestEntry]:
        """Harvest ADR records from SQLiteADRStorage and index new ones.

        Returns the list of *newly* ingested entries (skips duplicates).
        """

        new_entries: list[HarvestEntry] = []
        try:
            from kairon_lib.organs.registry.adr_storage import (
                SQLiteADRStorage as _SQLiteADRStorage,
            )

            storage = _SQLiteADRStorage()
            adrs = storage.list()[:limit]
        except (ImportError, sqlite3.Error, OSError) as exc:
            _log.warning("[HarvestScheduler] ADR storage unavailable: %s", exc)
            return new_entries

        for adr in adrs:
            content = f"{adr.title}|{adr.context}|{adr.decision}|{adr.consequences}"
            tags = ["adr", adr.status.lower(), adr.author]
            summary = f"[ADR] {adr.title} ({adr.status})"
            entry = self._upsert_entry("adr", adr.id, content, tags, summary)
            if entry is not None:
                new_entries.append(entry)

        _log.debug("[HarvestScheduler] harvest_adrs: %d new entries", len(new_entries))
        return new_entries

    def harvest_retrospectives(self, limit: int = 50) -> list[HarvestEntry]:
        """Harvest retrospective entries from the retrospective SQLite DB.

        Falls back gracefully if the DB or table does not exist yet.
        Returns newly ingested entries.
        """
        import os

        new_entries: list[HarvestEntry] = []
        root = os.environ.get("BOS_ROOT", ".")
        retro_db = str(Path(root) / self._DEFAULT_RETRO_DB)

        if not Path(retro_db).exists():
            _log.debug("[HarvestScheduler] retrospective DB not found at %s", retro_db)
            return new_entries

        try:
            conn = sqlite3.connect(retro_db, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM retrospectives ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            conn.close()
        except sqlite3.Error as exc:
            _log.warning("[HarvestScheduler] retrospective DB error: %s", exc)
            return new_entries

        for row in rows:
            source_id = str(row["id"]) if "id" in row.keys() else str(uuid.uuid4())
            content = " ".join(str(row[k]) for k in row.keys() if k not in ("id", "created_at", "updated_at"))
            tags = ["retrospective"]
            summary = f"[Retro] {str(row[0])[:80]}"
            entry = self._upsert_entry("retrospective", source_id, content, tags, summary)
            if entry is not None:
                new_entries.append(entry)

        return new_entries

    def harvest_external_sources(self, source_ids: list[str] | None = None, limit: int = 10) -> list[HarvestEntry]:
        """Harvest knowledge from D_Harvest external sources and index new ones.

        This method integrates with D_Harvest to fetch knowledge from external
        data sources (web APIs, HTML content, etc.) and integrates them into
        the Governance knowledge management system.

        Args:
            source_ids: List of source IDs to harvest (None for all available sources)
            limit: Maximum number of entries to harvest per source

        Returns:
            List of newly ingested HarvestEntry objects.
        """
        new_entries: list[HarvestEntry] = []

        try:
            # Lazy cross-organ imports via importlib (topology compliance)
            import importlib

            _html_mod = importlib.import_module("organs.D_Harvest.extractors.html_extractor")
            _HtmlExtractor = _html_mod.HtmlContentExtractor
            _orch_mod = importlib.import_module("organs.D_Harvest.orchestrator")
            _HarvestOrchestrator = _orch_mod.HarvestOrchestrator
            _gate_mod = importlib.import_module("organs.D_Harvest.quality.gate")
            _QualityGate = _gate_mod.QualityGate
            _reg_mod = importlib.import_module("organs.D_Harvest.sources.registry")
            _SourceRegistry = _reg_mod.SourceRegistry
            _store_mod = importlib.import_module("organs.D_Harvest.storage.knowledge_store")
            _KnowledgeStore = _store_mod.KnowledgeStore
        except (ImportError, AttributeError) as exc:
            _log.warning("[HarvestScheduler] D_Harvest components unavailable: %s", exc)
            return new_entries

        try:
            # Initialize D_Harvest components
            registry = _SourceRegistry()
            extractor = _HtmlExtractor()
            quality_gate = _QualityGate()

            # Optional: Use knowledge store if available
            try:
                knowledge_store = _KnowledgeStore()
            except _HARVEST_SCHEDULER_KNOWLEDGE_STORE_ERRORS as store_exc:
                if not _is_supported_harvest_scheduler_error(store_exc):
                    raise
                _log.debug("[HarvestScheduler] KnowledgeStore unavailable: %s", store_exc)
                knowledge_store = None

            # Get source IDs to harvest
            if source_ids is None:
                # Harvest all available sources up to limit
                all_sources = list(registry.list_sources().keys())[:limit]
                source_ids = all_sources

            _log.info("[HarvestScheduler] Harvesting %d external sources: %s", len(source_ids), source_ids)

            # Harvest each source
            for source_id in source_ids:
                try:
                    # Create orchestrator for this source
                    orchestrator = _HarvestOrchestrator(
                        source_registry=registry,
                        content_extractor=extractor,
                        quality_gate=quality_gate,
                        knowledge_store=knowledge_store,
                    )

                    # Execute harvest cycle
                    import asyncio

                    result = asyncio.run(orchestrator.harvest_cycle(source_id))

                    if result.success and result.items_count > 0:
                        # Convert D_Harvest results to HarvestEntry format
                        # For now, create a summary entry for each successful harvest
                        summary = f"[External Harvest] {source_id}: {result.items_count} items harvested"
                        tags = ["external_harvest", "d_harvest", source_id]

                        # Create a combined content hash from the source
                        import hashlib

                        content_hash = hashlib.sha256(f"d_harvest_{source_id}".encode()).hexdigest()

                        entry = HarvestEntry(
                            id=str(uuid.uuid4()),
                            source_type="external_harvest",
                            source_id=source_id,
                            content_hash=content_hash,
                            extracted_at=datetime.now(UTC).isoformat(),
                            freshness_score=1.0,  # Fresh harvest
                            tags=tags,
                            summary=summary,
                        )

                        # Store in Governance database
                        with self._lock, self._connect() as conn:
                            conn.execute(
                                """
                                INSERT INTO harvest_entries
                                    (id, source_type, source_id, content_hash, extracted_at,
                                     freshness_score, tags, summary)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    entry.id,
                                    entry.source_type,
                                    entry.source_id,
                                    entry.content_hash,
                                    entry.extracted_at,
                                    entry.freshness_score,
                                    json.dumps(entry.tags),
                                    entry.summary,
                                ),
                            )
                            conn.commit()

                        new_entries.append(entry)
                        _log.info(
                            "[HarvestScheduler] External harvest successful: %s -> %s",
                            source_id,
                            entry.id,
                        )

                except _HARVEST_SCHEDULER_SOURCE_ERRORS as source_exc:
                    if not _is_supported_harvest_scheduler_error(source_exc):
                        raise
                    _log.warning(
                        "[HarvestScheduler] External harvest failed for %s: %s",
                        source_id,
                        source_exc,
                    )
                    continue

        except _HARVEST_SCHEDULER_SETUP_ERRORS as exc:
            if not _is_supported_harvest_scheduler_error(exc):
                raise
            _log.error("[HarvestScheduler] External harvest setup failed: %s", exc)
            return new_entries

        _log.info(
            "[HarvestScheduler] harvest_external_sources: %d new entries from %d sources",
            len(new_entries),
            len(source_ids) if source_ids else 0,
        )
        return new_entries

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_fresh_knowledge(self, min_score: float = 0.5, limit: int = 20) -> list[HarvestEntry]:
        """Return entries with freshness_score >= *min_score*, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM harvest_entries
                WHERE freshness_score >= ?
                ORDER BY freshness_score DESC, extracted_at DESC
                LIMIT ?
                """,
                (min_score, limit),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_stale_knowledge(self, max_score: float = 0.3) -> list[HarvestEntry]:
        """Return entries with freshness_score <= *max_score*, stalest first."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM harvest_entries
                WHERE freshness_score <= ?
                ORDER BY freshness_score ASC
                """,
                (max_score,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def update_freshness_scores(self) -> int:
        """Recompute freshness for all entries based on their extracted_at timestamp.

        Returns the number of updated rows.
        """
        with self._connect() as conn:
            rows = conn.execute("SELECT id, extracted_at FROM harvest_entries").fetchall()

        updated = 0
        for row in rows:
            new_score = self._freshness.compute(row["extracted_at"])
            with self._lock, self._connect() as conn:
                conn.execute(
                    "UPDATE harvest_entries SET freshness_score = ? WHERE id = ?",
                    (new_score, row["id"]),
                )
                conn.commit()
            updated += 1

        _log.debug("[HarvestScheduler] updated %d freshness scores", updated)
        return updated

    def search(self, query: str) -> list[HarvestEntry]:
        """Full-text search across summary and tags (LIKE fallback).

        Returns matching entries ordered by freshness descending.
        """
        like = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM harvest_entries
                WHERE summary LIKE ?
                   OR tags    LIKE ?
                   OR source_type LIKE ?
                ORDER BY freshness_score DESC
                """,
                (like, like, like),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    # ------------------------------------------------------------------
    # Scheduling methods
    # ------------------------------------------------------------------

    def schedule(self, name: str, target: str, interval_hours: float) -> dict:
        """Register a recurring harvest task.

        Args:
            name: Human-readable name, e.g. "Daily ADR harvest"
            target: "adrs", "retrospectives", or a domain string
            interval_hours: How often to run (e.g. 24.0 for daily)

        Returns:
            dict with {id, name, target, interval_hours, next_run_at}
        """
        task_id = uuid.uuid4().hex
        now = self._now()
        next_run_at = (datetime.now(UTC) + timedelta(hours=interval_hours)).isoformat()

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scheduled_harvests
                    (id, name, target, interval_hours, last_run_at, next_run_at, enabled, created_at)
                VALUES (?, ?, ?, ?, NULL, ?, 1, ?)
                """,
                (task_id, name, target, interval_hours, next_run_at, now),
            )
            conn.commit()

        _log.debug("[HarvestScheduler] scheduled task '%s' id=%s next=%s", name, task_id, next_run_at)
        return {
            "id": task_id,
            "name": name,
            "target": target,
            "interval_hours": interval_hours,
            "next_run_at": next_run_at,
        }

    def get_scheduled_tasks(self) -> list[dict]:
        """Return all scheduled harvest tasks with their status.

        Returns:
            list of dicts {id, name, target, interval_hours, last_run_at,
            next_run_at, enabled, overdue} where overdue=True if next_run_at
            is in the past.
        """
        now = self._now()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM scheduled_harvests ORDER BY next_run_at ASC").fetchall()

        result = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "target": row["target"],
                    "interval_hours": row["interval_hours"],
                    "last_run_at": row["last_run_at"],
                    "next_run_at": row["next_run_at"],
                    "enabled": bool(row["enabled"]),
                    "overdue": row["next_run_at"] <= now,
                }
            )
        return result

    def run_due_tasks(self) -> list[dict]:
        """Execute all tasks whose next_run_at is now or past.

        For each due task:
        - Runs harvest_adrs() or harvest_retrospectives() based on target
        - Updates last_run_at and next_run_at

        Returns:
            list of {task_id, name, entries_harvested, ran_at}
        """
        now = self._now()
        with self._connect() as conn:
            due_rows = conn.execute(
                """
                SELECT * FROM scheduled_harvests
                WHERE enabled = 1
                  AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (now,),
            ).fetchall()

        results = []
        for row in due_rows:
            task_id = row["id"]
            name = row["name"]
            target = row["target"]
            interval_hours = row["interval_hours"]

            # Execute the appropriate harvest
            try:
                if target == "adrs":
                    entries = self.harvest_adrs()
                elif target == "retrospectives":
                    entries = self.harvest_retrospectives()
                elif target == "external_harvest":
                    # New: Integrate with D_Harvest for external knowledge sources
                    entries = self.harvest_external_sources(limit=10)
                else:
                    # Unknown domain — attempt adrs as safe default, log warning
                    _log.warning(
                        "[HarvestScheduler] run_due_tasks: unknown target '%s' for task '%s', skipping harvest",
                        target,
                        name,
                    )
                    entries = []
            except _HARVEST_SCHEDULER_TASK_ERRORS as exc:
                if not _is_supported_harvest_scheduler_error(exc):
                    raise
                _log.warning("[HarvestScheduler] run_due_tasks: task '%s' raised %s", name, exc)
                entries = []

            ran_at = self._now()
            new_next_run_at = (datetime.now(UTC) + timedelta(hours=interval_hours)).isoformat()

            with self._lock, self._connect() as conn:
                conn.execute(
                    """
                    UPDATE scheduled_harvests
                       SET last_run_at = ?,
                           next_run_at = ?
                     WHERE id = ?
                    """,
                    (ran_at, new_next_run_at, task_id),
                )
                conn.commit()

            results.append(
                {
                    "task_id": task_id,
                    "name": name,
                    "entries_harvested": len(entries),
                    "ran_at": ran_at,
                }
            )
            _log.debug(
                "[HarvestScheduler] ran task '%s' (%s new entries), next=%s",
                name,
                len(entries),
                new_next_run_at,
            )

        return results

    def disable_task(self, task_id: str) -> bool:
        """Disable a scheduled task.

        Returns:
            True if the task was found and updated, False otherwise.
        """
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE scheduled_harvests SET enabled = 0 WHERE id = ?",
                (task_id,),
            )
            conn.commit()
        found = cursor.rowcount > 0
        _log.debug("[HarvestScheduler] disable_task id=%s found=%s", task_id, found)
        return found

    def enable_task(self, task_id: str) -> bool:
        """Enable a scheduled task.

        Returns:
            True if the task was found and updated, False otherwise.
        """
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE scheduled_harvests SET enabled = 1 WHERE id = ?",
                (task_id,),
            )
            conn.commit()
        found = cursor.rowcount > 0
        _log.debug("[HarvestScheduler] enable_task id=%s found=%s", task_id, found)
        return found

    # ------------------------------------------------------------------
    # Auto-evolve: harvest → filter fresh → solidify via AutonomousEvolver
    # ------------------------------------------------------------------

    def _evolve_entries(
        self,
        entries: list[HarvestEntry],
        freshness_threshold: float,
    ) -> dict:
        """Shared logic for harvest_and_evolve / harvest_and_evolve_adrs."""
        import importlib

        fresh = [e for e in entries if e.freshness_score >= freshness_threshold]
        result: dict = {
            "harvested": len(entries),
            "fresh": len(fresh),
            "evolved": [],
        }
        if not fresh:
            _log.debug(
                "[HarvestScheduler] no entries above threshold %.2f",
                freshness_threshold,
            )
            return result

        groups: dict[str, list[HarvestEntry]] = {}
        for entry in fresh:
            groups.setdefault(entry.source_type, []).append(entry)

        try:
            mod = importlib.import_module(
                "organs.D_Genesis.organs.autonomous_evolver",
            )
            evolver = mod.AutonomousEvolver()
        except _HARVEST_SCHEDULER_EVOLVER_LOAD_ERRORS:
            _log.exception("[HarvestScheduler] failed to load AutonomousEvolver")
            return result

        for source_type, group in groups.items():
            avg_score = sum(e.freshness_score for e in group) / len(group)
            review_report: dict = {
                "vision_id": f"harvest_{source_type}_{uuid.uuid4().hex[:8]}",
                "metrics": {
                    "holographic_score": avg_score,
                    "entry_count": len(group),
                    "source_type": source_type,
                },
                "summaries": [e.summary for e in group],
            }
            try:
                evolve_result = evolver.solidify_knowledge_to_archetype(review_report)
                result["evolved"].append(evolve_result)
                _log.info(
                    "[HarvestScheduler] evolved %d %s entries (avg=%.2f)",
                    len(group),
                    source_type,
                    avg_score,
                )
            except _HARVEST_SCHEDULER_EVOLVER_SOLIDIFY_ERRORS:
                _log.exception(
                    "[HarvestScheduler] solidify failed for source_type=%s",
                    source_type,
                )

        return result

    def harvest_and_evolve(
        self,
        freshness_threshold: float = 0.8,
        limit: int = 50,
    ) -> dict:
        """Harvest retrospectives and auto-evolve fresh entries.

        Returns:
            ``{"harvested": int, "fresh": int, "evolved": list}``
        """
        entries = self.harvest_retrospectives(limit)
        return self._evolve_entries(entries, freshness_threshold)

    def harvest_and_evolve_adrs(
        self,
        freshness_threshold: float = 0.8,
        limit: int = 50,
    ) -> dict:
        """Harvest ADRs and auto-evolve fresh entries.

        Returns:
            ``{"harvested": int, "fresh": int, "evolved": list}``
        """
        entries = self.harvest_adrs(limit)
        return self._evolve_entries(entries, freshness_threshold)
