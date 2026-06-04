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
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Consolidation State Machine ≡ Module
# 内涵 ≝ {Consolidation, State, Machine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ConsolidationStateMachine)}
# 功能 ⊢ {Consolidation_State, State_Machine, Machine_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConsolidationState(Enum):
    GATHERING = "gathering"
    ANALYZING = "analyzing"
    PROPOSING = "proposing"
    VOTING = "voting"
    DECIDED = "decided"
    ARCHIVED = "archived"


_STATE_ORDER = [
    ConsolidationState.GATHERING,
    ConsolidationState.ANALYZING,
    ConsolidationState.PROPOSING,
    ConsolidationState.VOTING,
    ConsolidationState.DECIDED,
    ConsolidationState.ARCHIVED,
]

_ADVANCE_CONDITIONS: dict[ConsolidationState, str] = {
    ConsolidationState.GATHERING: "Must have at least one input",
    ConsolidationState.ANALYZING: "Automatic advance",
    ConsolidationState.PROPOSING: "Must have a proposal set",
    ConsolidationState.VOTING: "Must have a decision set",
    ConsolidationState.DECIDED: "Use archive() to move to ARCHIVED",
}


@dataclass
class ConsolidationItem:
    item_id: str
    title: str
    state: ConsolidationState = ConsolidationState.GATHERING
    inputs: list[dict[str, Any]] = field(default_factory=list)
    proposal: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None


class ConsolidationStateMachine:
    metadata_path = "organs/D-Governance/organs/consolidation_state_machine.py"

    def __init__(self) -> None:
        self._items: dict[str, ConsolidationItem] = {}

    def create_item(self, title: str) -> ConsolidationItem:
        item_id = f"CONS-{uuid.uuid4().hex[:8]}"
        item = ConsolidationItem(item_id=item_id, title=title)
        self._items[item_id] = item
        return item

    def add_input(self, item_id: str, input_data: dict[str, Any]) -> None:
        item = self._get_or_raise(item_id)
        if item.state != ConsolidationState.GATHERING:
            raise ValueError("Can only add inputs during GATHERING state")
        item.inputs.append(input_data)

    def advance(self, item_id: str) -> ConsolidationState:
        item = self._get_or_raise(item_id)
        idx = _STATE_ORDER.index(item.state)
        if item.state == ConsolidationState.ARCHIVED:
            raise ValueError("Cannot advance past ARCHIVED")
        if item.state == ConsolidationState.DECIDED:
            raise ValueError("Use archive() to move from DECIDED to ARCHIVED")
        if item.state == ConsolidationState.GATHERING and len(item.inputs) == 0:
            raise ValueError("Cannot advance: must have at least one input")
        if item.state == ConsolidationState.PROPOSING and item.proposal is None:
            raise ValueError("Cannot advance: must set a proposal first")
        if item.state == ConsolidationState.VOTING and item.decision is None:
            raise ValueError("Cannot advance: must set a decision first")
        item.state = _STATE_ORDER[idx + 1]
        return item.state

    def set_proposal(self, item_id: str, proposal: dict[str, Any]) -> None:
        item = self._get_or_raise(item_id)
        if item.state != ConsolidationState.PROPOSING:
            raise ValueError("Can only set proposal during PROPOSING state")
        item.proposal = proposal

    def set_decision(self, item_id: str, decision: dict[str, Any]) -> None:
        item = self._get_or_raise(item_id)
        if item.state != ConsolidationState.VOTING:
            raise ValueError("Can only set decision during VOTING state")
        item.decision = decision

    def get_item(self, item_id: str) -> ConsolidationItem | None:
        return self._items.get(item_id)

    def get_state(self, item_id: str) -> ConsolidationState:
        return self._get_or_raise(item_id).state

    def archive(self, item_id: str) -> None:
        item = self._get_or_raise(item_id)
        if item.state != ConsolidationState.DECIDED:
            raise ValueError("Can only archive items in DECIDED state")
        item.state = ConsolidationState.ARCHIVED

    def list_items(self, state: ConsolidationState | None = None) -> list[ConsolidationItem]:
        if state is None:
            return list(self._items.values())
        return [i for i in self._items.values() if i.state == state]

    def _get_or_raise(self, item_id: str) -> ConsolidationItem:
        item = self._items.get(item_id)
        if item is None:
            raise KeyError(f"Item not found: {item_id}")
        return item
