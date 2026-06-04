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
"""Human-in-the-loop confirmation mechanism for D-Governance.

---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Authority: EC-7/PB-3
Keywords: [hitl, human, confirmation, approval, governance, oversight]
---

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# HumanInTheLoop ≡ Organ
# 内涵 ≝ {request_id, action, context, status, created_at, expires_at}
# 外延 ⊢ {h | h ∈ D-Governance ∧ human_confirmation(h)}
# 功能 ⊢ {RequestConfirmation, WaitForConfirmation, ConfirmRequest,
#          RejectRequest, GetPendingRequests}
# S5 映射 ⊢ loyalty(@Prime) > autonomy(Self) — human has final authority
# =============================================================================

Manages the human confirmation workflow for high-risk AI operations.
Routes HIGH/CRITICAL risk items from ApprovalQueue into the HITL pipeline.

Usage::

    hitl = HumanInTheLoop()
    req = hitl.request_confirmation(
        action={"type": "delete_data", "target": "old_records"},
        context={"risk_level": "HIGH", "requester": "@Prime"}
    )
    confirmed = hitl.wait_for_confirmation(req.request_id, timeout_seconds=300)
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class HITLStatus(StrEnum):
    """Status of a human-in-the-loop confirmation request."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ConfirmationRequest:
    """Represents a single human-in-the-loop confirmation request."""

    request_id: str
    action: dict[str, object]
    context: dict[str, object]
    status: HITLStatus = HITLStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(seconds=300))
    confirmed_by: str | None = None
    rejection_reason: str | None = None

    def is_terminal(self) -> bool:
        """Return True if the request is in a terminal state."""
        return self.status in {HITLStatus.CONFIRMED, HITLStatus.REJECTED, HITLStatus.TIMEOUT}

    def is_expired(self) -> bool:
        """Return True if the request has expired."""
        return datetime.now(UTC) > self.expires_at

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "action": self.action,
            "context": self.context,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "confirmed_by": self.confirmed_by,
            "rejection_reason": self.rejection_reason,
        }


# ---------------------------------------------------------------------------
# HumanInTheLoop
# ---------------------------------------------------------------------------


class HumanInTheLoop:
    """Human-in-the-loop confirmation manager.

    Manages a queue of pending confirmation requests and coordinates
    with ApprovalQueue for HIGH/CRITICAL risk operations.

    BOS-URI endpoints
    -----------------
    ``bos://governance/hitl/request``   — submit a new confirmation request
    ``bos://governance/hitl/confirm``     — confirm a pending request
    ``bos://governance/hitl/reject``      — reject a pending request
    ``bos://governance/hitl/pending``     — list pending requests
    """

    def __init__(
        self,
        metadata_path: str = "organs/D-Governance/organs/human_in_the_loop.py",
    ) -> None:
        self._lock = threading.RLock()
        self._requests: dict[str, ConfirmationRequest] = {}
        self._history: list[ConfirmationRequest] = []
        self._approval_queue: Any = None  # Lazy-loaded
        self._conditions: dict[str, threading.Condition] = {}
        self.status = "ACTIVE"
        _log.info("HumanInTheLoop initialised")

    # ------------------------------------------------------------------
    # ApprovalQueue integration
    # ------------------------------------------------------------------

    def _get_approval_queue(self) -> Any:
        """Lazily load ApprovalQueue to avoid circular imports."""
        if self._approval_queue is None:
            try:
                from kairon_lib.approval_queue import ApprovalQueue

                self._approval_queue = ApprovalQueue()
            except (ImportError, OSError) as exc:
                _log.warning("[HITL] ApprovalQueue unavailable: %s", exc)
                self._approval_queue = True  # Mark unavailable, don't retry
        return self._approval_queue if self._approval_queue is not True else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_confirmation(
        self,
        action: dict[str, object],
        context: dict[str, object] | None = None,
        timeout_seconds: int = 300,
        requester: str = "system",
    ) -> ConfirmationRequest:
        """Submit a new human confirmation request.

        Parameters
        ----------
        action:
            The action requiring human confirmation.
        context:
            Additional context (risk_level, requester, etc.).
        timeout_seconds:
            Seconds until the request expires. Defaults to 300.
        requester:
            Identity of the requesting entity.

        Returns
        -------
        ConfirmationRequest
            The newly created confirmation request.
        """
        if not action or not isinstance(action, dict):
            raise ValueError("action must be a non-empty dict")

        if context is None:
            context = {}
        context = dict(context)
        context.setdefault("requester", requester)

        request_id = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(seconds=timeout_seconds)

        request = ConfirmationRequest(
            request_id=request_id,
            action=dict(action),
            context=context,
            status=HITLStatus.PENDING,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )

        with self._lock:
            self._requests[request_id] = request
            self._conditions[request_id] = threading.Condition(self._lock)

        _log.info(
            "[HITL] request_confirmation id=%s action=%s timeout=%ds requester=%s",
            request_id,
            action.get("type", "unknown"),
            timeout_seconds,
            requester,
        )

        # Also submit to ApprovalQueue if risk is HIGH or CRITICAL
        risk_raw = context.get("risk_level", "medium")
        if risk_raw in {"high", "critical"}:
            aq = self._get_approval_queue()
            if aq is not None:
                try:
                    aq.request_approval(
                        action=action,
                        context=context,
                        requester=requester,
                    )
                except Exception as exc:
                    _log.warning("[HITL] Failed to submit to ApprovalQueue: %s", exc)

        return request

    def wait_for_confirmation(
        self,
        request_id: str,
        timeout_seconds: int | None = None,
    ) -> bool:
        """Block until a confirmation request is resolved or times out.

        Parameters
        ----------
        request_id:
            ID of the confirmation request.
        timeout_seconds:
            Max seconds to wait. Uses request's expiry if None.

        Returns
        -------
        bool
            True if confirmed, False if rejected or timed out.
        """
        with self._lock:
            request = self._requests.get(request_id)
            if request is None:
                _log.warning("[HITL] wait_for_confirmation: unknown request_id %s", request_id)
                return False

            if request.is_terminal():
                return request.status == HITLStatus.CONFIRMED

            condition = self._conditions.get(request_id)
            if condition is None:
                self._conditions[request_id] = threading.Condition(self._lock)
                condition = self._conditions[request_id]

        # Compute absolute deadline
        if timeout_seconds is not None:
            deadline = datetime.now(UTC) + timedelta(seconds=timeout_seconds)
        else:
            deadline = request.expires_at

        remaining = (deadline - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            self._expire_request(request_id)
            return False

        with condition:
            while not request.is_terminal():
                remaining = (deadline - datetime.now(UTC)).total_seconds()
                if remaining <= 0:
                    self._expire_request(request_id)
                    return False
                condition.wait(timeout=remaining)
            return request.status == HITLStatus.CONFIRMED

    def confirm_request(
        self,
        request_id: str,
        confirmer: str = "@Prime",
    ) -> bool:
        """Confirm a pending confirmation request.

        Parameters
        ----------
        request_id:
            ID of the request to confirm.
        confirmer:
            Identity of the confirmer.

        Returns
        -------
        bool
            True if the request was successfully confirmed.
        """
        with self._lock:
            request = self._requests.get(request_id)
            if request is None:
                _log.warning("[HITL] confirm_request: unknown request_id %s", request_id)
                return False

            if request.is_terminal():
                _log.warning(
                    "[HITL] confirm_request: request %s already in terminal state %s",
                    request_id,
                    request.status.value,
                )
                return False

            request.status = HITLStatus.CONFIRMED
            request.confirmed_by = confirmer
            request.updated_at = datetime.now(UTC)

            # Move to history
            self._requests.pop(request_id, None)
            self._history.append(request)

            # Wake waiters
            condition = self._conditions.pop(request_id, None)
            if condition:
                with condition:
                    condition.notify_all()

        _log.info("[HITL] confirmed request_id=%s by %s", request_id, confirmer)
        return True

    def reject_request(
        self,
        request_id: str,
        reason: str,
        rejector: str = "@Prime",
    ) -> bool:
        """Reject a pending confirmation request.

        Parameters
        ----------
        request_id:
            ID of the request to reject.
        reason:
            Mandatory reason for rejection.
        rejector:
            Identity of the rejector.

        Returns
        -------
        bool
            True if the request was successfully rejected.
        """
        if not reason or not reason.strip():
            raise ValueError("reason must be a non-empty string")

        with self._lock:
            request = self._requests.get(request_id)
            if request is None:
                _log.warning("[HITL] reject_request: unknown request_id %s", request_id)
                return False

            if request.is_terminal():
                _log.warning(
                    "[HITL] reject_request: request %s already in terminal state %s",
                    request_id,
                    request.status.value,
                )
                return False

            request.status = HITLStatus.REJECTED
            request.rejection_reason = reason.strip()
            request.confirmed_by = rejector
            request.updated_at = datetime.now(UTC)

            # Move to history
            self._requests.pop(request_id, None)
            self._history.append(request)

            # Wake waiters
            condition = self._conditions.pop(request_id, None)
            if condition:
                with condition:
                    condition.notify_all()

        _log.info("[HITL] rejected request_id=%s by %s reason=%s", request_id, rejector, reason)
        return True

    def get_pending_requests(
        self,
        include_expired: bool = False,
    ) -> list[ConfirmationRequest]:
        """Return all pending confirmation requests.

        Parameters
        ----------
        include_expired:
            If True, include expired-but-unresolved requests.

        Returns
        -------
        list[ConfirmationRequest]
            Pending requests sorted by creation time (oldest first).
        """
        with self._lock:
            results = []
            for req in self._requests.values():
                if req.status != HITLStatus.PENDING:
                    continue
                if not include_expired and req.is_expired():
                    continue
                results.append(req)
            results.sort(key=lambda r: r.created_at)
            return results

    def get_request(self, request_id: str) -> ConfirmationRequest | None:
        """Retrieve a single request by ID (pending or history)."""
        with self._lock:
            pending = self._requests.get(request_id)
            if pending is not None:
                return pending
            for hist in reversed(self._history):
                if hist.request_id == request_id:
                    return hist
        return None

    def get_stats(self) -> dict[str, object]:
        """Return statistics about the HITL pipeline."""
        with self._lock:
            pending_list = [r for r in self._requests.values() if r.status == HITLStatus.PENDING]
            return {
                "pending_count": len(pending_list),
                "history_count": len(self._history),
                "history_by_status": {s.value: len([r for r in self._history if r.status == s]) for s in HITLStatus},
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _expire_request(self, request_id: str) -> None:
        """Mark a request as timed out (called by waiters or scheduler)."""
        with self._lock:
            request = self._requests.get(request_id)
            if request is None or request.is_terminal():
                return

            request.status = HITLStatus.TIMEOUT
            self._requests.pop(request_id, None)
            self._history.append(request)

            condition = self._conditions.pop(request_id, None)
            if condition:
                with condition:
                    condition.notify_all()

        _log.warning("[HITL] request timed out request_id=%s", request_id)

    # Required by CoreService — no-op for this organ
    def validate_access(self, operation: str, context: dict[str, object]) -> bool:
        return True

    def get_metadata(self) -> dict[str, object]:
        return {
            "name": "HumanInTheLoop",
            "domain": "D-Governance",
            "layer": "L4",
            "version": "1.0.0",
            "status": self.status,
        }

    def get_registry_info(self) -> dict[str, object]:
        return {
            "bos_uri": "bos://governance/hitl",
            "endpoints": [
                "bos://governance/hitl/request",
                "bos://governance/hitl/confirm",
                "bos://governance/hitl/reject",
                "bos://governance/hitl/pending",
            ],
        }
