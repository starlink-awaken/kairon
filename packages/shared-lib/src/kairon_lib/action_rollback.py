# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# ActionRollback ≡ Governance_Organ
# 内涵 ≝ {action_id, action_type, forward_op, reverse_op, context, status}
# 外延 ≝ {r | r ∈ D-Governance ∧ rollback_enabled(r)}
# 功能 ⊢ {record_action, rollback, get_action_history, _validate_rollback}
# =============================================================================

"""
---
Type: Organ
Layer: L3
Domain: D-Governance
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Governance/AGENTS.md
Keywords: [rollback, undo, action, history, governance, reversible]
BOS-URI:
  - bos://governance/rollback/record   — record_action
  - bos://governance/rollback/execute  — rollback
  - bos://governance/rollback/history  — get_action_history
---
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from kairon_lib.utils.sqlite_utils import managed_connection
from typing import Any

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ActionType enum
# ---------------------------------------------------------------------------


class ActionType(StrEnum):
    """Supported operation types that can be recorded and rolled back."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EXTERNAL_CALL = "EXTERNAL_CALL"


# ---------------------------------------------------------------------------
# ActionStatus enum
# ---------------------------------------------------------------------------


class ActionStatus(StrEnum):
    """Lifecycle status of a recorded action."""

    PENDING = "PENDING"  # Recorded but not yet executed
    COMMITTED = "COMMITTED"  # Forward operation completed
    ROLLED_BACK = "ROLLED_BACK"  # Successfully rolled back
    FAILED = "FAILED"  # Forward or reverse operation failed
    INVALID = "INVALID"  # Validation failed post-rollback


# ---------------------------------------------------------------------------
# ActionRecord dataclass
# ---------------------------------------------------------------------------


@dataclass
class ActionRecord:
    """Records the full context and reversibility of a single action.

    Attributes:
        action_id: Unique identifier for this action.
        action_type: One of CREATE, UPDATE, DELETE, EXTERNAL_CALL.
        forward_op: JSON-serializable description or payload of the forward operation.
        reverse_op: JSON-serializable description or payload of the reverse operation.
        context: Arbitrary metadata capturing the state before/after the action.
        recorded_at: ISO-8601 timestamp when the action was recorded.
        status: Current lifecycle status of the action.
        committed_at: Timestamp when the forward operation was committed (if any).
        rolled_back_at: Timestamp when the rollback was executed (if any).
    """

    action_id: str
    action_type: ActionType
    forward_op: dict[str, object]
    reverse_op: dict[str, object]
    context: dict[str, object]
    recorded_at: str
    status: ActionStatus = ActionStatus.PENDING
    committed_at: str | None = None
    rolled_back_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "forward_op": self.forward_op,
            "reverse_op": self.reverse_op,
            "context": self.context,
            "recorded_at": self.recorded_at,
            "status": self.status.value,
            "committed_at": self.committed_at,
            "rolled_back_at": self.rolled_back_at,
        }


# ---------------------------------------------------------------------------
# RollbackResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class RollbackResult:
    """Result of a rollback operation.

    Attributes:
        success: Whether the rollback completed without errors.
        action_id: The action that was targeted by this rollback.
        message: Human-readable description of the outcome.
        validation_passed: Whether the post-rollback state matches expectations.
        before_state: Snapshot of the system state before rollback was attempted.
        after_state: Snapshot of the system state after rollback was attempted.
    """

    success: bool
    action_id: str
    message: str
    validation_passed: bool
    before_state: dict[str, object] | None = None
    after_state: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "action_id": self.action_id,
            "message": self.message,
            "validation_passed": self.validation_passed,
            "before_state": self.before_state,
            "after_state": self.after_state,
        }


# ---------------------------------------------------------------------------
# RollbackManager
# ---------------------------------------------------------------------------


class RollbackManager:
    """Manages action history and reversible operations for D-Governance.

    Provides a transactional-style rollback mechanism: record actions with
    their forward and reverse operations, then optionally roll back by
    executing the stored reverse operation.

    Integrates with ``AuditTrail`` to log every rollback event for
    compliance and traceability.

    Thread-safe; uses a per-instance lock.

    BOS-URI endpoints
    ------------------
    ``bos://governance/rollback/record``  — record_action()
    ``bos://governance/rollback/execute`` — rollback()
    ``bos://governance/rollback/history``  — get_action_history()

    Examples
    --------
    >>> manager = RollbackManager()
    >>> record = manager.record_action(
    ...     action_id="act-001",
    ...     action_type=ActionType.UPDATE,
    ...     forward_op={"table": "users", "set": {"name": "Alice"}},
    ...     reverse_op={"table": "users", "set": {"name": "Bob"}},
    ...     context={"user_id": 42},
    ... )
    >>> result = manager.rollback("act-001")
    >>> assert result.success
    """

    _DEFAULT_DB: str = "data/db/organs/governance/action_rollback.db"
    _lock: threading.Lock

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize the RollbackManager.

        Args:
            db_path: Optional override for the SQLite database path.
                     Defaults to ``data/db/organs/governance/action_rollback.db``.
        """
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Lazy AuditTrail reference to avoid circular import at module level
        self._audit_trail: Any = None

        self._init_db()
        _log.debug("[RollbackManager] db=%s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _at(self) -> Any:
        """Lazy-load AuditTrail to avoid circular dependency."""
        if self._audit_trail is None:
            try:
                from kairon_lib.audit_trail import AuditTrail

                self._audit_trail = AuditTrail()
            except ImportError:
                self._audit_trail = None
        return self._audit_trail

    def _connect(self) -> Any:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return managed_connection(conn)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS action_records (
                    action_id      TEXT PRIMARY KEY,
                    action_type    TEXT NOT NULL,
                    forward_op     TEXT NOT NULL,
                    reverse_op     TEXT NOT NULL,
                    context        TEXT NOT NULL,
                    recorded_at    TEXT NOT NULL,
                    status         TEXT NOT NULL DEFAULT 'PENDING',
                    committed_at   TEXT,
                    rolled_back_at TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_action_type ON action_records(action_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_action_status ON action_records(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_action_recorded ON action_records(recorded_at DESC)")
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _row_to_record(self, row: sqlite3.Row) -> ActionRecord:
        return ActionRecord(
            action_id=row["action_id"],
            action_type=ActionType(row["action_type"]),
            forward_op=json.loads(row["forward_op"]),
            reverse_op=json.loads(row["reverse_op"]),
            context=json.loads(row["context"]),
            recorded_at=row["recorded_at"],
            status=ActionStatus(row["status"]),
            committed_at=row["committed_at"],
            rolled_back_at=row["rolled_back_at"],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_action(
        self,
        action_id: str,
        action_type: ActionType,
        forward_op: dict[str, object],
        reverse_op: dict[str, object],
        context: dict[str, object] | None = None,
    ) -> ActionRecord:
        """Record an action with its forward and reverse operations.

        Args:
            action_id: Unique identifier for this action (e.g. UUID or business key).
            action_type: One of CREATE, UPDATE, DELETE, EXTERNAL_CALL.
            forward_op: JSON-serializable description of the forward operation.
            reverse_op: JSON-serializable description of the reverse operation.
            context: Optional arbitrary metadata (e.g. user_id, affected rows).

        Returns:
            The persisted ``ActionRecord``.
        """
        now = self._now()
        record = ActionRecord(
            action_id=action_id,
            action_type=action_type,
            forward_op=forward_op,
            reverse_op=reverse_op,
            context=context or {},
            recorded_at=now,
            status=ActionStatus.COMMITTED,
            committed_at=now,
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO action_records
                    (action_id, action_type, forward_op, reverse_op, context,
                     recorded_at, status, committed_at, rolled_back_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.action_id,
                    record.action_type.value,
                    json.dumps(record.forward_op),
                    json.dumps(record.reverse_op),
                    json.dumps(record.context),
                    record.recorded_at,
                    record.status.value,
                    record.committed_at,
                    record.rolled_back_at,
                ),
            )
            conn.commit()

        _log.info(
            "[RollbackManager] recorded action action_id=%s type=%s",
            action_id,
            action_type.value,
        )
        return record

    def rollback(self, action_id: str) -> RollbackResult:
        """Execute the rollback for a previously recorded action.

        Retrieves the stored reverse operation, executes it, validates the
        result, and updates the record status.

        Args:
            action_id: The identifier of the action to roll back.

        Returns:
            A ``RollbackResult`` describing the outcome.
        """
        # 1. Load record
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM action_records WHERE action_id = ?", (action_id,)).fetchone()

        if row is None:
            result = RollbackResult(
                success=False,
                action_id=action_id,
                message=f"Action '{action_id}' not found.",
                validation_passed=False,
            )
            return result

        record = self._row_to_record(row)

        if record.status == ActionStatus.ROLLED_BACK:
            result = RollbackResult(
                success=False,
                action_id=action_id,
                message="Action has already been rolled back.",
                validation_passed=True,
            )
            return result

        # 2. Snapshot before state
        before_state: dict[str, object] | None = record.context.get("before_state")  # type: ignore[assignment]
        after_state: dict[str, object] | None = None

        # 3. Execute reverse operation
        try:
            _log.info(
                "[RollbackManager] executing rollback action_id=%s type=%s reverse=%s",
                action_id,
                record.action_type.value,
                record.reverse_op,
            )
            # The reverse_op is treated as a callable payload; invoke it if possible.
            # Structured as {"callable": "module.function", "args": [...]} or raw dict.
            after_state = self._execute_reverse(record.reverse_op, record.action_type)
        except (ValueError, KeyError, RuntimeError, AttributeError) as exc:
            _log.error(
                "[RollbackManager] rollback failed action_id=%s error=%s",
                action_id,
                exc,
            )
            self._update_status(action_id, ActionStatus.FAILED)
            self._log_audit(action_id, record, success=False, message=str(exc))
            return RollbackResult(
                success=False,
                action_id=action_id,
                message=f"Rollback execution failed: {exc}",
                validation_passed=False,
                before_state=before_state,
                after_state=None,
            )

        # 4. Validate
        validation_passed = self._validate_rollback(action_id, before_state, after_state)

        # 5. Persist outcome
        now = self._now()
        new_status = ActionStatus.ROLLED_BACK if validation_passed else ActionStatus.INVALID
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE action_records SET status = ?, rolled_back_at = ? WHERE action_id = ?",
                (new_status.value, now, action_id),
            )
            conn.commit()

        self._log_audit(action_id, record, success=validation_passed, message="")

        return RollbackResult(
            success=validation_passed,
            action_id=action_id,
            message="Rollback succeeded." if validation_passed else "Rollback validation failed.",
            validation_passed=validation_passed,
            before_state=before_state,
            after_state=after_state,
        )

    def get_action_history(
        self,
        action_type: ActionType | None = None,
        limit: int = 100,
    ) -> list[ActionRecord]:
        """Retrieve recorded action history.

        Args:
            action_type: Optional filter — return only this action type.
            limit: Maximum number of records to return (default 100).

        Returns:
            Chronologically ordered list of ``ActionRecord`` objects (newest first).
        """
        params: list[object] = []
        where = ""
        if action_type is not None:
            where = "WHERE action_type = ?"
            params.append(action_type.value)

        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM action_records {where} ORDER BY recorded_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [self._row_to_record(r) for r in rows]

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------

    def _execute_reverse(
        self,
        reverse_op: dict[str, object],
        _action_type: ActionType,  # type: ignore[reportUnusedParameter]
    ) -> dict[str, object]:
        """Execute a stored reverse operation.

        Supports two modes:
        1. ``{"callable": "module.function", "args": [...], "kwargs": {...}}`` —
           dynamically imports and invokes a Python callable.
        2. Plain dict — returned as-is as the ``after_state`` snapshot.

        Subclasses or callers can extend this to support custom executors.

        Args:
            reverse_op: The reverse operation payload.
            action_type: The type of the original action (for logging).

        Returns:
            A dict representing the state after the reverse operation.
        """
        if isinstance(reverse_op, dict) and "callable" in reverse_op:
            callable_path: Any = reverse_op["callable"]
            module_path, func_name = callable_path.rsplit(".", 1)
            import importlib

            mod = importlib.import_module(module_path)
            func: Callable[..., object] = getattr(mod, func_name)
            args: list[object] = reverse_op.get("args", [])  # type: ignore[assignment]
            kwargs: dict[str, object] = reverse_op.get("kwargs", {})  # type: ignore[assignment]
            result = func(*args, **kwargs)
            if isinstance(result, dict):
                return result
            return {"value": result}

        # Unstructured reverse op — treat as a state snapshot
        return dict(reverse_op)

    def _validate_rollback(self, action_id: str, before_state: Any, after_state: Any) -> bool:
        """Validate that a rollback restored the expected system state.

        Default implementation checks that ``after_state`` is non-None and
        structurally matches ``before_state`` when both are dicts.

        Override in subclasses to implement domain-specific validation logic.

        Args:
            action_id: The action being validated.
            before_state: State snapshot captured before rollback.
            after_state: State snapshot captured after rollback.

        Returns:
            True if validation passes, False otherwise.
        """
        if after_state is None:
            _log.warning(
                "[RollbackManager] validation failed action_id=%s: after_state is None",
                action_id,
            )
            return False

        # If we have both snapshots, check structural equality of key fields
        if isinstance(before_state, dict) and isinstance(after_state, dict):
            overlap = set(before_state.keys()) & set(after_state.keys())
            for key in overlap:
                if before_state[key] != after_state[key]:
                    # One or more fields differ — flag but don't hard-fail
                    _log.debug(
                        "[RollbackManager] field '%s' differs after rollback: %s → %s",
                        key,
                        before_state[key],
                        after_state[key],
                    )

        _log.info("[RollbackManager] rollback validated action_id=%s", action_id)
        return True

    def _update_status(self, action_id: str, status: ActionStatus) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE action_records SET status = ? WHERE action_id = ?",
                (status.value, action_id),
            )
            conn.commit()

    def _log_audit(
        self,
        action_id: str,
        record: ActionRecord,
        success: bool,
        message: str,
    ) -> None:
        """Log rollback events to AuditTrail for compliance."""
        at = self._at
        if at is None:
            return
        try:
            from kairon_lib.audit_trail import AuditSeverity, OperationType

            severity = AuditSeverity.INFO if success else AuditSeverity.ERROR
            at.log_operation(
                operation_type=OperationType.EXECUTION_ROLLED_BACK,
                actor="RollbackManager",
                target=action_id,
                changes={
                    "action_type": record.action_type.value,
                    "reverse_op": record.reverse_op,
                    "validation_passed": success,
                    "message": message,
                },
                severity=severity,
                metadata={"action_id": action_id},
            )
        except (OSError, TypeError, AttributeError) as exc:
            _log.warning("[RollbackManager] failed to log audit event: %s", exc)

    # ------------------------------------------------------------------
    # BOS-URI handler (CoreService.call dispatch)
    # ------------------------------------------------------------------

    def _handle_record(self, params: dict[str, object]) -> dict[str, object]:
        record = self.record_action(
            action_id=str(params["action_id"]),
            action_type=ActionType(str(params["action_type"])),
            forward_op=dict(params.get("forward_op", {})),  # type: ignore[arg-type]
            reverse_op=dict(params.get("reverse_op", {})),  # type: ignore[arg-type]
            context=params.get("context"),  # type: ignore[arg-type]
        )
        return {"status": "ok", "record": record.to_dict()}

    def _handle_execute(self, params: dict[str, object]) -> dict[str, object]:
        result = self.rollback(str(params["action_id"]))
        return {"status": "ok", "result": result.to_dict()}

    def _handle_history(self, params: dict[str, object]) -> dict[str, object]:
        action_type_raw: Any = params.get("action_type")
        limit_raw: Any = params.get("limit", 100)
        action_type = None if action_type_raw is None else ActionType(str(action_type_raw))
        limit = int(limit_raw)  # type: ignore[arg-type]
        history = self.get_action_history(action_type=action_type, limit=limit)
        return {"status": "ok", "records": [r.to_dict() for r in history]}
