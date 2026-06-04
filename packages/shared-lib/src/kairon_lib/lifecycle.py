from __future__ import annotations

"""RFC Lifecycle types — state machine for governance RFCs.

Extracted from SharedBrain D_Governance (organs/lifecycle/rfc_lifecycle_manager.py).
CoreService-dependent orchestration code (RFCLifecycleManager) skipped.

Provides:
- RFCState enum: the 7 RFC lifecycle states
- VALID_TRANSITIONS: the legal state transition map
- RFC dataclass: the data model for a governance RFC
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class RFCState(Enum):
    """The seven canonical RFC lifecycle states."""

    DRAFT = "draft"
    OPEN = "open"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    ENFORCED = "enforced"
    WITHDRAWN = "withdrawn"


# Legal state transitions: RFCState -> list of valid next states
VALID_TRANSITIONS: dict[RFCState, list[RFCState]] = {
    RFCState.DRAFT: [RFCState.OPEN, RFCState.WITHDRAWN],
    RFCState.OPEN: [RFCState.REVIEWING, RFCState.WITHDRAWN],
    RFCState.REVIEWING: [RFCState.APPROVED, RFCState.REJECTED, RFCState.WITHDRAWN],
    RFCState.APPROVED: [RFCState.ENFORCED, RFCState.WITHDRAWN],
    RFCState.REJECTED: [RFCState.WITHDRAWN],
    RFCState.ENFORCED: [],
    RFCState.WITHDRAWN: [],
}

# Terminal states (no outgoing transitions)
TERMINAL_STATES: frozenset[RFCState] = frozenset(
    {s for s, transitions in VALID_TRANSITIONS.items() if len(transitions) == 0}
)

# Entrance states (states that can be the first state of an RFC)
ENTRANCE_STATES: frozenset[RFCState] = frozenset({RFCState.DRAFT})


def is_valid_transition(from_state: RFCState, to_state: RFCState) -> bool:
    """Return True if transitioning from_state -> to_state is legal."""
    return to_state in VALID_TRANSITIONS.get(from_state, [])


def is_terminal(state: RFCState) -> bool:
    """Return True if *state* is a terminal state (no further transitions)."""
    return state in TERMINAL_STATES


@dataclass
class RFC:
    """A governance RFC (Request for Comments) data model.

    Tracks the full lifecycle of a governance proposal from draft through
    review, approval/rejection, enforcement, or withdrawal.
    """

    rfc_id: str
    title: str
    author: str
    state: RFCState = RFCState.DRAFT
    created_at: float = 0.0
    body: str = ""
    reviewers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, title: str, author: str, body: str = "") -> RFC:  # noqa: F821
        """Factory: create a new RFC in DRAFT state with a generated ID."""
        return cls(
            rfc_id=f"RFC-{uuid.uuid4().hex[:8]}",
            title=title,
            author=author,
            body=body,
            created_at=time.time(),
        )

    def can_transition_to(self, target: RFCState) -> bool:
        """Check whether a transition to *target* is legal from current state."""
        return is_valid_transition(self.state, target)

    def is_terminal(self) -> bool:
        """Return True if this RFC is in a terminal state."""
        return is_terminal(self.state)


__all__ = [
    "ENTRANCE_STATES",
    "RFC",
    "RFCState",
    "TERMINAL_STATES",
    "VALID_TRANSITIONS",
    "is_terminal",
    "is_valid_transition",
]
