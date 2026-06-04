# ---
# domain: D-Governance
# layer: organ
# status: active
# ---
from __future__ import annotations
from typing import Any

"""Observability seam for ApprovalRouter audit and EventBus side effects."""

import importlib
import logging

_log = logging.getLogger(__name__)
def _load_optional_event_bus_module() -> Any | None:
    """Load EventBus lazily without leaking import failures into governance flows."""
    module_path = "organs.D_Execution.organs.engine.event_bus"
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        _log.debug("[ApprovalRouter] EventBus module unavailable: %s", exc)
        return None
    except ImportError as exc:
        _log.debug("[ApprovalRouter] failed to import EventBus module: %s", exc)
        return None


def _emit_governance_event(event_type: str, payload: dict[str, object]) -> None:
    """Emit a best-effort EventBus event from ApprovalRouter — never raises."""
    event_bus_module = _load_optional_event_bus_module()
    if event_bus_module is None:
        return

    try:
        event_bus = event_bus_module.EventBus
        make_event = event_bus_module.make_event
    except AttributeError as exc:
        _log.debug("[ApprovalRouter] EventBus API unavailable: %s", exc)
        return

    try:
        event_bus.get_instance().publish(make_event(event_type, "approval_router", payload))
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
