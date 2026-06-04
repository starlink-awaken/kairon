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
"""User-facing approval queue for D-Governance.

---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Authority: EC-7/PB-3
Keywords: [approval, queue, user, control, veto, governance, audit]
---

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# ApprovalQueue ≡ Organ
# 内涵 ≝ {queue_id, action, context, risk_level, status, requester, timestamp}
# 外延 ≝ {q | q ∈ D-Governance ∧ user_approval(q)}
# 功能 ⊢ {RequestApproval, Approve, Reject, GetPending, GetHistory, GetQueueStats}
# S5 映射 ⊢ loyalty(@Prime) > autonomy(Self) when conflict(values)
# =============================================================================

High-risk operations enter the approval queue for human review.
Captures user decisions and writes complete audit logs.

Usage::

    queue = ApprovalQueue()
    req = queue.request_approval(
        action={"type": "delete_data", "target": "old_records"},
        context={"risk_level": "HIGH"}
    )
    queue.approve(req.id, approver="@Prime")
    queue.reject(req.id, "insufficient backup", approver="@Prime")
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

_log = logging.getLogger(__name__)

_shared_instance: ApprovalQueue | None = None

# ---------------------------------------------------------------------------
# Risk level enum
# ---------------------------------------------------------------------------


class RiskLevel(StrEnum):
    """Risk classification for approval queue items."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_value(cls, value: str | None) -> RiskLevel:
        """Parse a risk level from a string, defaulting to MEDIUM."""
        if value is None:
            return cls.MEDIUM
        try:
            return cls(value.lower().strip())
        except ValueError:
            return cls.MEDIUM


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

_STATUS_PENDING = "pending"
_STATUS_APPROVED = "approved"
_STATUS_REJECTED = "rejected"
_STATUS_VETOED = "vetoed"
_STATUS_EXPIRED = "expired"

_VALID_STATUSES: frozenset[str] = frozenset(
    {
        _STATUS_PENDING,
        _STATUS_APPROVED,
        _STATUS_REJECTED,
        _STATUS_VETOED,
        _STATUS_EXPIRED,
    }
)

# Risk-to-committee mapping
_RISK_COMMITTEE: dict[RiskLevel, str] = {
    RiskLevel.LOW: "auto-approved",
    RiskLevel.MEDIUM: "human-review",
    RiskLevel.HIGH: "human-review",
    RiskLevel.CRITICAL: "prime-review",
}

# Risk-to-auto-approve flag
_AUTO_APPROVE_THRESHOLD: dict[RiskLevel, bool] = {
    RiskLevel.LOW: True,
    RiskLevel.MEDIUM: False,
    RiskLevel.HIGH: False,
    RiskLevel.CRITICAL: False,
}

_HIGH_BLAST_RADII: frozenset[str] = frozenset({"cluster", "global", "system"})

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ApprovalItem:
    """Represents a single item in the approval queue."""

    id: str
    action: dict[str, object]
    context: dict[str, object]
    risk_level: RiskLevel
    status: str = _STATUS_PENDING
    requester: str = "system"
    approver: str | None = None
    resolution_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_terminal(self) -> bool:
        """Return True if the item is in a terminal state."""
        return self.status in {_STATUS_APPROVED, _STATUS_REJECTED, _STATUS_VETOED, _STATUS_EXPIRED}

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "action": self.action,
            "context": self.context,
            "risk_level": self.risk_level.value,
            "status": self.status,
            "requester": self.requester,
            "approver": self.approver,
            "resolution_reason": self.resolution_reason,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ApprovalResult:
    """Result returned after approving or rejecting an item."""

    success: bool
    item_id: str
    action: str  # "approved" | "rejected" | "vetoed"
    reason: str
    approver: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


# ---------------------------------------------------------------------------
# ApprovalQueue
# ---------------------------------------------------------------------------


class ApprovalQueue:
    """User-facing approval queue for governance operations.

    High-risk operations are submitted to the queue for human review.
    All decisions are written to the AuditTrail for compliance.

    BOS-URI endpoints
    -----------------
    ``bos://governance/approval/request``  — request approval
    ``bos://governance/approval/approve``   — approve an item
    ``bos://governance/approval/reject``    — reject an item
    ``bos://governance/approval/pending``   — list pending items
    ``bos://governance/approval/history``   — get approval history
    """

    def __init__(
        self,
        metadata_path: str = "organs/D_Governance/organs/voting/approval_queue.py",
    ) -> None:
        self._lock = threading.RLock()
        self._queue: dict[str, ApprovalItem] = {}
        self._history: list[ApprovalItem] = []
        self._audit_trail: Any = None  # Lazy-loaded
        self.status = "ACTIVE"
        _log.info("ApprovalQueue initialised")

    @staticmethod
    def get_instance() -> ApprovalQueue:
        """Return the shared ApprovalQueue singleton."""
        global _shared_instance
        if _shared_instance is None:
            _shared_instance = ApprovalQueue()
        return _shared_instance

    @staticmethod
    def reset_instance() -> None:
        """Reset the shared instance (for testing)."""
        global _shared_instance
        _shared_instance = None

    # ------------------------------------------------------------------
    # Audit trail lazy loader
    # ------------------------------------------------------------------

    def _get_audit_trail(self) -> Any:
        """Lazily load AuditTrail to avoid circular imports."""
        if self._audit_trail is None:
            try:
                from kairon_lib.organs.audit.audit_trail import (  # type: ignore[import-not-found]
                    AuditSeverity,
                    AuditTrail,
                    OperationType,
                )

                self._audit_trail = AuditTrail()
                self._audit_trail_severity = AuditSeverity
                self._audit_trail_op_type = OperationType
            except (ImportError, OSError) as exc:
                _log.warning("[ApprovalQueue] AuditTrail unavailable: %s", exc)
                self._audit_trail = True  # Mark as unavailable, don't retry
        return self._audit_trail if self._audit_trail is not True else None

    def _log_to_audit(
        self,
        operation: str,
        item: ApprovalItem,
        approver: str,
        reason: str,
        severity: str = "info",
    ) -> None:
        """Write an audit entry to AuditTrail."""
        audit = self._get_audit_trail()
        if audit is None:
            return
        try:
            severity_enum = getattr(self._audit_trail_severity, severity.upper(), self._audit_trail_severity.INFO)
            op_type_str = f"approval_{operation}"
            try:
                op_type = self._audit_trail_op_type(op_type_str)
            except ValueError:
                op_type = self._audit_trail_op_type.CUSTOM

            audit.log_operation(
                operation_type=op_type,
                actor=approver,
                target=f"approval_queue:{item.id}",
                changes={
                    "action": item.action,
                    "context": item.context,
                    "risk_level": item.risk_level.value,
                    "status": item.status,
                    "resolution_reason": reason,
                },
                severity=severity_enum,
                metadata={"approval_item_id": item.id, "requester": item.requester},
                correlation_id=item.id,
            )
        except Exception as exc:
            _log.warning("[ApprovalQueue] Failed to write audit log: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _effective_risk_level(action: dict[str, object], context: dict[str, object]) -> RiskLevel:
        risk_raw = context.get("risk_level", "medium")
        risk_level = RiskLevel.from_value(str(risk_raw))

        context_scope = str(context.get("governance_scope", "")).strip().lower()
        action_scope = str(action.get("governance_scope", "")).strip().lower()
        governance_scope = context_scope or action_scope

        context_radius = str(context.get("blast_radius", "")).strip().lower()
        action_radius = str(action.get("blast_radius", "")).strip().lower()
        blast_radius = context_radius or action_radius

        is_high_blast = governance_scope == "cluster" or blast_radius in _HIGH_BLAST_RADII

        if is_high_blast and risk_level in {RiskLevel.LOW, RiskLevel.MEDIUM}:
            return RiskLevel.HIGH
        return risk_level

    def request_approval(
        self,
        action: dict[str, object],
        context: dict[str, object] | None = None,
        requester: str = "system",
    ) -> ApprovalItem:
        """Submit a high-risk operation to the approval queue.

        Parameters
        ----------
        action:
            The action to be approved (e.g. ``{"type": "delete_data", "target": "..."}``).
        context:
            Additional context including ``risk_level`` (low/medium/high/critical).
            Defaults to ``{"risk_level": "medium"}``.
        requester:
            Identity of the entity requesting approval.

        Returns
        -------
        ApprovalItem
            The newly created queue item.
        """
        if not action or not isinstance(action, dict):
            raise ValueError("action must be a non-empty dict")

        if context is None:
            context = {}
        context = dict(context)

        risk_level = self._effective_risk_level(action, context)
        context["risk_level"] = risk_level.value

        item = ApprovalItem(
            id=str(uuid.uuid4()),
            action=dict(action),
            context=context,
            risk_level=risk_level,
            status=_STATUS_PENDING,
            requester=requester,
        )

        with self._lock:
            self._queue[item.id] = item

        _log.info(
            "[ApprovalQueue] request_approval id=%s risk=%s requester=%s",
            item.id,
            risk_level.value,
            requester,
        )

        self._log_to_audit(
            "requested",
            item,
            requester,
            f"Approval requested for {action.get('type', 'unknown')} action (risk={risk_level.value})",
            severity="info",
        )

        # Auto-approve LOW risk items
        if _AUTO_APPROVE_THRESHOLD[risk_level]:
            self.approve(item.id, approver="system", reason="Auto-approved: LOW risk")

        return item

    def approve(
        self,
        action_id: str,
        approver: str = "@Prime",
        reason: str | None = None,
    ) -> ApprovalResult:
        """Approve a pending approval item.

        Parameters
        ----------
        action_id:
            ID of the item to approve.
        approver:
            Identity of the approver.
        reason:
            Optional reason for the approval.

        Returns
        -------
        ApprovalResult
            Result of the approval action.
        """
        if not action_id or not action_id.strip():
            raise ValueError("action_id must be a non-empty string")
        if not approver or not approver.strip():
            raise ValueError("approver must be a non-empty string")

        reason = reason or "Approved"

        with self._lock:
            item = self._queue.get(action_id)
            if item is None:
                _log.warning("[ApprovalQueue] approve: unknown action_id %s", action_id)
                return ApprovalResult(
                    success=False,
                    item_id=action_id,
                    action="rejected",
                    reason=f"Item {action_id} not found in queue",
                    approver=approver,
                )

            if item.is_terminal():
                return ApprovalResult(
                    success=False,
                    item_id=action_id,
                    action="rejected",
                    reason=f"Item {action_id} already in terminal state: {item.status}",
                    approver=approver,
                )

            item.status = _STATUS_APPROVED
            item.approver = approver.strip()
            item.resolution_reason = reason.strip()
            item.updated_at = datetime.now(UTC)

            self._queue.pop(action_id, None)
            self._history.append(item)

        _log.info(
            "[ApprovalQueue] approved id=%s by %s reason=%s",
            action_id,
            approver,
            reason,
        )

        self._log_to_audit(
            "approved",
            item,
            approver,
            reason,
            severity="info",
        )

        return ApprovalResult(
            success=True,
            item_id=action_id,
            action="approved",
            reason=reason,
            approver=approver,
        )

    def reject(
        self,
        action_id: str,
        reason: str,
        approver: str = "@Prime",
    ) -> ApprovalResult:
        """Reject a pending approval item.

        Parameters
        ----------
        action_id:
            ID of the item to reject.
        reason:
            Mandatory reason for the rejection.
        approver:
            Identity of the rejector.

        Returns
        -------
        ApprovalResult
            Result of the rejection action.
        """
        if not action_id or not action_id.strip():
            raise ValueError("action_id must be a non-empty string")
        if not reason or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        if not approver or not approver.strip():
            raise ValueError("approver must be a non-empty string")

        with self._lock:
            item = self._queue.get(action_id)
            if item is None:
                _log.warning("[ApprovalQueue] reject: unknown action_id %s", action_id)
                return ApprovalResult(
                    success=False,
                    item_id=action_id,
                    action="rejected",
                    reason=f"Item {action_id} not found in queue",
                    approver=approver,
                )

            if item.is_terminal():
                return ApprovalResult(
                    success=False,
                    item_id=action_id,
                    action="rejected",
                    reason=f"Item {action_id} already in terminal state: {item.status}",
                    approver=approver,
                )

            item.status = _STATUS_REJECTED
            item.approver = approver.strip()
            item.resolution_reason = reason.strip()
            item.updated_at = datetime.now(UTC)

            self._queue.pop(action_id, None)
            self._history.append(item)

        _log.info(
            "[ApprovalQueue] rejected id=%s by %s reason=%s",
            action_id,
            approver,
            reason,
        )

        self._log_to_audit(
            "rejected",
            item,
            approver,
            reason,
            severity="warning",
        )

        return ApprovalResult(
            success=True,
            item_id=action_id,
            action="rejected",
            reason=reason,
            approver=approver,
        )

    def get_pending(
        self,
        risk_level: RiskLevel | None = None,
        requester: str | None = None,
    ) -> list[ApprovalItem]:
        """Return all pending approval items.

        Parameters
        ----------
        risk_level:
            Optional filter by risk level.
        requester:
            Optional filter by requester.

        Returns
        -------
        list[ApprovalItem]
            Pending items sorted by creation time (oldest first).
        """
        with self._lock:
            results = [item for item in self._queue.values() if item.status == _STATUS_PENDING]

        if risk_level is not None:
            results = [item for item in results if item.risk_level == risk_level]

        if requester is not None:
            results = [item for item in results if item.requester == requester]

        results.sort(key=lambda i: i.created_at)
        return results

    def get_history(
        self,
        limit: int = 100,
        status: str | None = None,
    ) -> list[ApprovalItem]:
        """Return resolved approval items.

        Parameters
        ----------
        limit:
            Maximum number of items to return.
        status:
            Optional filter by final status (approved/rejected/vetoed).

        Returns
        -------
        list[ApprovalItem]
            Historical items sorted by update time (newest first).
        """
        with self._lock:
            results = list(self._history)

        if status is not None:
            results = [item for item in results if item.status == status]

        results.sort(key=lambda i: i.updated_at, reverse=True)
        return results[:limit]

    def get_item(self, action_id: str) -> ApprovalItem | None:
        """Retrieve a single item by ID (checks both pending and history)."""
        with self._lock:
            pending = self._queue.get(action_id)
            if pending is not None:
                return pending
            for item in reversed(self._history):
                if item.id == action_id:
                    return item
        return None

    def restore_pending(self, action_id: str) -> bool:
        """Restore a terminal item to pending for ingress-layer compensation."""
        with self._lock:
            pending = self._queue.get(action_id)
            if pending is not None:
                return pending.status == _STATUS_PENDING

            for index in range(len(self._history) - 1, -1, -1):
                item = self._history[index]
                if item.id != action_id:
                    continue
                if item.status not in {
                    _STATUS_APPROVED,
                    _STATUS_REJECTED,
                    _STATUS_VETOED,
                    _STATUS_EXPIRED,
                }:
                    return False
                del self._history[index]
                item.status = _STATUS_PENDING
                item.approver = None
                item.resolution_reason = None
                item.updated_at = datetime.now(UTC)
                self._queue[action_id] = item
                return True
        return False

    def get_queue_stats(self) -> dict[str, object]:
        """Return statistics about the approval queue."""
        with self._lock:
            pending_list = [i for i in self._queue.values() if i.status == _STATUS_PENDING]
            return {
                "pending_count": len(pending_list),
                "history_count": len(self._history),
                "pending_by_risk": {rl.value: len([i for i in pending_list if i.risk_level == rl]) for rl in RiskLevel},
                "history_by_status": {
                    "approved": len([i for i in self._history if i.status == _STATUS_APPROVED]),
                    "rejected": len([i for i in self._history if i.status == _STATUS_REJECTED]),
                    "vetoed": len([i for i in self._history if i.status == _STATUS_VETOED]),
                    "expired": len([i for i in self._history if i.status == _STATUS_EXPIRED]),
                },
            }

    def mark_vetoed(self, action_id: str, vetoer: str, reason: str) -> ApprovalResult:
        """Mark an item as vetoed by a user. Used by UserVeto."""
        with self._lock:
            item = self._queue.get(action_id)
            if item is None:
                # Check history
                for hist in self._history:
                    if hist.id == action_id:
                        item = hist
                        break
            if item is None:
                return ApprovalResult(
                    success=False,
                    item_id=action_id,
                    action="vetoed",
                    reason=f"Item {action_id} not found",
                    approver=vetoer,
                )

            if item.is_terminal():
                return ApprovalResult(
                    success=False,
                    item_id=action_id,
                    action="vetoed",
                    reason=f"Item {action_id} already in terminal state: {item.status}",
                    approver=vetoer,
                )

            item.status = _STATUS_VETOED
            item.approver = vetoer
            item.resolution_reason = reason
            item.updated_at = datetime.now(UTC)

            self._queue.pop(action_id, None)
            if item not in self._history:
                self._history.append(item)

        _log.warning(
            "[ApprovalQueue] VETOED id=%s by %s reason=%s",
            action_id,
            vetoer,
            reason,
        )

        self._log_to_audit(
            "vetoed",
            item,
            vetoer,
            reason,
            severity="critical",
        )

        return ApprovalResult(
            success=True,
            item_id=action_id,
            action="vetoed",
            reason=reason,
            approver=vetoer,
        )

    def cancel_all_pending(self, reason: str, actor: str = "system") -> int:
        """Cancel all pending items (used by emergency_stop). Returns count cancelled."""
        cancelled = 0
        with self._lock:
            for item_id in list(self._queue.keys()):
                item = self._queue[item_id]
                if item.status == _STATUS_PENDING:
                    item.status = _STATUS_EXPIRED
                    item.resolution_reason = f"Emergency stop: {reason}"
                    item.updated_at = datetime.now(UTC)
                    self._history.append(item)
                    self._queue.pop(item_id)
                    cancelled += 1
                    self._log_to_audit(
                        "cancelled",
                        item,
                        actor,
                        f"Emergency stop: {reason}",
                        severity="critical",
                    )

        _log.warning("[ApprovalQueue] Emergency stop cancelled %d pending items", cancelled)
        return cancelled
