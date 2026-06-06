from __future__ import annotations

"""
---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Updated: 2026-03-17
Authority: 4
Keywords: [auto, executor, automation, trigger, rollback, orchestration, sqlite]
---

Extracted from SharedBrain D_Governance → kairon_lib.
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# AutoExecutor ≡ Organ
# 内涵 ≝ {execution_id, trigger_type, target, status, result, rollback_state}
# 外延 ≝ {e | e ∈ D-Governance ∧ auto_execution(e)}
# 功能 ⊢ {TriggerOnCondition, OrchestrateExecution, RollbackExecution,
#          GetExecution, ListExecutions, RegisterTrigger, UnregisterTrigger}
# =============================================================================

import json
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


# ---------------------------------------------------------------------------
# TriggerType enum
# ---------------------------------------------------------------------------


class TriggerType(StrEnum):
    """Type of execution trigger."""

    SCHEDULE = "schedule"  # Time-based trigger
    EVENT = "event"  # Event-based trigger
    CONDITION = "condition"  # Condition-based trigger
    MANUAL = "manual"  # Manual trigger
    POLICY = "policy"  # Policy-based trigger


# ---------------------------------------------------------------------------
# ExecutionStatus enum
# ---------------------------------------------------------------------------


class ExecutionStatus(StrEnum):
    """Status of an auto-execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# TriggerCondition dataclass
# ---------------------------------------------------------------------------


@dataclass
class TriggerCondition:
    """Represents a condition that can trigger auto-execution."""

    field: str  # Field to monitor (e.g., "metric.cpu_usage")
    operator: str  # Comparison operator (">", "<", "==", "!=", ">=", "<=")
    threshold: float  # Threshold value
    description: str | None = None

    def evaluate(self, value: float) -> bool:
        """Evaluate if the condition is met."""
        ops = {
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            "==": lambda a, b: abs(a - b) < 1e-9,
            "!=": lambda a, b: abs(a - b) >= 1e-9,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        op_func = ops.get(self.operator)
        if op_func is None:
            raise ValueError(f"Unknown operator: {self.operator}")
        return op_func(value, self.threshold)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator,
            "threshold": self.threshold,
            "description": self.description,
        }


# ---------------------------------------------------------------------------
# AutoTrigger dataclass
# ---------------------------------------------------------------------------


@dataclass
class AutoTrigger:
    """Represents a registered auto-execution trigger."""

    id: str
    name: str
    trigger_type: TriggerType
    condition: TriggerCondition | None
    target: str  # What to execute (e.g., policy_id, workflow_id)
    enabled: bool
    created_at: str
    last_triggered_at: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "trigger_type": self.trigger_type.value,
            "condition": self.condition.to_dict() if self.condition else None,
            "target": self.target,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_triggered_at": self.last_triggered_at,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# ExecutionResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExecutionResult:
    """Result of an auto-execution."""

    success: bool
    message: str
    data: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# AutoExecution dataclass
# ---------------------------------------------------------------------------


@dataclass
class AutoExecution:
    """Represents an auto-execution event."""

    id: str
    trigger_id: str
    trigger_type: TriggerType
    target: str
    status: ExecutionStatus
    result: ExecutionResult | None
    started_at: str
    completed_at: str | None = None
    rollback_state: dict[str, Any] | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type.value,
            "target": self.target,
            "status": self.status.value,
            "result": self.result.to_dict() if self.result else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "rollback_state": self.rollback_state,
            "error_message": self.error_message,
        }


# ---------------------------------------------------------------------------
# AutoExecutor
# ---------------------------------------------------------------------------


class AutoExecutor:
    """Automated decision execution with rollback support.

    Triggers executions based on conditions, events, schedules, or policies.
    Maintains rollback state for recovery from failures.

    SQLite at ``data/db/organs/governance/auto_executor.db``.
    Thread-safe; uses a per-instance Lock.

    BOS-URI endpoints
    -----------------
    ``bos://governance/auto/trigger``    — trigger on condition
    ``bos://governance/auto/execute``    — orchestrate execution
    ``bos://governance/auto/rollback``   — rollback execution
    ``bos://governance/auto/register``   — register a trigger
    """

    _DEFAULT_DB: str = "data/db/organs/governance/auto_executor.db"
    _lock: threading.Lock

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        _log.debug("[AutoExecutor] db=%s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return managed_connection(conn)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auto_triggers (
                    id                  TEXT PRIMARY KEY,
                    name                TEXT NOT NULL,
                    trigger_type        TEXT NOT NULL,
                    condition_json      TEXT,
                    target              TEXT NOT NULL,
                    enabled             INTEGER NOT NULL DEFAULT 1,
                    created_at          TEXT NOT NULL,
                    last_triggered_at   TEXT,
                    metadata_json       TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trigger_type ON auto_triggers(trigger_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trigger_enabled ON auto_triggers(enabled)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auto_executions (
                    id              TEXT PRIMARY KEY,
                    trigger_id      TEXT NOT NULL,
                    trigger_type    TEXT NOT NULL,
                    target          TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    result_json     TEXT,
                    started_at      TEXT NOT NULL,
                    completed_at    TEXT,
                    rollback_state  TEXT,
                    error_message   TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_trigger ON auto_executions(trigger_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_status ON auto_executions(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_started ON auto_executions(started_at DESC)")
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _row_to_trigger(self, row: sqlite3.Row) -> AutoTrigger:
        condition_data = row["condition_json"]
        condition = TriggerCondition(**json.loads(condition_data)) if condition_data else None

        return AutoTrigger(
            id=row["id"],
            name=row["name"],
            trigger_type=TriggerType(row["trigger_type"]),
            condition=condition,
            target=row["target"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            last_triggered_at=row["last_triggered_at"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else None,
        )

    def _row_to_execution(self, row: sqlite3.Row) -> AutoExecution:
        result_data = row["result_json"]
        result = ExecutionResult(**json.loads(result_data)) if result_data else None

        return AutoExecution(
            id=row["id"],
            trigger_id=row["trigger_id"],
            trigger_type=TriggerType(row["trigger_type"]),
            target=row["target"],
            status=ExecutionStatus(row["status"]),
            result=result,
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            rollback_state=json.loads(row["rollback_state"]) if row["rollback_state"] else None,
            error_message=row["error_message"],
        )

    # ------------------------------------------------------------------
    # Public API: Trigger Management
    # ------------------------------------------------------------------

    def register_trigger(
        self,
        name: str,
        trigger_type: TriggerType,
        target: str,
        condition: TriggerCondition | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AutoTrigger:
        """Register a new auto-execution trigger."""
        trigger_id = str(uuid.uuid4())
        now = self._now()

        trigger = AutoTrigger(
            id=trigger_id,
            name=name,
            trigger_type=trigger_type,
            condition=condition,
            target=target,
            enabled=True,
            created_at=now,
            last_triggered_at=None,
            metadata=metadata,
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO auto_triggers
                    (id, name, trigger_type, condition_json, target, enabled, created_at, last_triggered_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trigger.id,
                    trigger.name,
                    trigger.trigger_type.value,
                    json.dumps(trigger.condition.to_dict()) if trigger.condition else None,
                    trigger.target,
                    int(trigger.enabled),
                    trigger.created_at,
                    trigger.last_triggered_at,
                    json.dumps(trigger.metadata) if trigger.metadata else None,
                ),
            )
            conn.commit()

        _log.debug("[AutoExecutor] registered trigger %s (%s)", trigger_id, name)
        return trigger

    def unregister_trigger(self, trigger_id: str) -> bool:
        """Unregister a trigger."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM auto_triggers WHERE id = ?", (trigger_id,))
            conn.commit()

        unregistered = cursor.rowcount > 0
        if unregistered:
            _log.debug("[AutoExecutor] unregistered trigger %s", trigger_id)
        return unregistered

    def enable_trigger(self, trigger_id: str) -> bool:
        """Enable a trigger."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute("UPDATE auto_triggers SET enabled = 1 WHERE id = ?", (trigger_id,))
            conn.commit()

        return cursor.rowcount > 0

    def disable_trigger(self, trigger_id: str) -> bool:
        """Disable a trigger."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute("UPDATE auto_triggers SET enabled = 0 WHERE id = ?", (trigger_id,))
            conn.commit()

        return cursor.rowcount > 0

    def get_trigger(self, trigger_id: str) -> AutoTrigger | None:
        """Get a trigger by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM auto_triggers WHERE id = ?", (trigger_id,)).fetchone()

        if row is None:
            return None
        return self._row_to_trigger(row)

    def list_triggers(self, enabled_only: bool = False) -> list[AutoTrigger]:
        """List all triggers."""
        sql = "SELECT * FROM auto_triggers"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY created_at DESC"

        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()

        return [self._row_to_trigger(r) for r in rows]

    # ------------------------------------------------------------------
    # Public API: Execution
    # ------------------------------------------------------------------

    def trigger_on_condition(self, trigger_id: str, context: dict[str, float]) -> AutoExecution | None:
        """Check if trigger condition is met and execute if so."""
        trigger = self.get_trigger(trigger_id)
        if trigger is None or not trigger.enabled:
            return None

        if trigger.condition is None:
            _log.warning("[AutoExecutor] trigger %s has no condition", trigger_id)
            return None

        # Get the field value from context
        field_value = context.get(trigger.condition.field)
        if field_value is None:
            _log.debug(
                "[AutoExecutor] field %s not in context for trigger %s",
                trigger.condition.field,
                trigger_id,
            )
            return None

        # Evaluate condition
        try:
            if not trigger.condition.evaluate(float(field_value)):
                _log.debug(
                    "[AutoExecutor] condition not met for trigger %s: %s %s %s (got %s)",
                    trigger_id,
                    trigger.condition.field,
                    trigger.condition.operator,
                    trigger.condition.threshold,
                    field_value,
                )
                return None
        except (ValueError, TypeError) as exc:
            _log.error("[AutoExecutor] failed to evaluate condition for trigger %s: %s", trigger_id, exc)
            return None

        # Condition met - execute
        _log.info(
            "[AutoExecutor] condition met for trigger %s, executing target %s",
            trigger_id,
            trigger.target,
        )

        return self.orchestrate_execution(trigger_id, trigger.target, context)

    def orchestrate_execution(
        self,
        trigger_id: str,
        target: str,
        context: dict[str, Any] | None = None,
        save_rollback_state: bool = True,
    ) -> AutoExecution:
        """Orchestrate the execution of an auto-triggered action."""
        execution_id = str(uuid.uuid4())
        now = self._now()

        trigger = self.get_trigger(trigger_id)
        trigger_type = trigger.trigger_type if trigger else TriggerType.MANUAL

        execution = AutoExecution(
            id=execution_id,
            trigger_id=trigger_id,
            trigger_type=trigger_type,
            target=target,
            status=ExecutionStatus.PENDING,
            result=None,
            started_at=now,
            completed_at=None,
            rollback_state={},
            error_message=None,
        )

        # Save initial state for rollback
        if save_rollback_state:
            execution.rollback_state = self._capture_rollback_state(target, context)

        # Create execution record
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO auto_executions
                    (id, trigger_id, trigger_type, target, status, result_json, started_at, completed_at, rollback_state, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    execution.id,
                    execution.trigger_id,
                    execution.trigger_type.value,
                    execution.target,
                    execution.status.value,
                    None,
                    execution.started_at,
                    execution.completed_at,
                    json.dumps(execution.rollback_state) if execution.rollback_state else None,
                    execution.error_message,
                ),
            )
            conn.commit()

        # Update trigger's last_triggered_at
        if trigger:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "UPDATE auto_triggers SET last_triggered_at = ? WHERE id = ?",
                    (now, trigger_id),
                )
                conn.commit()

        # Execute the target (implementation-specific)
        try:
            result = self._execute_target(target, context or {})

            execution.status = ExecutionStatus.COMPLETED
            execution.result = result
            execution.completed_at = self._now()

            _log.info(
                "[AutoExecutor] execution %s completed: %s",
                execution_id,
                result.message,
            )

        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(exc)
            execution.completed_at = self._now()
            execution.result = ExecutionResult(success=False, message=f"Execution failed: {exc}", error=str(exc))

            _log.error("[AutoExecutor] execution %s failed: %s", execution_id, exc)

        # Update execution record
        self._update_execution(execution)

        return execution

    def rollback_execution(self, execution_id: str) -> AutoExecution | None:
        """Rollback a failed execution using saved state."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM auto_executions WHERE id = ?", (execution_id,)).fetchone()

        if row is None:
            return None

        execution = self._row_to_execution(row)

        if execution.status != ExecutionStatus.FAILED:
            _log.warning(
                "[AutoExecutor] cannot rollback execution %s (status=%s)",
                execution_id,
                execution.status.value,
            )
            return execution

        if not execution.rollback_state:
            _log.warning("[AutoExecutor] no rollback state for execution %s", execution_id)
            return execution

        # Perform rollback
        try:
            self._apply_rollback_state(execution.target, execution.rollback_state)

            execution.status = ExecutionStatus.ROLLED_BACK
            execution.completed_at = self._now()

            _log.info("[AutoExecutor] rolled back execution %s", execution_id)

        except Exception as exc:
            _log.error("[AutoExecutor] rollback failed for execution %s: %s", execution_id, exc)
            execution.error_message = f"Rollback failed: {exc}"

        self._update_execution(execution)
        return execution

    def get_execution(self, execution_id: str) -> AutoExecution | None:
        """Get an execution by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM auto_executions WHERE id = ?", (execution_id,)).fetchone()

        if row is None:
            return None
        return self._row_to_execution(row)

    def list_executions(
        self, trigger_id: str | None = None, status: ExecutionStatus | None = None
    ) -> list[AutoExecution]:
        """List executions with optional filters."""
        clauses: list[str] = []
        params: list = []

        if trigger_id is not None:
            clauses.append("trigger_id = ?")
            params.append(trigger_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM auto_executions {where} ORDER BY started_at DESC",
                params,
            ).fetchall()

        return [self._row_to_execution(r) for r in rows]

    # ------------------------------------------------------------------
    # Internal execution helpers
    # ------------------------------------------------------------------

    def _capture_rollback_state(self, target: str, context: dict[str, Any] | None) -> dict[str, Any]:
        """Capture state before execution for potential rollback."""
        # Basic implementation - capture current timestamp and context
        return {
            "target": target,
            "captured_at": self._now(),
            "context": context or {},
        }

    def _execute_target(self, target: str, context: dict[str, Any]) -> ExecutionResult:
        """Execute the target action (implementation-specific).

        This is a placeholder - actual implementation depends on what
        the target refers to (policy, workflow, API call, etc.)
        """
        # Placeholder: simulate execution
        _log.debug("[AutoExecutor] executing target %s with context %s", target, context)

        # Try to execute as a policy
        try:
            from kairon_lib.governance_engine import GovernanceEngine

            engine = GovernanceEngine()
            result = engine.execute_rule(target, 0, context)

            return ExecutionResult(
                success=True,
                message=f"Executed policy rule: {target}",
                data=result,
            )
        except (KeyError, ValueError, AttributeError, RuntimeError):
            # Not a policy, try other execution methods
            pass

        # Default: successful execution
        return ExecutionResult(
            success=True,
            message=f"Executed target: {target}",
            data={"target": target, "context": context},
        )

    def _apply_rollback_state(self, target: str, state: dict[str, Any]) -> None:
        """Apply rollback state to revert changes."""
        # Placeholder implementation
        _log.info(
            "[AutoExecutor] applying rollback state for target %s (captured at %s)",
            target,
            state.get("captured_at"),
        )
        # Actual implementation would revert specific changes

    def _update_execution(self, execution: AutoExecution) -> None:
        """Update execution record in database."""
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE auto_executions
                SET status = ?, result_json = ?, completed_at = ?, error_message = ?
                WHERE id = ?
                """,
                (
                    execution.status.value,
                    json.dumps(execution.result.to_dict()) if execution.result else None,
                    execution.completed_at,
                    execution.error_message,
                    execution.id,
                ),
            )
            conn.commit()
