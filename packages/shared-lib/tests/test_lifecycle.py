"""Tests for kairon_lib.lifecycle — RFC lifecycle state machine types."""

from kairon_lib.lifecycle import (
    ENTRANCE_STATES,
    RFC,
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    RFCState,
    is_terminal,
    is_valid_transition,
)


class TestRFCState:
    """Tests for RFCState enum."""

    def test_all_seven_states(self):
        assert len(RFCState) == 7

    def test_state_values(self):
        assert RFCState.DRAFT.value == "draft"
        assert RFCState.OPEN.value == "open"
        assert RFCState.REVIEWING.value == "reviewing"
        assert RFCState.APPROVED.value == "approved"
        assert RFCState.REJECTED.value == "rejected"
        assert RFCState.ENFORCED.value == "enforced"
        assert RFCState.WITHDRAWN.value == "withdrawn"


class TestValidTransitions:
    """Tests for VALID_TRANSITIONS map."""

    def test_all_states_have_entries(self):
        for state in RFCState:
            assert state in VALID_TRANSITIONS

    def test_draft_transitions(self):
        assert RFCState.OPEN in VALID_TRANSITIONS[RFCState.DRAFT]
        assert RFCState.WITHDRAWN in VALID_TRANSITIONS[RFCState.DRAFT]
        assert RFCState.ENFORCED not in VALID_TRANSITIONS[RFCState.DRAFT]

    def test_open_transitions(self):
        assert RFCState.REVIEWING in VALID_TRANSITIONS[RFCState.OPEN]
        assert RFCState.WITHDRAWN in VALID_TRANSITIONS[RFCState.OPEN]

    def test_reviewing_transitions(self):
        assert RFCState.APPROVED in VALID_TRANSITIONS[RFCState.REVIEWING]
        assert RFCState.REJECTED in VALID_TRANSITIONS[RFCState.REVIEWING]
        assert RFCState.WITHDRAWN in VALID_TRANSITIONS[RFCState.REVIEWING]

    def test_approved_transitions(self):
        assert RFCState.ENFORCED in VALID_TRANSITIONS[RFCState.APPROVED]
        assert RFCState.WITHDRAWN in VALID_TRANSITIONS[RFCState.APPROVED]

    def test_rejected_transitions(self):
        assert RFCState.WITHDRAWN in VALID_TRANSITIONS[RFCState.REJECTED]
        assert len(VALID_TRANSITIONS[RFCState.REJECTED]) == 1

    def test_enforced_is_terminal(self):
        assert VALID_TRANSITIONS[RFCState.ENFORCED] == []

    def test_withdrawn_is_terminal(self):
        assert VALID_TRANSITIONS[RFCState.WITHDRAWN] == []

    def test_no_invalid_shortcuts(self):
        """Verify there are no jumps that skip the review pipeline."""
        assert RFCState.APPROVED not in VALID_TRANSITIONS[RFCState.DRAFT]
        assert RFCState.ENFORCED not in VALID_TRANSITIONS[RFCState.DRAFT]
        assert RFCState.ENFORCED not in VALID_TRANSITIONS[RFCState.OPEN]
        assert RFCState.ENFORCED not in VALID_TRANSITIONS[RFCState.REVIEWING]


class TestIsValidTransition:
    """Tests for is_valid_transition helper."""

    def test_valid_transitions(self):
        assert is_valid_transition(RFCState.DRAFT, RFCState.OPEN) is True
        assert is_valid_transition(RFCState.OPEN, RFCState.REVIEWING) is True
        assert is_valid_transition(RFCState.REVIEWING, RFCState.APPROVED) is True
        assert is_valid_transition(RFCState.APPROVED, RFCState.ENFORCED) is True

    def test_invalid_transitions(self):
        assert is_valid_transition(RFCState.DRAFT, RFCState.ENFORCED) is False
        assert is_valid_transition(RFCState.ENFORCED, RFCState.DRAFT) is False
        assert is_valid_transition(RFCState.WITHDRAWN, RFCState.OPEN) is False

    def test_self_transition_is_invalid(self):
        assert is_valid_transition(RFCState.DRAFT, RFCState.DRAFT) is False


class TestTerminalAndEntrance:
    """Tests for TERMINAL_STATES and ENTRANCE_STATES."""

    def test_terminal_states(self):
        assert TERMINAL_STATES == frozenset({RFCState.ENFORCED, RFCState.WITHDRAWN})

    def test_entrance_states(self):
        assert ENTRANCE_STATES == frozenset({RFCState.DRAFT})

    def test_is_terminal(self):
        assert is_terminal(RFCState.ENFORCED) is True
        assert is_terminal(RFCState.WITHDRAWN) is True
        assert is_terminal(RFCState.DRAFT) is False
        assert is_terminal(RFCState.APPROVED) is False


class TestRFC:
    """Tests for RFC dataclass."""

    def test_create_factory(self):
        rfc = RFC.create("My RFC", "alice", "This is the body")
        assert rfc.title == "My RFC"
        assert rfc.author == "alice"
        assert rfc.body == "This is the body"
        assert rfc.state == RFCState.DRAFT
        assert rfc.rfc_id.startswith("RFC-")
        assert len(rfc.rfc_id) == 12  # "RFC-" + 8 hex chars
        assert rfc.created_at > 0

    def test_create_generates_unique_ids(self):
        rfc1 = RFC.create("A", "alice")
        rfc2 = RFC.create("B", "bob")
        assert rfc1.rfc_id != rfc2.rfc_id

    def test_default_values(self):
        rfc = RFC(rfc_id="RFC-1", title="T", author="alice")
        assert rfc.state == RFCState.DRAFT
        assert rfc.created_at == 0.0
        assert rfc.body == ""
        assert rfc.reviewers == []
        assert rfc.tags == []

    def test_can_transition_to(self):
        rfc = RFC(rfc_id="RFC-1", title="T", author="alice")
        assert rfc.can_transition_to(RFCState.OPEN) is True
        assert rfc.can_transition_to(RFCState.WITHDRAWN) is True
        assert rfc.can_transition_to(RFCState.ENFORCED) is False

    def test_state_changes_affect_can_transition(self):
        rfc = RFC.create("T", "alice")
        assert rfc.can_transition_to(RFCState.OPEN) is True
        rfc.state = RFCState.OPEN
        assert rfc.can_transition_to(RFCState.REVIEWING) is True
        assert rfc.can_transition_to(RFCState.DRAFT) is False

    def test_is_terminal(self):
        rfc = RFC(rfc_id="RFC-1", title="T", author="alice")
        assert rfc.is_terminal() is False
        rfc.state = RFCState.ENFORCED
        assert rfc.is_terminal() is True

    def test_withdrawn_is_terminal(self):
        rfc = RFC(rfc_id="RFC-1", title="T", author="alice", state=RFCState.WITHDRAWN)
        assert rfc.is_terminal() is True

    def test_reviewers_and_tags(self):
        rfc = RFC(
            rfc_id="RFC-1",
            title="T",
            author="alice",
            reviewers=["bob", "carol"],
            tags=["security", "governance"],
        )
        assert rfc.reviewers == ["bob", "carol"]
        assert rfc.tags == ["security", "governance"]


class TestFullLifecycle:
    """Integration-style test of a full RFC lifecycle path."""

    def test_happy_path(self):
        """DRAFT -> OPEN -> REVIEWING -> APPROVED -> ENFORCED."""
        rfc = RFC.create("Security Policy v2", "alice")

        # Draft -> Open
        assert is_valid_transition(rfc.state, RFCState.OPEN)
        rfc.state = RFCState.OPEN

        # Open -> Reviewing
        assert is_valid_transition(rfc.state, RFCState.REVIEWING)
        rfc.state = RFCState.REVIEWING

        # Reviewing -> Approved
        assert is_valid_transition(rfc.state, RFCState.APPROVED)
        rfc.state = RFCState.APPROVED

        # Approved -> Enforced
        assert is_valid_transition(rfc.state, RFCState.ENFORCED)
        rfc.state = RFCState.ENFORCED

        assert rfc.is_terminal() is True

    def test_withdrawal_path(self):
        """DRAFT -> WITHDRAWN (withdraw before opening)."""
        rfc = RFC.create("Bad Idea", "bob")
        assert is_valid_transition(rfc.state, RFCState.WITHDRAWN)
        rfc.state = RFCState.WITHDRAWN
        assert rfc.is_terminal() is True

    def test_rejection_path(self):
        """DRAFT -> OPEN -> REVIEWING -> REJECTED -> WITHDRAWN."""
        rfc = RFC.create("Rejected Proposal", "carol")
        rfc.state = RFCState.OPEN
        rfc.state = RFCState.REVIEWING
        rfc.state = RFCState.REJECTED
        rfc.state = RFCState.WITHDRAWN
        assert rfc.is_terminal() is True

    def test_enforced_cannot_be_withdrawn(self):
        """Enforced is terminal — no withdrawal possible."""
        assert not is_valid_transition(RFCState.ENFORCED, RFCState.WITHDRAWN)
