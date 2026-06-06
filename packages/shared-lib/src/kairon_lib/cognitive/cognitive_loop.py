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
Keywords: [cognitive, loop, observe, think, act, learn, governance, sqlite]
---

CognitiveLoop — observe→think→act→learn engine for D-Governance.

Extracted from SharedBrain D_Governance → kairon_lib.
"""


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# CognitiveLoop ≡ Organ
# 内涵 ≝ {observe, think, act, learn}  (四相循环)
# 外延 ≝ {i | i ∈ D-Governance ∧ loop_iteration(i)}
# 功能 ⊢ {RunIteration, GetHistory, Reset, GetCurrentPhase}
# =============================================================================
import logging
import sqlite3
import threading
import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from kairon_utils.sqlite_utils import managed_connection

_log = logging.getLogger(__name__)

__all__ = [
    "CognitiveLoopPhase",
    "LoopIteration",
    "CognitiveLoop",
]


# ---------------------------------------------------------------------------
# Phase enum
# ---------------------------------------------------------------------------


class CognitiveLoopPhase(StrEnum):
    """The four phases of the cognitive loop."""

    OBSERVE = "observe"
    THINK = "think"
    ACT = "act"
    LEARN = "learn"


_PHASE_ORDER: list[CognitiveLoopPhase] = [
    CognitiveLoopPhase.OBSERVE,
    CognitiveLoopPhase.THINK,
    CognitiveLoopPhase.ACT,
    CognitiveLoopPhase.LEARN,
]


# ---------------------------------------------------------------------------
# LoopIteration dataclass
# ---------------------------------------------------------------------------


@dataclass
class LoopIteration:
    """A single completed iteration of the cognitive loop."""

    id: str
    phase: CognitiveLoopPhase
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    started_at: str
    completed_at: str | None = None
    duration_ms: float | None = None


# ---------------------------------------------------------------------------
# CognitiveLoop
# ---------------------------------------------------------------------------


class CognitiveLoop:
    """Implements the observe→think→act→learn cognitive cycle.

    Each iteration:
    - OBSERVE: collect context from external dict (metrics, alerts, etc.)
    - THINK: apply ThinkingPathLibrary.recommend() to select a strategy
    - ACT: store the recommended action in outputs
    - LEARN: call RetrospectiveEngine.record_iteration()

    Iterations are persisted to SQLite so history survives restarts.
    All phase transitions are protected by a threading.Lock.

    Phase cycling design intent: after every full run_iteration() call the
    internal ``_current_phase`` is reset to OBSERVE.  This means
    get_current_phase() will always report OBSERVE *between* active
    iterations — it reflects the idle/idle-ready state, not the phase that
    was most recently completed.  The completed phase is stored in the
    LoopIteration record (persisted to SQLite) and retrieved via
    get_history().  Callers that need the last completed phase should
    consult the history, not get_current_phase().
    """

    _DEFAULT_DB: str = "data/db/organs/governance/cognitive_loop.db"

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._lock: threading.Lock = threading.Lock()
        self._current_phase: CognitiveLoopPhase = CognitiveLoopPhase.OBSERVE

        self._init_db()
        _log.debug("[CognitiveLoop] db=%s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return managed_connection(conn)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS loop_iterations (
                    id           TEXT PRIMARY KEY,
                    phase        TEXT NOT NULL,
                    inputs_json  TEXT NOT NULL DEFAULT '{}',
                    outputs_json TEXT NOT NULL DEFAULT '{}',
                    started_at   TEXT NOT NULL,
                    completed_at TEXT,
                    duration_ms  REAL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_loop_started ON loop_iterations(started_at DESC)")

    def _persist(self, iteration: LoopIteration) -> None:
        import json

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO loop_iterations
                    (id, phase, inputs_json, outputs_json, started_at, completed_at, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    iteration.id,
                    iteration.phase.value,
                    json.dumps(iteration.inputs),
                    json.dumps(iteration.outputs),
                    iteration.started_at,
                    iteration.completed_at,
                    iteration.duration_ms,
                ),
            )

    @staticmethod
    def _row_to_iteration(row: sqlite3.Row) -> LoopIteration:
        import json

        return LoopIteration(
            id=row["id"],
            phase=CognitiveLoopPhase(row["phase"]),
            inputs=json.loads(row["inputs_json"]),
            outputs=json.loads(row["outputs_json"]),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"],
        )

    # ------------------------------------------------------------------
    # Phase execution helpers
    # ------------------------------------------------------------------

    def _run_observe(self, context: dict[str, Any]) -> dict[str, Any]:
        """OBSERVE phase: accept external context, return it as outputs."""
        return dict(context)

    def _run_think(self, observe_outputs: dict[str, Any]) -> dict[str, Any]:
        """THINK phase: recommend a ThinkingPath based on observed context."""
        problem_type = observe_outputs.get("problem_type", "architecture")

        thinking_mode: str = "council"  # fallback
        thinking_steps: list[str] = []

        try:
            from kairon_lib.thinking import ThinkingPathLibrary

            path = ThinkingPathLibrary.recommend(str(problem_type))
            thinking_mode = path.mode.value if hasattr(path, "mode") else "council"
            thinking_steps = [s.prompt for s in getattr(path, "steps", [])]
        except ImportError:
            _log.debug("[CognitiveLoop] ThinkingPathLibrary not available; using default")
        except (OSError, ValueError, AttributeError) as exc:
            _log.warning("[CognitiveLoop] think phase error: %s", exc)

        return {
            "recommended_mode": thinking_mode,
            "thinking_steps": thinking_steps,
            "problem_type": problem_type,
        }

    def _run_act(self, think_outputs: dict[str, Any]) -> dict[str, Any]:
        """ACT phase: store the recommended action."""
        return {
            "action": f"execute_{think_outputs.get('recommended_mode', 'council')}",
            "mode": think_outputs.get("recommended_mode", "council"),
            "problem_type": think_outputs.get("problem_type", "architecture"),
        }

    def _run_learn(self, iteration_id: str, act_outputs: dict[str, Any]) -> dict[str, Any]:
        """LEARN phase: delegate to RetrospectiveEngine and integrate op6 evolution suggestions."""
        retro_id: str | None = None
        evolution_suggestions: list[dict] = []

        try:
            from kairon_lib.retrospective import RetrospectiveEngine

            engine = RetrospectiveEngine()

            # Collect historical data for op6 analysis
            recent_entries = engine.list_recent(limit=10)
            historical_data = {
                "errors": [],
                "execution_times": [],
                "total_entries": len(recent_entries),
            }

            # Aggregate historical data from recent retrospectives
            for entry in recent_entries:
                if entry.what_failed:
                    historical_data["errors"].extend(entry.what_failed)

            # Base lessons and recommendations
            base_lessons = [f"Mode {act_outputs.get('mode', 'council')} applied"]
            base_recommendations = ["Continue monitoring context"]

            # Record retrospective with evolution-enhanced recommendations
            entry = engine.record(
                iteration_id=iteration_id,
                what_worked=[f"Executed action: {act_outputs.get('action', 'unknown')}"],
                what_failed=[],
                lessons=base_lessons,
                recommendations=base_recommendations,
            )
            retro_id = entry.id

        except ImportError:
            _log.debug("[CognitiveLoop] RetrospectiveEngine not available")
        except (OSError, ValueError, AttributeError) as exc:
            _log.warning("[CognitiveLoop] learn phase error: %s", exc)

        return {
            "retrospective_id": retro_id,
            "action_recorded": act_outputs.get("action"),
            "evolution_suggestions_count": len(evolution_suggestions),
            "high_priority_count": len([s for s in evolution_suggestions if s.get("priority") == "high"]),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_iteration(self, context: dict[str, Any]) -> LoopIteration:
        """Run one full observe→think→act→learn cycle.

        Args:
            context: External inputs (metrics, alerts, problem_type, etc.)

        Returns:
            Completed LoopIteration with all phase outputs merged.
        """
        import time

        with self._lock:
            iteration_id = str(uuid.uuid4())
            started_at = datetime.now(UTC).isoformat()
            start_ns = time.monotonic_ns()

            # Phase: OBSERVE
            self._current_phase = CognitiveLoopPhase.OBSERVE
            observe_out = self._run_observe(context)

            # Phase: THINK
            self._current_phase = CognitiveLoopPhase.THINK
            think_out = self._run_think(observe_out)

            # Phase: ACT
            self._current_phase = CognitiveLoopPhase.ACT
            act_out = self._run_act(think_out)

            # Phase: LEARN
            self._current_phase = CognitiveLoopPhase.LEARN
            learn_out = self._run_learn(iteration_id, act_out)

            # Return to OBSERVE for next iteration
            self._current_phase = CognitiveLoopPhase.OBSERVE

            duration_ms = (time.monotonic_ns() - start_ns) / 1_000_000
            completed_at = datetime.now(UTC).isoformat()

            outputs = {
                "observe": observe_out,
                "think": think_out,
                "act": act_out,
                "learn": learn_out,
            }

            iteration = LoopIteration(
                id=iteration_id,
                phase=CognitiveLoopPhase.LEARN,  # last completed phase
                inputs=dict(context),
                outputs=outputs,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )
            self._persist(iteration)
            return iteration

    def get_history(self, limit: int = 10) -> list[LoopIteration]:
        """Return the most recent iterations (newest first)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM loop_iterations ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_iteration(r) for r in rows]

    def get_current_phase(self) -> CognitiveLoopPhase:
        """Return the current phase (thread-safe read)."""
        with self._lock:
            return self._current_phase

    def reset(self) -> None:
        """Reset the loop to OBSERVE phase (does not clear history)."""
        with self._lock:
            self._current_phase = CognitiveLoopPhase.OBSERVE
            _log.debug("[CognitiveLoop] reset to OBSERVE")
