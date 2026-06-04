from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: "@Builder"
Layer: L4
Domain: D-Governance
Summary: EvolutionMetrics — tracks B-OS system evolution over time via snapshots.
Tags:
  - evolution
  - metrics
  - governance
  - sqlite
  - observability
Authority: organs/D_Governance/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Evolution Metrics ≡ Module
# 内涵 ≝ {Evolution, Metrics}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, EvolutionMetrics)}
# 功能 ⊢ {Evolution_Metrics, Init_Evolution, Validate_Metrics}
# =============================================================================

import logging
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nucleus.Z_Microkernel.utilities.sqlite_utils import managed_connection

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EvolutionSnapshot dataclass
# ---------------------------------------------------------------------------


@dataclass
class EvolutionSnapshot:
    """A point-in-time snapshot of B-OS evolution indicators."""

    id: str
    snapshot_at: str
    archetype_count: int  # number of distinct ThinkingModes used
    knowledge_entries: int  # harvest_scheduler entries
    gate_reviews_passed: int  # from audit_query
    gate_reviews_total: int
    success_rate: float  # passed/total if total > 0 else 0.0
    cognitive_loop_iterations: int  # from cognitive_loop history
    adr_count: int  # from adr_storage
    freshness_avg: float  # avg freshness score from harvest

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# EvolutionMetrics
# ---------------------------------------------------------------------------


class EvolutionMetrics:
    """Tracks B-OS system evolution over time.

    Takes snapshots of key evolution indicators:
    - Archetype diversity (ThinkingMode usage variety)
    - Knowledge growth (HarvestScheduler entries)
    - Success rate (gate reviews passed/total)
    - Cognitive loop activity
    - ADR accumulation (decision history)

    SQLite at data/db/organs/governance/evolution.db
    Thread-safe; per-instance Lock.
    """

    _DEFAULT_DB: str = "data/db/organs/governance/evolution.db"

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        _log.debug("[EvolutionMetrics] db=%s", self._db_path)

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
                CREATE TABLE IF NOT EXISTS evolution_snapshots (
                    id                       TEXT PRIMARY KEY,
                    snapshot_at              TEXT NOT NULL,
                    archetype_count          INTEGER NOT NULL DEFAULT 0,
                    knowledge_entries        INTEGER NOT NULL DEFAULT 0,
                    gate_reviews_passed      INTEGER NOT NULL DEFAULT 0,
                    gate_reviews_total       INTEGER NOT NULL DEFAULT 0,
                    success_rate             REAL NOT NULL DEFAULT 0.0,
                    cognitive_loop_iterations INTEGER NOT NULL DEFAULT 0,
                    adr_count                INTEGER NOT NULL DEFAULT 0,
                    freshness_avg            REAL NOT NULL DEFAULT 0.0
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evo_snapshot_at ON evolution_snapshots(snapshot_at)")
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _row_to_snapshot(self, row: sqlite3.Row) -> EvolutionSnapshot:
        return EvolutionSnapshot(
            id=row["id"],
            snapshot_at=row["snapshot_at"],
            archetype_count=row["archetype_count"],
            knowledge_entries=row["knowledge_entries"],
            gate_reviews_passed=row["gate_reviews_passed"],
            gate_reviews_total=row["gate_reviews_total"],
            success_rate=row["success_rate"],
            cognitive_loop_iterations=row["cognitive_loop_iterations"],
            adr_count=row["adr_count"],
            freshness_avg=row["freshness_avg"],
        )

    # ------------------------------------------------------------------
    # Individual metric collectors (each wrapped in try/except)
    # ------------------------------------------------------------------

    def _collect_archetype_count(self) -> int:
        """Count distinct ThinkingModes from ThinkingPathLibrary."""
        try:
            from kairon_lib.organs.governance.thinking_paths import (
                ThinkingMode,
            )

            # Count only path-level modes (not step-level reasoning modes)
            path_modes = {
                ThinkingMode.COUNCIL,
                ThinkingMode.RED_TEAM,
                ThinkingMode.SOCRATIC,
                ThinkingMode.DELPHI,
                ThinkingMode.DESIGN_THINKING,
                ThinkingMode.SYSTEMS_THINKING,
            }
            return len(path_modes)
        except (ImportError, AttributeError):
            return 0

    def _collect_knowledge_entries(self) -> int:
        """Count total harvest entries from HarvestScheduler."""
        try:
            from kairon_lib.organs.registry.harvest_scheduler import (
                HarvestScheduler,
            )

            hs = HarvestScheduler()
            with hs._connect() as conn:
                row = conn.execute("SELECT COUNT(*) AS cnt FROM harvest_entries").fetchone()
                return int(row["cnt"]) if row else 0
        except sqlite3.Error:
            return 0

    def _collect_gate_reviews(self) -> tuple[int, int]:
        """Return (passed, total) gate reviews from AuditQueryEngine."""
        try:
            from kairon_lib.organs.audit.audit_query import (
                AuditQueryEngine,
            )

            aq = AuditQueryEngine()
            all_reviews = aq.query(event_type="gate_review")
            total = len(all_reviews)
            passed = sum(1 for e in all_reviews if isinstance(e.payload, dict) and e.payload.get("passed", False))
            return passed, total
        except (OSError, ValueError, AttributeError):
            return 0, 0

    def _collect_cognitive_loop_iterations(self) -> int:
        """Count cognitive loop iterations."""
        try:
            from kairon_lib.organs.cognitive.cognitive_loop import (
                CognitiveLoop,
            )

            loop = CognitiveLoop()
            history = loop.get_history(limit=10000)
            return len(history)
        except (ImportError, OSError, ValueError, AttributeError):
            return 0

    def _collect_adr_count(self) -> int:
        """Count ADR records."""
        try:
            from kairon_lib.organs.registry.adr_storage import (
                SQLiteADRStorage,
            )

            storage = SQLiteADRStorage()
            return len(storage.list())
        except (ImportError, sqlite3.Error, OSError):
            return 0

    def _collect_freshness_avg(self) -> float:
        """Compute average freshness score from HarvestScheduler."""
        try:
            from kairon_lib.organs.registry.harvest_scheduler import (
                HarvestScheduler,
            )

            hs = HarvestScheduler()
            with hs._connect() as conn:
                row = conn.execute("SELECT AVG(freshness_score) AS avg_fs FROM harvest_entries").fetchone()
                if row and row["avg_fs"] is not None:
                    return float(row["avg_fs"])
            return 0.0
        except sqlite3.Error:
            return 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def take_snapshot(self) -> EvolutionSnapshot:
        """Collect current metrics and persist a new snapshot."""
        archetype_count = self._collect_archetype_count()
        knowledge_entries = self._collect_knowledge_entries()
        gate_passed, gate_total = self._collect_gate_reviews()
        success_rate = (gate_passed / gate_total) if gate_total > 0 else 0.0
        loop_iterations = self._collect_cognitive_loop_iterations()
        adr_count = self._collect_adr_count()
        freshness_avg = self._collect_freshness_avg()

        snapshot = EvolutionSnapshot(
            id=str(uuid.uuid4()),
            snapshot_at=self._now(),
            archetype_count=archetype_count,
            knowledge_entries=knowledge_entries,
            gate_reviews_passed=gate_passed,
            gate_reviews_total=gate_total,
            success_rate=round(success_rate, 4),
            cognitive_loop_iterations=loop_iterations,
            adr_count=adr_count,
            freshness_avg=round(freshness_avg, 4),
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO evolution_snapshots
                    (id, snapshot_at, archetype_count, knowledge_entries,
                     gate_reviews_passed, gate_reviews_total, success_rate,
                     cognitive_loop_iterations, adr_count, freshness_avg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.id,
                    snapshot.snapshot_at,
                    snapshot.archetype_count,
                    snapshot.knowledge_entries,
                    snapshot.gate_reviews_passed,
                    snapshot.gate_reviews_total,
                    snapshot.success_rate,
                    snapshot.cognitive_loop_iterations,
                    snapshot.adr_count,
                    snapshot.freshness_avg,
                ),
            )
            conn.commit()

        _log.debug("[EvolutionMetrics] snapshot %s taken", snapshot.id)
        return snapshot

    def get_snapshots(self, limit: int = 10) -> list[EvolutionSnapshot]:
        """Return up to *limit* snapshots, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evolution_snapshots ORDER BY snapshot_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    def get_latest(self) -> EvolutionSnapshot | None:
        """Return the most recent snapshot, or None if no snapshots exist."""
        snapshots = self.get_snapshots(limit=1)
        return snapshots[0] if snapshots else None

    def compute_growth_rate(self) -> dict[str, float]:
        """Compute growth indicators from the two most recent snapshots.

        Returns:
            {'knowledge_growth': float, 'adr_growth': float, 'success_trend': float}

        Values are deltas (new - old).  0.0 if fewer than two snapshots.
        """
        snapshots = self.get_snapshots(limit=2)
        if len(snapshots) < 2:
            return {"knowledge_growth": 0.0, "adr_growth": 0.0, "success_trend": 0.0}

        newer, older = snapshots[0], snapshots[1]
        return {
            "knowledge_growth": float(newer.knowledge_entries - older.knowledge_entries),
            "adr_growth": float(newer.adr_count - older.adr_count),
            "success_trend": round(newer.success_rate - older.success_rate, 4),
        }

    def summary(self) -> dict[str, Any]:
        """Return human-readable summary suitable for bos status."""
        latest = self.get_latest()
        growth = self.compute_growth_rate()

        if latest is None:
            return {
                "available": False,
                "archetypes": 0,
                "adrs": 0,
                "success_rate_pct": 0.0,
                "knowledge_entries": 0,
                "cognitive_loop_iterations": 0,
                "freshness_avg": 0.0,
                "knowledge_growth": 0.0,
                "adr_growth": 0.0,
                "success_trend": 0.0,
                "snapshot_at": None,
            }

        return {
            "available": True,
            "archetypes": latest.archetype_count,
            "adrs": latest.adr_count,
            "success_rate_pct": round(latest.success_rate * 100, 1),
            "knowledge_entries": latest.knowledge_entries,
            "cognitive_loop_iterations": latest.cognitive_loop_iterations,
            "freshness_avg": latest.freshness_avg,
            "knowledge_growth": growth["knowledge_growth"],
            "adr_growth": growth["adr_growth"],
            "success_trend": growth["success_trend"],
            "snapshot_at": latest.snapshot_at,
        }
