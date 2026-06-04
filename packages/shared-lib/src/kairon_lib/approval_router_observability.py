# ---
# domain: D-Governance
# layer: organ
# status: active
# ---
from __future__ import annotations

from typing import Any

"""Observability seam for ApprovalRouter audit and EventBus side effects."""

import logging

from kairon_lib.events import get_global_event_bus, make_event

_log = logging.getLogger(__name__)


def _load_optional_event_bus_module() -> Any | None:
    """Return the global EventBus singleton, or None if not yet registered.

    .. deprecated::
        Use :func:`get_global_event_bus` directly instead.  This wrapper
        remains only for backward compatibility of the exported name.
    """
    return get_global_event_bus()


def _emit_governance_event(event_type: str, payload: dict[str, object]) -> None:
    """Emit a best-effort EventBus event from ApprovalRouter — never raises."""
    bus = get_global_event_bus()
    if bus is None:
        return

    try:
        bus.publish(make_event(event_type, "approval_router", payload))
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        _log.debug("[ApprovalRouter] EventBus publish skipped: %s", exc)


class ApprovalObservability:
    """Own ApprovalRouter audit and EventBus side effects."""

    def __init__(self, audit_trail: Any | None = None) -> None:
        self._audit_trail = audit_trail

    def emit_request_submitted(
        self,
        *,
        request_id: str,
        request_type: str,
        requester: str,
    ) -> None:
        _emit_governance_event(
            "approval.requested",
            {
                "request_id": request_id,
                "type": request_type,
                "requester": requester,
            },
        )

    def emit_decision_recorded(
        self,
        *,
        request_id: str,
        decision: str,
        approver: str,
    ) -> None:
        event_name = "approval.granted" if decision == "approved" else "approval.denied"
        _emit_governance_event(
            event_name,
            {
                "request_id": request_id,
                "decision": decision,
                "approver": approver,
            },
        )

    def log_decision(
        self,
        *,
        request_id: str,
        decision: str,
        reason: str,
        approver: str,
    ) -> None:
        if self._audit_trail is None:
            return
        try:
            self._audit_trail.log_operation(
                operation_type=f"decision.{decision}",
                actor=approver,
                target=request_id,
                changes={
                    "decision": decision,
                    "reason": reason,
                    "request_id": request_id,
                },
            )
        except Exception as exc:
            _log.warning("Audit trail logging failed: %s", exc)


__all__ = [
    "ApprovalObservability",
    "_emit_governance_event",
    "_load_optional_event_bus_module",
]
