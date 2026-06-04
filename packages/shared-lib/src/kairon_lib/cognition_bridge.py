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
# Cognition Loop Bridge ≡ Module
# 内涵 ≝ {Cognition, Loop, Bridge}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CognitionLoopBridge)}
# 功能 ⊢ {Cognition_Loop, Loop_Bridge, Bridge_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

"""Reusable cognition-loop orchestration over existing governance primitives."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from kairon_lib.organs.cognitive.cognitive_loop import CognitiveLoop
from kairon_lib.organs.voting.approval_router import ApprovalRouter


@dataclass
class CognitionLoopRecord:
    iteration_id: str
    request_id: str
    request_status: str
    recommended_mode: str
    action: str
    approved: bool


class CognitionLoopBridge:
    """Turn a perception payload into a governed cognition decision."""

    def __init__(self, cognitive_loop: CognitiveLoop | None = None) -> None:
        self._cognitive_loop = cognitive_loop or CognitiveLoop()

    def run(
        self,
        *,
        perception_event: dict[str, Any],
        approval_router: ApprovalRouter,
        requester: str,
        committee_id: str = "",
        auto_approve: bool = False,
        event_publisher: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> CognitionLoopRecord:
        iteration = self._cognitive_loop.run_iteration(dict(perception_event))
        think_output = dict(iteration.outputs.get("think", {}))
        act_output = dict(iteration.outputs.get("act", {}))

        request = approval_router.submit_request(
            "cognition",
            {
                "perception_event": dict(perception_event),
                "recommended_mode": think_output.get("recommended_mode", "react"),
                "action": act_output.get("action", "execute_default"),
            },
            requester=requester,
        )

        resolved_committee_id = committee_id.strip() or "cognition-auto-committee"
        approval_router.route_to_committee(request.id, resolved_committee_id)

        approved = False
        if auto_approve:
            approval_router.record_decision(
                request.id,
                "approved",
                "Auto-approved cognition loop result",
                requester,
            )
            approved = True
            request.status = "approved"

        payload = {
            "iteration_id": iteration.id,
            "request_id": request.id,
            "request_status": request.status,
            "recommended_mode": think_output.get("recommended_mode", "react"),
            "action": act_output.get("action", "execute_default"),
            "approved": approved,
        }
        if event_publisher is not None:
            event_publisher("cognition.loop.completed", payload)

        return CognitionLoopRecord(
            iteration_id=iteration.id,
            request_id=request.id,
            request_status=request.status,
            recommended_mode=payload["recommended_mode"],
            action=payload["action"],
            approved=approved,
        )


__all__ = ["CognitionLoopBridge", "CognitionLoopRecord"]
