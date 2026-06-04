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
"""Approval routing engine for D-Governance.
---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Authority: EC-7/PB-3
Keywords: [approval, routing, governance, committee, decision, workflow]
---

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# ApprovalRouter ≡ Organ
# 内涵 ≝ {request_id, type, payload, requester, status, committee_id}
# 外延 ≝ {r | r ∈ D-Governance ∧ approval_request(r)}
# 功能 ⊢ {SubmitRequest, RouteToCommittee, RecordDecision, GetPending, GetHistory}
# =============================================================================

Handles workflow approvals, committee routing, and decision recording for B-OS
governance processes.  Supports in-memory operation (default) with optional
SQLite persistence for durability.

Usage::

    router = ApprovalRouter()
    req = router.submit_request("architecture", {"title": "Use async workers"}, "team-a")
    router.route_to_committee(req.id, "cto-committee")
    router.record_decision(req.id, "approved", "Aligns with roadmap", "@Prime")
    history = router.get_decision_history(req.id)
"""

import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from kairon_lib.approval_router_observability import (
    ApprovalObservability,
    _emit_governance_event,
    _load_optional_event_bus_module,
)
from kairon_lib.approval_router_persistence import ApprovalPersistence

_log = logging.getLogger(__name__)

__all__ = [
    "STATUS_PENDING",
    "STATUS_ROUTED",
    "STATUS_APPROVED",
    "STATUS_REJECTED",
    "STATUS_CANCELLED",
    "ApprovalRequest",
    "Decision",
    "ApprovalResult",
    "ApprovalRouter",
    "_emit_governance_event",
    "_load_optional_event_bus_module",
]

# ---------------------------------------------------------------------------
# CoreService — try both known import paths, fall back to plain object
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_ROUTED = "routed"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"

_VALID_STATUSES: frozenset[str] = frozenset(
    {STATUS_PENDING, STATUS_ROUTED, STATUS_APPROVED, STATUS_REJECTED, STATUS_CANCELLED}
)

# Allowed status transitions
_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_PENDING: frozenset({STATUS_ROUTED, STATUS_CANCELLED}),
    STATUS_ROUTED: frozenset({STATUS_APPROVED, STATUS_REJECTED, STATUS_CANCELLED}),
    STATUS_APPROVED: frozenset(),
    STATUS_REJECTED: frozenset(),
    STATUS_CANCELLED: frozenset(),
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRequest:
    """Represents a single approval request in the governance pipeline."""

    id: str
    type: str
    payload: dict[str, Any]
    requester: str
    status: str = STATUS_PENDING
    committee_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_terminal(self) -> bool:
        """Return True if the request is in a terminal (unchangeable) state."""
        return self.status in {STATUS_APPROVED, STATUS_REJECTED, STATUS_CANCELLED}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "requester": self.requester,
            "status": self.status,
            "committee_id": self.committee_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Decision:
    """Records a single decision event for an approval request."""

    id: str
    request_id: str
    decision: str  # "approved" | "rejected" | "routed" | "cancelled"
    reason: str
    approver: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def outcome(self) -> str:
        """Backward-compatible alias for older tests and shims."""
        return self.decision

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "decision": self.decision,
            "reason": self.reason,
            "approver": self.approver,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ApprovalResult:
    """Lightweight result returned by :meth:`ApprovalRouter.request_approval`."""

    approved: bool
    reason: str
    request_id: str = ""


# ---------------------------------------------------------------------------
# ApprovalRouter
# ---------------------------------------------------------------------------


class ApprovalRouter:
    """Governance approval routing engine.

    Manages the full lifecycle of approval requests:
    submit → route → decide (approve / reject / cancel).

    Parameters
    ----------
    db_path:
        Optional path to a SQLite database for persistent storage.  When
        *None* (default), all state is held in memory only.
    metadata_path:
        Passed through to ``CoreService`` for organ registration.
    """

    def __init__(
        self,
        db_path: str | None = None,
        metadata_path: str = "organs/D_Governance/organs/voting/approval_router.py",
        audit_trail: Any | None = None,
    ) -> None:
        self._lock = threading.RLock()

        # In-memory stores
        self._requests: dict[str, ApprovalRequest] = {}
        self._history: dict[str, list[Decision]] = {}  # request_id → decisions

        # Optional audit trail integration
        self._audit_trail = audit_trail
        self._observability = ApprovalObservability(audit_trail=audit_trail)

        # Optional SQLite persistence
        self._db_path = db_path
        self._persistence = ApprovalPersistence(db_path)

        self.status = "ACTIVE"
        _log.info("ApprovalRouter initialised (db=%s, audit=%s)", db_path or "in-memory", bool(audit_trail))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_request(
        self,
        request_type: str | None = None,
        payload: dict[str, Any] | None = None,
        requester: str = "",
        *,
        type: str | None = None,
    ) -> ApprovalRequest:
        """Create a new approval request with *pending* status.

        Parameters
        ----------
        request_type:
            Category of the request (e.g. ``"architecture"``, ``"budget"``,
            ``"policy"``).
        payload:
            Arbitrary structured data describing the request.
        requester:
            Identity of the entity submitting the request.

        Returns
        -------
        ApprovalRequest
            The newly created request (status = *pending*).
        """
        if request_type is not None and type is not None and request_type != type:
            raise ValueError("request_type and type must match when both are provided")

        resolved_request_type = request_type if request_type is not None else type
        if not resolved_request_type or not resolved_request_type.strip():
            raise ValueError("request_type must be a non-empty string")
        if payload is None:
            raise ValueError("payload must be provided")
        if not requester or not requester.strip():
            raise ValueError("requester must be a non-empty string")

        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            type=resolved_request_type.strip(),
            payload=dict(payload),
            requester=requester.strip(),
            status=STATUS_PENDING,
        )

        with self._lock:
            self._requests[req.id] = req
            self._history[req.id] = []
            self._persistence.insert_request(req)

        _log.debug(
            "Submitted request %s type=%s requester=%s",
            req.id,
            resolved_request_type,
            requester,
        )
        self._observability.emit_request_submitted(
            request_id=req.id,
            request_type=resolved_request_type,
            requester=requester,
        )
        return req

    def route_to_committee(self, request_id: str, committee_id: str) -> bool:
        """Assign a pending request to a committee for review.

        Parameters
        ----------
        request_id:
            ID of the request to route.
        committee_id:
            Target committee identifier.

        Returns
        -------
        bool
            ``True`` on success, ``False`` if the request does not exist or
            cannot be transitioned to *routed* state.
        """
        if not committee_id or not committee_id.strip():
            raise ValueError("committee_id must be a non-empty string")

        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                _log.warning("route_to_committee: unknown request %s", request_id)
                return False

            if STATUS_ROUTED not in _TRANSITIONS.get(req.status, frozenset()):
                _log.warning(
                    "route_to_committee: invalid transition %s → routed for %s",
                    req.status,
                    request_id,
                )
                return False

            req.committee_id = committee_id.strip()
            req.status = STATUS_ROUTED
            req.updated_at = datetime.now(UTC)

            decision = Decision(
                id=str(uuid.uuid4()),
                request_id=request_id,
                decision="routed",
                reason=f"Routed to committee {committee_id}",
                approver="system",
            )
            self._history[request_id].append(decision)

            self._persistence.update_request(req)
            self._persistence.insert_decision(decision)

        _log.debug("Routed request %s → committee %s", request_id, committee_id)
        return True

    def record_decision(
        self,
        request_id: str,
        decision: str,
        reason: str | None = None,
        approver: str | None = None,
        *,
        notes: str | None = None,
        decided_by: str | None = None,
    ) -> bool | Decision:
        """Record a final decision (approved / rejected / cancelled) on a request.

        Parameters
        ----------
        request_id:
            ID of the request being decided.
        decision:
            One of ``"approved"``, ``"rejected"``, ``"cancelled"``.
        reason:
            Human-readable rationale for the decision.
        approver:
            Identity of the decision-maker.

        Returns
        -------
        bool
            ``True`` on success, ``False`` if the transition is invalid.
        """
        decision = decision.lower().strip()
        if decision not in {STATUS_APPROVED, STATUS_REJECTED, STATUS_CANCELLED}:
            raise ValueError(f"decision must be one of approved/rejected/cancelled, got {decision!r}")
        resolved_reason = reason if reason is not None else notes
        resolved_approver = approver if approver is not None else decided_by
        legacy_return = reason is None and approver is None and (notes is not None or decided_by is not None)

        if not resolved_reason or not resolved_reason.strip():
            raise ValueError("reason must be a non-empty string")
        if not resolved_approver or not resolved_approver.strip():
            raise ValueError("approver must be a non-empty string")

        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                _log.warning("record_decision: unknown request %s", request_id)
                return False

            if decision not in _TRANSITIONS.get(req.status, frozenset()):
                if legacy_return and req.status == STATUS_PENDING and decision in {STATUS_APPROVED, STATUS_REJECTED}:
                    req.committee_id = req.committee_id or "legacy-compat"
                    req.status = STATUS_ROUTED
                    req.updated_at = datetime.now(UTC)
                    routed_decision = Decision(
                        id=str(uuid.uuid4()),
                        request_id=request_id,
                        decision=STATUS_ROUTED,
                        reason="Implicitly routed for legacy compatibility",
                        approver="system",
                    )
                    self._history[request_id].append(routed_decision)
                    self._persistence.update_request(req)
                    self._persistence.insert_decision(routed_decision)
                else:
                    _log.warning(
                        "record_decision: invalid transition %s → %s for %s",
                        req.status,
                        decision,
                        request_id,
                    )
                    return False

            if decision not in _TRANSITIONS.get(req.status, frozenset()):
                _log.warning(
                    "record_decision: invalid transition %s → %s for %s",
                    req.status,
                    decision,
                    request_id,
                )
                return False

            req.status = decision
            req.updated_at = datetime.now(UTC)

            dec = Decision(
                id=str(uuid.uuid4()),
                request_id=request_id,
                decision=decision,
                reason=resolved_reason.strip(),
                approver=resolved_approver.strip(),
            )
            self._history[request_id].append(dec)

            self._persistence.update_request(req)
            self._persistence.insert_decision(dec)

        _log.debug("Decision recorded for %s: %s by %s", request_id, decision, resolved_approver)
        self._observability.emit_decision_recorded(
            request_id=request_id,
            decision=decision,
            approver=resolved_approver.strip(),
        )
        self._observability.log_decision(
            request_id=request_id,
            decision=decision,
            reason=resolved_reason.strip(),
            approver=resolved_approver.strip(),
        )
        if legacy_return:
            return dec
        return True

    def get_pending_requests(self, domain: str | None = None) -> list[ApprovalRequest]:
        """Return all requests that are not in a terminal state.

        Parameters
        ----------
        domain:
            Optional filter by ``request_type``.  When supplied, only requests
            whose ``type`` matches (case-insensitive) are returned.

        Returns
        -------
        list[ApprovalRequest]
            Requests with status *pending* or *routed*, sorted by creation
            time (oldest first).
        """
        with self._lock:
            results = [r for r in self._requests.values() if not r.is_terminal()]

        if domain is not None:
            domain_lower = domain.lower().strip()
            results = [r for r in results if r.type.lower() == domain_lower]

        results.sort(key=lambda r: r.created_at)
        return results

    def get_decision_history(self, request_id: str) -> list[Decision]:
        """Return all decision events recorded for a given request.

        Parameters
        ----------
        request_id:
            ID of the request.

        Returns
        -------
        list[Decision]
            Chronologically ordered decision events (empty list if not found).
        """
        with self._lock:
            history = self._history.get(request_id)
            if history is None:
                return []
            return list(history)

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """Retrieve a single request by its ID."""
        with self._lock:
            return self._requests.get(request_id)

    def cancel_request(self, request_id: str, reason: str, approver: str) -> bool:
        """Convenience helper to cancel a request (delegates to record_decision)."""
        return self.record_decision(request_id, STATUS_CANCELLED, reason, approver)

    def request_approval(
        self,
        task_id: str,
        plan: dict[str, Any],
        requester: str = "system",
    ) -> ApprovalResult:
        """Gate execution on a CAREFUL-strategy plan.

        When the environment variable ``BOS_AUTO_APPROVE`` is set to a truthy
        value (``"true"``, ``"1"``, ``"yes"``) **or** when this is called in a
        test/CI context (default behaviour), the request is auto-approved so
        that pipelines are not blocked.  Human review can be enforced by
        setting ``BOS_AUTO_APPROVE=false``.

        Parameters
        ----------
        task_id:
            Identifier of the task/agent requesting execution.
        plan:
            The plan dict produced by :class:`NKSTaskPlanner` (contains
            ``strategy``, ``requires_approval``, etc.).
        requester:
            Identity label for audit logging.

        Returns
        -------
        ApprovalResult
            ``approved=True`` when auto-approved; ``approved=False`` when
            auto-approval is disabled (manual gate not yet implemented).
        """
        auto_approve_env = os.environ.get("BOS_AUTO_APPROVE", "true").strip().lower()
        auto_approve = auto_approve_env in {"true", "1", "yes"}

        req = self.submit_request(
            request_type="execution_strategy",
            payload={"task_id": task_id, "plan": plan},
            requester=requester,
        )
        _log.info(
            "[ApprovalRouter] request_approval task_id=%s req_id=%s auto_approve=%s",
            task_id,
            req.id,
            auto_approve,
        )

        if auto_approve:
            self.route_to_committee(req.id, "auto-approval")
            self.record_decision(req.id, STATUS_APPROVED, "auto-approved via BOS_AUTO_APPROVE", "system")
            _log.info("[ApprovalRouter] Auto-approved request %s for task %s", req.id, task_id)
            return ApprovalResult(approved=True, reason="auto-approved", request_id=req.id)

        # Manual gate: record as pending/routed and return rejected until a human acts
        self.route_to_committee(req.id, "human-review")
        _log.warning(
            "[ApprovalRouter] Manual approval required for task %s (request %s) — returning rejected",
            task_id,
            req.id,
        )
        return ApprovalResult(
            approved=False,
            reason="manual approval required; set BOS_AUTO_APPROVE=true to bypass",
            request_id=req.id,
        )

    def close(self) -> None:
        """Close the SQLite connection if open."""
        self._persistence.close()
