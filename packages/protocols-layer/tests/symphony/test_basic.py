"""Basic tests for symphony-protocol package."""

from __future__ import annotations

from symphony_protocol import (
    AgentCapability,
    AgentMatcher,
    AgentProfile,
    MatchResult,
    StageHistoryEntry,
    StageInvariant,
    StageOutput,
    StageTransition,
    SymphonyStage,
    SymphonyStateMachine,
    TaskRequirement,
    TransitionCondition,
    TransitionResult,
    Trigger,
    TriggerEngine,
    TriggerResult,
    TriggerType,
    create_default_triggers,
    setup_trigger_engine,
)


class TestSymphonyBasic:
    """Core functionality and edge case tests."""

    def test_import(self):
        """All expected exports are importable."""
        assert AgentCapability is not None
        assert AgentMatcher is not None
        assert AgentProfile is not None
        assert MatchResult is not None
        assert StageHistoryEntry is not None
        assert StageInvariant is not None
        assert StageOutput is not None
        assert StageTransition is not None
        assert SymphonyStage is not None
        assert SymphonyStateMachine is not None
        assert TaskRequirement is not None
        assert TransitionCondition is not None
        assert TransitionResult is not None
        assert Trigger is not None
        assert TriggerEngine is not None
        assert TriggerResult is not None
        assert TriggerType is not None
        assert create_default_triggers is not None
        assert setup_trigger_engine is not None

    def test_symphony_stage_complete_no_transitions(self):
        """COMPLETE stage has no valid outgoing transitions."""
        from symphony_protocol.models import StageTransition

        assert StageTransition(
            from_stage=SymphonyStage.COMPLETE, to_stage=SymphonyStage.ANCHORING
        ).is_valid() is False
        assert StageTransition(
            from_stage=SymphonyStage.COMPLETE, to_stage=SymphonyStage.POLISHING
        ).is_valid() is False

    def test_stage_transition_same_stage_invalid(self):
        """Same from/to stage is invalid."""
        from symphony_protocol.models import StageTransition

        stages = list(SymphonyStage)
        for s in stages:
            assert StageTransition(from_stage=s, to_stage=s).is_valid() is False

    def test_state_machine_reset_preserves_independence(self):
        """Reset creates independent state."""
        sm1 = SymphonyStateMachine(initial_context={"task": "a"})
        sm2 = SymphonyStateMachine(initial_context={"task": "b"})
        sm1.reset()
        assert sm1.get_context() == {}
        assert sm2.get_context() == {"task": "b"}

    def test_trigger_engine_empty_evaluate(self):
        """TriggerEngine with no triggers returns empty results."""
        engine = TriggerEngine()
        assert engine.evaluate_and_trigger({}) == []
        assert engine.get_history() == []
