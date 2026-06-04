from __future__ import annotations

import logging

_log = logging.getLogger(__name__)
"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
"""Emergency stop (kill switch) for D-Governance.

---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Authority: EC-7/PB-3
Keywords: [emergency, stop, kill, switch, halt, safety, governance]
---

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# EmergencyStop ≡ Organ
# 内涵 ≝ {stopped, stopped_at, stopped_by, reason, resume_allowed}
# 外延 ⊢ {e | e ∈ D-Governance ∧ emergency_stop(e)}
# 功能 ⊢ {EmergencyStop, Resume, IsStopped, GetStopHistory}
# S5 映射 ⊢ 用户随时可一键停止 AI 活动 — 最终控制权属于 @Prime
# =============================================================================

One-button emergency stop that halts all AI activities.
Scope: pending actions, scheduled tasks, active workflows.
This is the physical manifestation of S5: loyalty > autonomy.

Usage::

    stop = EmergencyStop()
    stop.emergency_stop(reason="User initiated", actor="@Prime")
    stop.resume(actor="@Prime")
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class StopStatus(StrEnum):
    """Status of the emergency stop mechanism."""

    RUNNING = "running"
    STOPPED = "stopped"
    RESUMING = "resuming"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class StopEvent:
    """Records an emergency stop or resume event."""

    id: str
    event_type: str  # "emergency_stop" | "resume"
    actor: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    cancelled_actions: int = 0
    stopped_tasks: int = 0
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "actor": self.actor,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "cancelled_actions": self.cancelled_actions,
            "stopped_tasks": self.stopped_tasks,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# EmergencyStop
# ---------------------------------------------------------------------------


class EmergencyStop:
    """Emergency stop (kill switch) for the digital twin.

    One-button halt of all AI activities. Scope includes:
    - Pending approval queue items
    - Scheduled tasks and jobs
    - Active workflows

    Embodies S5: "loyalty(@Prime) > autonomy(Self)" — the user always
    retains ultimate control and can stop the AI at any time.

    BOS-URI endpoints
    -----------------
    ``bos://governance/emergency/stop``     — trigger emergency stop
    ``bos://governance/emergency/resume``   — resume operations
    ``bos://governance/emergency/status``    — get current stop status
    ``bos://governance/emergency/history``  — get stop/resume history

    Singleton
    --------
    Use ``EmergencyStop.get_instance()`` for global shared state across the process.
    """

    _instance: EmergencyStop | None = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> EmergencyStop:
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        metadata_path: str = "organs/D_Governance/organs/emergency_stop.py",
    ) -> None:
        self._lock = threading.RLock()
        self._stopped = False
        self._stopped_at: str | None = None
        self._stopped_by: str | None = None
        self._stop_reason: str | None = None
        self._stop_events: list[StopEvent] = []
        self._status = StopStatus.RUNNING
        self._audit_trail: Any = None  # Lazy-loaded
        self._approval_queue: Any = None  # Lazy-loaded
        self._scheduled_tasks: dict[str, bool] = {}  # task_id -> active
        self.status = "ACTIVE"
        _log.info("EmergencyStop initialised (singleton=%s)", self._instance is self)

    # ------------------------------------------------------------------
    # Lazy loaders
    # ------------------------------------------------------------------

    def _get_audit_trail(self) -> Any:
        if self._audit_trail is None:
            try:
                from kairon_lib.audit_trail import (
                    AuditSeverity,
                    AuditTrail,
                    OperationType,
                )

                self._audit_trail = AuditTrail()
                self._audit_severity = AuditSeverity
                self._audit_op_type = OperationType
            except (ImportError, OSError) as exc:
                _log.warning("[EmergencyStop] AuditTrail unavailable: %s", exc)
                self._audit_trail = True
        return self._audit_trail if self._audit_trail is not True else None

    def _get_approval_queue(self) -> Any:
        if self._approval_queue is None:
            try:
                from kairon_lib.approval_queue import ApprovalQueue

                self._approval_queue = ApprovalQueue()
            except (ImportError, OSError) as exc:
                _log.warning("[EmergencyStop] ApprovalQueue unavailable: %s", exc)
                self._approval_queue = True
        return self._approval_queue if self._approval_queue is not True else None

    def _log_to_audit(self, event: StopEvent) -> None:
        audit = self._get_audit_trail()
        if audit is None:
            return
        try:
            sev = self._audit_severity.CRITICAL
            try:
                op_type_str = f"emergency_{event.event_type}"
                op_type = self._audit_op_type(op_type_str)
            except ValueError:
                op_type = self._audit_op_type.CUSTOM

            audit.log_operation(
                operation_type=op_type,
                actor=event.actor,
                target=f"emergency_stop:{event.id}",
                changes=event.to_dict(),
                severity=sev,
                metadata={"stop_event_id": event.id},
                correlation_id=event.id,
            )
        except Exception as exc:
            _log.warning("[EmergencyStop] Failed to write audit log: %s", exc)

    # ------------------------------------------------------------------
    # Scheduled task registry (for kill switch scope)
    # ------------------------------------------------------------------

    def register_scheduled_task(self, task_id: str) -> None:
        """Register a scheduled task so it can be stopped by emergency_stop."""
        with self._lock:
            self._scheduled_tasks[task_id] = self._stopped

    def unregister_scheduled_task(self, task_id: str) -> None:
        """Unregister a scheduled task."""
        with self._lock:
            self._scheduled_tasks.pop(task_id, None)

    def is_task_active(self, task_id: str) -> bool:
        """Check if a scheduled task is allowed to run."""
        with self._lock:
            was_stopped = self._scheduled_tasks.get(task_id, False)
            # Task was registered when stop was active
            if was_stopped:
                return False
            # Task is registered but stop is now active
            if self._stopped:
                self._scheduled_tasks[task_id] = True
                return False
            return True

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def emergency_stop(
        self,
        reason: str = "User initiated",
        actor: str = "@Prime",
    ) -> StopEvent:
        """Immediately stop all AI activities (kill switch).

        This method:
        1. Sets the global stop flag (atomically)
        2. Cancels all pending approval queue items
        3. Marks all registered scheduled tasks as stopped
        4. Writes to AuditTrail

        Parameters
        ----------
        reason:
            Why the stop was triggered.
        actor:
            Who triggered the stop.

        Returns
        -------
        StopEvent
            The stop event record.
        """
        if not reason or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        if not actor or not actor.strip():
            raise ValueError("actor must be a non-empty string")

        now = datetime.now(UTC)
        cancelled_actions = 0
        stopped_tasks = 0

        with self._lock:
            if self._stopped:
                _log.warning(
                    "[EmergencyStop] Already stopped at %s by %s — ignoring duplicate stop",
                    self._stopped_at,
                    self._stopped_by,
                )
                # Return existing stop event
                for event in reversed(self._stop_events):
                    if event.event_type == "emergency_stop":
                        return event

            self._stopped = True
            self._stopped_at = now.isoformat()
            self._stopped_by = actor.strip()
            self._stop_reason = reason.strip()
            self._status = StopStatus.STOPPED

            # Mark all scheduled tasks as stopped
            for task_id in self._scheduled_tasks:
                self._scheduled_tasks[task_id] = True
            stopped_tasks = len(self._scheduled_tasks)

        # Cancel pending approval queue items (outside main lock)
        approval_queue = self._get_approval_queue()
        if approval_queue is not None:
            try:
                cancelled_actions = approval_queue.cancel_all_pending(reason, actor)
            except Exception as exc:
                _log.warning("[EmergencyStop] Failed to cancel approval queue: %s", exc)

        event = StopEvent(
            id=str(uuid.uuid4()),
            event_type="emergency_stop",
            actor=actor.strip(),
            reason=reason.strip(),
            timestamp=now.isoformat(),
            cancelled_actions=cancelled_actions,
            stopped_tasks=stopped_tasks,
        )

        with self._lock:
            self._stop_events.append(event)

        _log.critical(
            "[EmergencyStop] KILL SWITCH ACTIVATED by %s reason=%s cancelled_actions=%d stopped_tasks=%d",
            actor,
            reason,
            cancelled_actions,
            stopped_tasks,
        )

        self._log_to_audit(event)

        return event

    def resume(
        self,
        actor: str = "@Prime",
        reason: str = "User initiated resume",
    ) -> StopEvent:
        """Resume all AI activities after an emergency stop.

        Parameters
        ----------
        actor:
            Who triggered the resume.
        reason:
            Why the resume was triggered.

        Returns
        -------
        StopEvent
            The resume event record.
        """
        if not actor or not actor.strip():
            raise ValueError("actor must be a non-empty string")
        if not reason or not reason.strip():
            raise ValueError("reason must be a non-empty string")

        now = datetime.now(UTC)
        cleared_tasks = 0

        with self._lock:
            if not self._stopped:
                _log.warning("[EmergencyStop] Not currently stopped — nothing to resume")
                # Return a no-op event
                return StopEvent(
                    id=str(uuid.uuid4()),
                    event_type="resume",
                    actor=actor.strip(),
                    reason="No-op: system was not stopped",
                    timestamp=now.isoformat(),
                    cancelled_actions=0,
                    stopped_tasks=0,
                )

            self._stopped = False
            self._stopped_at = None
            self._stopped_by = None
            self._stop_reason = None
            self._status = StopStatus.RUNNING

            # Clear stop flag from all registered tasks
            for task_id in self._scheduled_tasks:
                self._scheduled_tasks[task_id] = False
            cleared_tasks = len(self._scheduled_tasks)

        event = StopEvent(
            id=str(uuid.uuid4()),
            event_type="resume",
            actor=actor.strip(),
            reason=reason.strip(),
            timestamp=now.isoformat(),
            cancelled_actions=0,
            stopped_tasks=cleared_tasks,
        )

        with self._lock:
            self._stop_events.append(event)

        _log.info(
            "[EmergencyStop] RESUMED by %s reason=%s cleared_tasks=%d",
            actor,
            reason,
            cleared_tasks,
        )

        self._log_to_audit(event)

        return event

    def is_stopped(self) -> bool:
        """Return True if the emergency stop is active."""
        with self._lock:
            return self._stopped

    def get_status(self) -> dict[str, object]:
        """Return the current emergency stop status."""
        with self._lock:
            return {
                "stopped": self._stopped,
                "status": self._status.value,
                "stopped_at": self._stopped_at,
                "stopped_by": self._stopped_by,
                "stop_reason": self._stop_reason,
                "registered_tasks": len(self._scheduled_tasks),
                "stopped_tasks": sum(1 for v in self._scheduled_tasks.values() if v),
            }

    def get_stop_history(self, limit: int = 50) -> list[StopEvent]:
        """Return the history of stop/resume events.

        Parameters
        ----------
        limit:
            Maximum number of events to return.

        Returns
        -------
        list[StopEvent]
            Stop/resume events sorted by timestamp (newest first).
        """
        with self._lock:
            results = list(self._stop_events)
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]
