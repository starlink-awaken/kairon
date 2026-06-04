from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Domain: D-Governance
Summary: "Approval ingress surface - handles governance/approval/* routes without becoming the truth store."
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Approval ≡ Module
# 内涵 ≝ {Approval}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Approval)}
# 功能 ⊢ {Init_Approval, Execute_Approval, Validate_Approval}
# =============================================================================


import logging
from dataclasses import asdict, is_dataclass
from typing import Any

from kairon_lib.governance.approval_router import (  # type: ignore[import-not-found]
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_ROUTED,
)
from kairon_lib.governance.approval_router import (
    ApprovalRouter as TruthApprovalRouter,
)

from .base import BaseGovernanceRouter

_log = logging.getLogger(__name__)
_truth_router = None
_TRUTH_REQUEST_CONTEXT_KEY = "truth_request_id"


def _get_truth_router() -> Any:
    global _truth_router
    if _truth_router is None:
        _truth_router = TruthApprovalRouter()
    return _truth_router


class ApprovalRouter(BaseGovernanceRouter):
    """Ingress surface for governance/approval/* endpoints.

    This router projects BOS-URI surfaces into D-Governance approval organs.
    It must not become a second approval truth store:
    - `voting/approval_router.py` owns routed approval lifecycle truth.
    - `voting/approval_queue.py` owns user-facing queue projection state.
    """

    @staticmethod
    def _success_result(result: Any) -> dict[str, object]:
        if hasattr(result, "to_dict"):
            payload = result.to_dict()
        elif is_dataclass(result):
            payload = asdict(result)
        else:
            payload = dict(result)
        return {
            "status": "success",
            "result": payload,
            "ownership": {
                "truth_owner": "organs/D-Governance/organs/voting/approval_router.py",
                "projection_owner": "organs/D-Governance/organs/voting/approval_queue.py",
                "ingress_surface": "organs/D-Governance/organs/governance/routes/approval.py",
            },
        }

    @staticmethod
    def _error_result(message: str, result: dict[str, object] | None = None) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": "error",
            "message": message,
            "ownership": {
                "truth_owner": "organs/D-Governance/organs/voting/approval_router.py",
                "projection_owner": "organs/D-Governance/organs/voting/approval_queue.py",
                "ingress_surface": "organs/D-Governance/organs/governance/routes/approval.py",
            },
        }
        if result is not None:
            payload["result"] = result
        return payload

    @staticmethod
    def _normalize_request_id(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    def _resolve_correlated_request_id(
        self,
        *,
        queue: Any,
        truth_router: Any,
        action_id: str,
        request_id: str | None,
    ) -> tuple[str | None, dict[str, object] | None]:
        queue_item = queue.get_item(action_id)
        if queue_item is None:
            return None, self._error_result(
                f"Approval item {action_id} not found in queue",
                result={
                    "success": False,
                    "item_id": action_id,
                    "action": "rejected",
                    "reason": f"Item {action_id} not found in queue",
                    "approver": "",
                },
            )

        mapped_request_id = self._normalize_request_id(
            getattr(queue_item, "context", {}).get(_TRUTH_REQUEST_CONTEXT_KEY)
        )
        if mapped_request_id is None:
            return None, self._error_result(
                f"Approval item {action_id} is missing a truth correlation",
                result={
                    "success": False,
                    "item_id": action_id,
                    "action": "rejected",
                    "reason": "Missing truth_request_id correlation",
                    "approver": "",
                },
            )
        if request_id is not None and request_id != mapped_request_id:
            return None, self._error_result(
                "request_id does not match action_id correlation",
                result={
                    "success": False,
                    "item_id": action_id,
                    "action": "rejected",
                    "reason": (f"request_id {request_id} does not match correlated request {mapped_request_id}"),
                    "approver": "",
                },
            )

        truth_request = truth_router.get_request(mapped_request_id)
        if truth_request is None:
            return None, self._error_result(
                f"Correlated truth request {mapped_request_id} was not found",
                result={
                    "success": False,
                    "item_id": action_id,
                    "action": "rejected",
                    "reason": f"Unknown truth request {mapped_request_id}",
                    "approver": "",
                },
            )
        if truth_request.status != STATUS_ROUTED:
            return None, self._error_result(
                f"Truth request {mapped_request_id} is not awaiting a decision",
                result={
                    "success": False,
                    "item_id": action_id,
                    "action": "rejected",
                    "reason": f"Truth request status is {truth_request.status}",
                    "approver": "",
                },
            )
        return mapped_request_id, None

    async def _handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        try:
            from kairon_lib.governance.approval_queue import (  # type: ignore[import-not-found]
                ApprovalQueue,
                RiskLevel,
            )

            queue = ApprovalQueue.get_instance()
            truth_router = _get_truth_router()
            params = params or {}

            action = params.get("action")
            if action == "request":
                action_payload = params.get("request_payload")
                if action_payload is None:
                    action_payload = params.get("payload")
                if not isinstance(action_payload, dict) or not action_payload:
                    return {
                        "status": "error",
                        "message": "request_payload must be a non-empty object",
                    }

                context = params.get("context", {})
                requester = params.get("requester", "user")
                request_type = str(action_payload.get("type") or context.get("domain") or "governance")

                request = truth_router.submit_request(
                    request_type=request_type,
                    payload=action_payload,
                    requester=requester,
                )
                committee_id = str(context.get("committee_id") or "human-review")
                truth_router.route_to_committee(request.id, committee_id)
                queue_context = dict(context)
                queue_context[_TRUTH_REQUEST_CONTEXT_KEY] = request.id
                item = queue.request_approval(
                    action=action_payload,
                    context=queue_context,
                    requester=requester,
                )
                if item.status == STATUS_APPROVED:
                    decision_synced = truth_router.record_decision(
                        request_id=request.id,
                        decision=STATUS_APPROVED,
                        reason=item.resolution_reason or "Approved",
                        approver=item.approver or "system",
                    )
                    if decision_synced is not True:
                        queue.restore_pending(item.id)
                        return self._error_result(
                            f"Failed to synchronize auto-approved request {request.id} to truth state"
                        )
                return {
                    "status": "success",
                    "request": request.to_dict(),
                    "item": item.to_dict(),
                    "ownership": {
                        "truth_owner": "organs/D-Governance/organs/voting/approval_router.py",
                        "projection_owner": "organs/D-Governance/organs/voting/approval_queue.py",
                        "ingress_surface": "organs/D-Governance/organs/governance/routes/approval.py",
                    },
                }
            elif action == "approve":
                action_id = params["action_id"]
                request_id = self._normalize_request_id(params.get("request_id"))
                resolved_request_id, resolution_error = self._resolve_correlated_request_id(
                    queue=queue,
                    truth_router=truth_router,
                    action_id=action_id,
                    request_id=request_id,
                )
                if resolution_error is not None:
                    return resolution_error
                result = queue.approve(
                    action_id=action_id,
                    approver=params.get("approver", "@Prime"),
                    reason=params.get("reason"),
                )
                if not result.success:
                    return self._error_result(
                        result.reason,
                        result={
                            "success": result.success,
                            "item_id": result.item_id,
                            "action": result.action,
                            "reason": result.reason,
                            "approver": result.approver,
                        },
                    )
                decision_recorded = truth_router.record_decision(
                    request_id=resolved_request_id,
                    decision=STATUS_APPROVED,
                    reason=params.get("reason", "Approved"),
                    approver=params.get("approver", "@Prime"),
                )
                if decision_recorded is not True:
                    queue.restore_pending(action_id)
                    return self._error_result(
                        f"Failed to record truth decision for request {resolved_request_id}",
                        result={
                            "success": False,
                            "item_id": action_id,
                            "action": "rejected",
                            "reason": "Projection change was rolled back after truth sync failure",
                            "approver": params.get("approver", "@Prime"),
                        },
                    )
                response = self._success_result(result)
                response["request_id"] = resolved_request_id
                return response
            elif action == "reject":
                action_id = params["action_id"]
                request_id = self._normalize_request_id(params.get("request_id"))
                resolved_request_id, resolution_error = self._resolve_correlated_request_id(
                    queue=queue,
                    truth_router=truth_router,
                    action_id=action_id,
                    request_id=request_id,
                )
                if resolution_error is not None:
                    return resolution_error
                result = queue.reject(
                    action_id=action_id,
                    reason=params.get("reason", "Rejected by user"),
                    approver=params.get("approver", "@Prime"),
                )
                if not result.success:
                    return self._error_result(
                        result.reason,
                        result={
                            "success": result.success,
                            "item_id": result.item_id,
                            "action": result.action,
                            "reason": result.reason,
                            "approver": result.approver,
                        },
                    )
                decision_recorded = truth_router.record_decision(
                    request_id=resolved_request_id,
                    decision=STATUS_REJECTED,
                    reason=params.get("reason", "Rejected by user"),
                    approver=params.get("approver", "@Prime"),
                )
                if decision_recorded is not True:
                    queue.restore_pending(action_id)
                    return self._error_result(
                        f"Failed to record truth decision for request {resolved_request_id}",
                        result={
                            "success": False,
                            "item_id": action_id,
                            "action": "rejected",
                            "reason": "Projection change was rolled back after truth sync failure",
                            "approver": params.get("approver", "@Prime"),
                        },
                    )
                response = self._success_result(result)
                response["request_id"] = resolved_request_id
                return response
            elif action == "pending":
                items = queue.get_pending(
                    risk_level=RiskLevel(params["risk_level"]) if params.get("risk_level") else None,
                    requester=params.get("requester"),
                )
                return {
                    "status": "success",
                    "pending": [i.to_dict() for i in items],
                    "ownership": {
                        "truth_owner": "organs/D-Governance/organs/voting/approval_router.py",
                        "projection_owner": "organs/D-Governance/organs/voting/approval_queue.py",
                        "ingress_surface": "organs/D-Governance/organs/governance/routes/approval.py",
                    },
                }
            elif action == "history":
                items = queue.get_history(
                    limit=params.get("limit", 100),
                    status=params.get("status"),
                )
                return {
                    "status": "success",
                    "history": [i.to_dict() for i in items],
                    "ownership": {
                        "truth_owner": "organs/D-Governance/organs/voting/approval_router.py",
                        "projection_owner": "organs/D-Governance/organs/voting/approval_queue.py",
                        "ingress_surface": "organs/D-Governance/organs/governance/routes/approval.py",
                    },
                }
            elif action == "stats":
                stats = queue.get_queue_stats()
                return {
                    "status": "success",
                    "stats": stats,
                    "ownership": {
                        "truth_owner": "organs/D-Governance/organs/voting/approval_router.py",
                        "projection_owner": "organs/D-Governance/organs/voting/approval_queue.py",
                        "ingress_surface": "organs/D-Governance/organs/governance/routes/approval.py",
                    },
                }
            return {"status": "error", "message": f"Unknown approval action: {action}"}
        except Exception as exc:
            _log.error(f"[D-Governance URI] approval_queue_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    def register_routes(self, register: Any) -> None:
        register("governance", "approval/request", self._handler)
        register("governance", "approval/approve", self._handler)
        register("governance", "approval/reject", self._handler)
        register("governance", "approval/pending", self._handler)
        register("governance", "approval/history", self._handler)
        register("governance", "approval/stats", self._handler)
