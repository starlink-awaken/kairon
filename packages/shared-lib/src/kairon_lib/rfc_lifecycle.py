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
# Rfc Lifecycle Manager ≡ Manager
# 内涵 ≝ {Rfc, Lifecycle, Manager}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, RfcLifecycleManager)}
# 功能 ⊢ {Rfc_Lifecycle, Lifecycle_Manager, Manager_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RFCState(Enum):
    DRAFT = "draft"
    OPEN = "open"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    ENFORCED = "enforced"
    WITHDRAWN = "withdrawn"


VALID_TRANSITIONS: dict[RFCState, list[RFCState]] = {
    RFCState.DRAFT: [RFCState.OPEN, RFCState.WITHDRAWN],
    RFCState.OPEN: [RFCState.REVIEWING, RFCState.WITHDRAWN],
    RFCState.REVIEWING: [RFCState.APPROVED, RFCState.REJECTED, RFCState.WITHDRAWN],
    RFCState.APPROVED: [RFCState.ENFORCED, RFCState.WITHDRAWN],
    RFCState.REJECTED: [RFCState.WITHDRAWN],
    RFCState.ENFORCED: [],
    RFCState.WITHDRAWN: [],
}


@dataclass
class RFC:
    rfc_id: str
    title: str
    author: str
    state: RFCState = RFCState.DRAFT
    created_at: float = 0.0
    body: str = ""
    reviewers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


class RFCLifecycleManager:
    metadata_path = "organs/D-Governance/organs/rfc_lifecycle_manager.py"

    def __init__(self) -> None:
        self._rfcs: dict[str, RFC] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}

    def _transition(self, rfc: RFC, new_state: RFCState, actor: str = "", detail: str = "") -> RFC:
        if new_state not in VALID_TRANSITIONS.get(rfc.state, []):
            raise ValueError(f"Invalid transition: {rfc.state.value} -> {new_state.value}")
        old = rfc.state
        rfc.state = new_state
        self._history.setdefault(rfc.rfc_id, []).append(
            {
                "from": old.value,
                "to": new_state.value,
                "actor": actor,
                "detail": detail,
                "timestamp": time.time(),
            }
        )
        return rfc

    def create_rfc(self, title: str, author: str, body: str = "") -> RFC:
        rfc_id = f"RFC-{uuid.uuid4().hex[:8]}"
        rfc = RFC(rfc_id=rfc_id, title=title, author=author, body=body, created_at=time.time())
        self._rfcs[rfc_id] = rfc
        self._history[rfc_id] = [
            {"from": None, "to": "draft", "actor": author, "detail": "created", "timestamp": rfc.created_at}
        ]
        return rfc

    def submit_for_review(self, rfc_id: str) -> RFC:
        rfc = self._get_or_raise(rfc_id)
        return self._transition(rfc, RFCState.OPEN, rfc.author, "submitted for review")

    def assign_reviewers(self, rfc_id: str, reviewers: list[str]) -> None:
        rfc = self._get_or_raise(rfc_id)
        if rfc.state != RFCState.OPEN:
            raise ValueError("Can only assign reviewers when RFC is OPEN")
        rfc.reviewers = reviewers
        self._transition(rfc, RFCState.REVIEWING, detail="reviewers assigned")

    def approve(self, rfc_id: str, approver: str) -> RFC:
        rfc = self._get_or_raise(rfc_id)
        return self._transition(rfc, RFCState.APPROVED, approver, "approved")

    def reject(self, rfc_id: str, reason: str) -> RFC:
        rfc = self._get_or_raise(rfc_id)
        return self._transition(rfc, RFCState.REJECTED, detail=reason)

    def enforce(self, rfc_id: str) -> RFC:
        rfc = self._get_or_raise(rfc_id)
        return self._transition(rfc, RFCState.ENFORCED, detail="enforced")

    def withdraw(self, rfc_id: str) -> RFC:
        rfc = self._get_or_raise(rfc_id)
        if rfc.state == RFCState.ENFORCED:
            raise ValueError("Cannot withdraw an ENFORCED RFC")
        return self._transition(rfc, RFCState.WITHDRAWN, detail="withdrawn")

    def get_rfc(self, rfc_id: str) -> RFC | None:
        return self._rfcs.get(rfc_id)

    def list_rfcs(self, state: RFCState | None = None) -> list[RFC]:
        if state is None:
            return list(self._rfcs.values())
        return [r for r in self._rfcs.values() if r.state == state]

    def get_transition_history(self, rfc_id: str) -> list[dict]:
        return list(self._history.get(rfc_id, []))

    def _get_or_raise(self, rfc_id: str) -> RFC:
        rfc = self._rfcs.get(rfc_id)
        if rfc is None:
            raise KeyError(f"RFC not found: {rfc_id}")
        return rfc
