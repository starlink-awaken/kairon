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
"""User veto mechanism for D-Governance.

---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Authority: EC-7/PB-3
Keywords: [veto, user, control, governance, override, sovereignty]
---

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# UserVeto ≡ Organ
# 内涵 ≝ {veto_id, action_id, reason, vetoer, timestamp, status}
# 外延 ⊢ {v | v ∈ D-Governance ∧ user_veto(v)}
# 功能 ⊢ {Veto, GetPending, GetVetoHistory, RegisterVetoableAction}
# S5 映射 ⊢ loyalty(@Prime) > autonomy(Self) — 用户拥有最终否决权
# =============================================================================

Allows users to veto AI actions at any time, embodying S5:
"loyalty(@Prime) > autonomy(Self) when conflict(values)"

Usage::

    veto = UserVeto()
    veto.register_vetoable_action("send_email", risk_level="HIGH")
    result = veto.veto(action_id="action-123", reason="Not approved by user")
    pending = veto.get_pending_veto()
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Veto status enum
# ---------------------------------------------------------------------------


class VetoStatus(StrEnum):
    """Status of a veto entry."""

    ACTIVE = "active"  # Veto has been issued
    ACKNOWLEDGED = "acknowledged"  # System has acknowledged the veto
    EXECUTED = "executed"  # Veto action has been carried out
    DISMISSED = "dismissed"  # Veto was dismissed by user


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class VetoableAction:
    """An action that can be vetoed by the user."""

    action_id: str
    action_type: str
    description: str
    risk_level: str = "medium"
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    can_be_vetoed: bool = True


@dataclass
class VetoEntry:
    """A user veto entry."""

    id: str
    action_id: str
    action_type: str
    reason: str
    vetoer: str
    status: VetoStatus = VetoStatus.ACTIVE
    acknowledged_at: datetime | None = None
    executed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "reason": self.reason,
            "vetoer": self.vetoer,
            "status": self.status.value,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# UserVeto
# ---------------------------------------------------------------------------


class UserVeto:
    """User veto mechanism — embodies S5 (loyalty > autonomy).

    Gives the human user ultimate override power over any AI action.
    All vetoes are written to the AuditTrail for accountability.

    BOS-URI endpoints
    -----------------
    ``bos://governance/user/veto``           — issue a veto
    ``bos://governance/user/veto/pending``   — get pending vetoes
    ``bos://governance/user/veto/history``   — get veto history
    ``bos://governance/user/veto/register``  — register a vetoable action
    """

    def __init__(
        self,
        metadata_path: str = "organs/D_Governance/organs/user_veto.py",
    ) -> None:
        self._lock = threading.RLock()
        self._vetoable_actions: dict[str, VetoableAction] = {}
        self._veto_entries: dict[str, VetoEntry] = {}
        self._audit_trail: Any = None  # Lazy-loaded
        self._approval_queue: Any = None  # Lazy-loaded
        self.status = "ACTIVE"
        _log.info("UserVeto initialised")

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
                _log.warning("[UserVeto] AuditTrail unavailable: %s", exc)
                self._audit_trail = True
        return self._audit_trail if self._audit_trail is not True else None

    def _get_approval_queue(self) -> Any:
        if self._approval_queue is None:
            try:
                from kairon_lib.approval_queue import ApprovalQueue

                self._approval_queue = ApprovalQueue()
            except (ImportError, OSError) as exc:
                _log.warning("[UserVeto] ApprovalQueue unavailable: %s", exc)
                self._approval_queue = True
        return self._approval_queue if self._approval_queue is not True else None

    def _log_to_audit(
        self,
        entry: VetoEntry,
        operation: str,
        severity: str = "warning",
    ) -> None:
        audit = self._get_audit_trail()
        if audit is None:
            return
        try:
            sev = getattr(self._audit_severity, severity.upper(), self._audit_severity.WARNING)
            try:
                op_type = self._audit_op_type(f"user_veto_{operation}")
            except ValueError:
                op_type = self._audit_op_type.CUSTOM

            audit.log_operation(
                operation_type=op_type,
                actor=entry.vetoer,
                target=f"user_veto:{entry.id}",
                changes={
                    "action_id": entry.action_id,
                    "action_type": entry.action_type,
                    "reason": entry.reason,
                    "status": entry.status.value,
                },
                severity=sev,
                metadata={"veto_entry_id": entry.id},
                correlation_id=entry.id,
            )
        except Exception as exc:
            _log.warning("[UserVeto] Failed to write audit log: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_vetoable_action(
        self,
        action_id: str,
        action_type: str,
        description: str = "",
        risk_level: str = "medium",
    ) -> VetoableAction:
        """Register an action as vetoable by the user.

        Parameters
        ----------
        action_id:
            Unique identifier for the action.
        action_type:
            Category of the action (e.g. "send_email", "delete_data").
        description:
            Human-readable description of the action.
        risk_level:
            Risk level (low/medium/high/critical).

        Returns
        -------
        VetoableAction
            The registered vetoable action.
        """
        if not action_id or not action_id.strip():
            raise ValueError("action_id must be a non-empty string")
        if not action_type or not action_type.strip():
            raise ValueError("action_type must be a non-empty string")

        action = VetoableAction(
            action_id=action_id.strip(),
            action_type=action_type.strip(),
            description=description,
            risk_level=risk_level.lower(),
        )

        with self._lock:
            self._vetoable_actions[action_id] = action

        _log.info(
            "[UserVeto] Registered vetoable action id=%s type=%s risk=%s",
            action_id,
            action_type,
            risk_level,
        )
        return action

    def veto(
        self,
        action_id: str,
        reason: str,
        vetoer: str = "@Prime",
        metadata: dict[str, object] | None = None,
    ) -> VetoEntry:
        """Issue a veto on an action.

        This is the primary user-facing veto method. It:
        1. Creates a veto entry
        2. Marks the action as non-vetoable (can_be_vetoed=False)
        3. Writes to AuditTrail
        4. Notifies ApprovalQueue (if available)

        Parameters
        ----------
        action_id:
            ID of the action to veto.
        reason:
            Mandatory reason for the veto.
        vetoer:
            Identity of the veto issuer.
        metadata:
            Additional metadata.

        Returns
        -------
        VetoEntry
            The created veto entry.
        """
        if not action_id or not action_id.strip():
            raise ValueError("action_id must be a non-empty string")
        if not reason or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        if not vetoer or not vetoer.strip():
            raise ValueError("vetoer must be a non-empty string")

        # Get action type from registered actions
        action_type = "unknown"
        can_be_vetoed = True
        with self._lock:
            registered = self._vetoable_actions.get(action_id)
            if registered is not None:
                action_type = registered.action_type
                can_be_vetoed = registered.can_be_vetoed

        entry = VetoEntry(
            id=str(uuid.uuid4()),
            action_id=action_id.strip(),
            action_type=action_type,
            reason=reason.strip(),
            vetoer=vetoer.strip(),
            status=VetoStatus.ACTIVE,
            metadata=metadata or {},
        )

        with self._lock:
            self._veto_entries[entry.id] = entry
            # Mark the action as no longer vetoable (it's been vetoed)
            if action_id in self._vetoable_actions:
                self._vetoable_actions[action_id].can_be_vetoed = False

        _log.warning(
            "[UserVeto] VETO ISSUED id=%s action=%s by %s reason=%s",
            entry.id,
            action_id,
            vetoer,
            reason,
        )

        self._log_to_audit(entry, "issued", severity="critical")

        # Notify the ApprovalQueue to mark this as vetoed
        approval_queue = self._get_approval_queue()
        if approval_queue is not None and can_be_vetoed:
            try:
                approval_queue.mark_vetoed(action_id, vetoer, reason)
            except Exception as exc:
                _log.warning("[UserVeto] Failed to notify ApprovalQueue: %s", exc)

        return entry

    def acknowledge_veto(self, veto_id: str) -> bool:
        """Acknowledge a veto entry (system confirms it received the veto)."""
        with self._lock:
            entry = self._veto_entries.get(veto_id)
            if entry is None:
                return False
            entry.status = VetoStatus.ACKNOWLEDGED
            entry.acknowledged_at = datetime.now(UTC)

        self._log_to_audit(entry, "acknowledged", severity="info")
        _log.info("[UserVeto] Veto acknowledged id=%s", veto_id)
        return True

    def execute_veto(self, veto_id: str) -> bool:
        """Mark a veto as executed (action has been stopped)."""
        with self._lock:
            entry = self._veto_entries.get(veto_id)
            if entry is None:
                return False
            entry.status = VetoStatus.EXECUTED
            entry.executed_at = datetime.now(UTC)

        self._log_to_audit(entry, "executed", severity="info")
        _log.info("[UserVeto] Veto executed id=%s", veto_id)
        return True

    def dismiss_veto(self, veto_id: str, dismisser: str = "@Prime") -> bool:
        """Dismiss a veto entry (user decides to let the action proceed)."""
        with self._lock:
            entry = self._veto_entries.get(veto_id)
            if entry is None:
                return False
            entry.status = VetoStatus.DISMISSED

        self._log_to_audit(entry, "dismissed", severity="info")
        _log.info("[UserVeto] Veto dismissed id=%s by %s", veto_id, dismisser)
        return True

    def get_pending_veto(self) -> list[VetoEntry]:
        """Return all active (not yet executed/dismissed) veto entries.

        Returns
        -------
        list[VetoEntry]
            Pending veto entries sorted by creation time (newest first).
        """
        with self._lock:
            results = [
                entry
                for entry in self._veto_entries.values()
                if entry.status in (VetoStatus.ACTIVE, VetoStatus.ACKNOWLEDGED)
            ]
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results

    def get_veto_history(
        self,
        action_id: str | None = None,
        vetoer: str | None = None,
        limit: int = 100,
    ) -> list[VetoEntry]:
        """Return veto history with optional filters.

        Parameters
        ----------
        action_id:
            Filter by specific action.
        vetoer:
            Filter by vetoer.
        limit:
            Maximum entries to return.

        Returns
        -------
        list[VetoEntry]
            Historical veto entries sorted by creation time (newest first).
        """
        with self._lock:
            results = list(self._veto_entries.values())

        if action_id is not None:
            results = [e for e in results if e.action_id == action_id]
        if vetoer is not None:
            results = [e for e in results if e.vetoer == vetoer]

        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]

    def get_veto_entry(self, veto_id: str) -> VetoEntry | None:
        """Retrieve a single veto entry by ID."""
        with self._lock:
            return self._veto_entries.get(veto_id)

    def is_action_vetoed(self, action_id: str) -> bool:
        """Check if an action currently has an active veto."""
        with self._lock:
            for entry in self._veto_entries.values():
                if entry.action_id == action_id and entry.status == VetoStatus.ACTIVE:
                    return True
        return False

    def get_vetoable_actions(
        self,
        action_type: str | None = None,
    ) -> list[VetoableAction]:
        """Return all registered vetoable actions.

        Parameters
        ----------
        action_type:
            Optional filter by action type.

        Returns
        -------
        list[VetoableAction]
            Vetoable actions that can still be vetoed.
        """
        with self._lock:
            results = [a for a in self._vetoable_actions.values() if a.can_be_vetoed]

        if action_type is not None:
            results = [a for a in results if a.action_type == action_type]

        return results

    def get_veto_stats(self) -> dict[str, object]:
        """Return veto statistics."""
        with self._lock:
            all_entries = list(self._veto_entries.values())
            return {
                "total_vetoes": len(all_entries),
                "active_vetoes": len([e for e in all_entries if e.status == VetoStatus.ACTIVE]),
                "acknowledged_vetoes": len([e for e in all_entries if e.status == VetoStatus.ACKNOWLEDGED]),
                "executed_vetoes": len([e for e in all_entries if e.status == VetoStatus.EXECUTED]),
                "dismissed_vetoes": len([e for e in all_entries if e.status == VetoStatus.DISMISSED]),
                "registered_actions": len(self._vetoable_actions),
                "vetoable_actions": len([a for a in self._vetoable_actions.values() if a.can_be_vetoed]),
            }
