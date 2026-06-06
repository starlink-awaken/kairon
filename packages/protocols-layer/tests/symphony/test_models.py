"""Tests for symphony-protocol data models."""

from protocols_layer.symphony.models import (
    AgentCapability,
    AgentProfile,
    MatchResult,
    StageHistoryEntry,
    StageInvariant,
    StageOutput,
    StageTransition,
    SymphonyStage,
    TaskRequirement,
    TransitionCondition,
    TransitionResult,
    Trigger,
    TriggerResult,
    TriggerType,
)


class TestSymphonyStage:
    def test_enum_values(self):
        assert SymphonyStage.ANCHORING.value == "anchoring"
        assert SymphonyStage.SCAFFOLDING.value == "scaffolding"
        assert SymphonyStage.IMPLEMENTATION.value == "implementation"
        assert SymphonyStage.POLISHING.value == "polishing"
        assert SymphonyStage.COMPLETE.value == "complete"

    def test_str_enum(self):
        assert str(SymphonyStage.ANCHORING) == "anchoring"


class TestTriggerType:
    def test_enum_values(self):
        assert TriggerType.CONDITION_MET.value == "condition_met"
        assert TriggerType.TIMER.value == "timer"
        assert TriggerType.MANUAL.value == "manual"
        assert TriggerType.STAGE_ENTER.value == "stage_enter"
        assert TriggerType.STAGE_EXIT.value == "stage_exit"


class TestTransitionCondition:
    def test_defaults(self):
        tc = TransitionCondition(name="test", predicate=lambda ctx: True)
        assert tc.name == "test"
        assert tc.threshold == 1.0
        assert tc.description == ""

    def test_custom_values(self):
        tc = TransitionCondition(name="check", predicate=lambda ctx: False, threshold=0.8, description="check desc")
        assert tc.threshold == 0.8
        assert tc.description == "check desc"
        assert tc.predicate({}) is False


class TestTransitionResult:
    def test_success_result(self):
        tr = TransitionResult(
            success=True,
            from_stage=SymphonyStage.ANCHORING,
            to_stage=SymphonyStage.SCAFFOLDING,
            conditions_met=["context_completeness"],
            message="ok",
        )
        assert tr.success is True
        assert tr.from_stage == SymphonyStage.ANCHORING
        assert tr.to_stage == SymphonyStage.SCAFFOLDING

    def test_default_lists(self):
        tr = TransitionResult(success=False, from_stage=None, to_stage=SymphonyStage.ANCHORING)
        assert tr.conditions_met == []
        assert tr.conditions_failed == []


class TestStageTransition:
    def test_valid_direct_transition(self):
        t = StageTransition(from_stage=SymphonyStage.ANCHORING, to_stage=SymphonyStage.SCAFFOLDING)
        assert t.is_valid() is True

    def test_valid_all_transitions(self):
        valid_pairs = [
            (SymphonyStage.ANCHORING, SymphonyStage.SCAFFOLDING),
            (SymphonyStage.SCAFFOLDING, SymphonyStage.IMPLEMENTATION),
            (SymphonyStage.IMPLEMENTATION, SymphonyStage.POLISHING),
            (SymphonyStage.POLISHING, SymphonyStage.COMPLETE),
        ]
        for from_stage, to_stage in valid_pairs:
            assert StageTransition(from_stage=from_stage, to_stage=to_stage).is_valid()

    def test_invalid_skip_transition(self):
        t = StageTransition(from_stage=SymphonyStage.ANCHORING, to_stage=SymphonyStage.COMPLETE)
        assert t.is_valid() is False

    def test_invalid_reverse_transition(self):
        t = StageTransition(from_stage=SymphonyStage.COMPLETE, to_stage=SymphonyStage.POLISHING)
        assert t.is_valid() is False

    def test_complete_has_no_valid_transitions(self):
        t = StageTransition(from_stage=SymphonyStage.COMPLETE, to_stage=SymphonyStage.ANCHORING)
        assert t.is_valid() is False


class TestStageHistoryEntry:
    def test_defaults(self):
        entry = StageHistoryEntry(stage=SymphonyStage.ANCHORING)
        assert entry.stage == SymphonyStage.ANCHORING
        assert entry.exited_at is None
        assert entry.output is None

    def test_with_output(self):
        output = StageOutput(stage=SymphonyStage.COMPLETE)
        entry = StageHistoryEntry(stage=SymphonyStage.ANCHORING, output=output)
        assert entry.output is not None
        assert entry.output.stage == SymphonyStage.COMPLETE


class TestStageInvariant:
    def test_defaults(self):
        inv = StageInvariant(name="test_invariant")
        assert inv.name == "test_invariant"
        assert inv.violation_action == "WARN"
        assert inv.severity == "error"
        assert inv.condition == ""

    def test_predicate_defaults_to_true(self):
        inv = StageInvariant(name="test")
        assert inv.predicate({}) is True


class TestStageOutput:
    def test_defaults(self):
        o = StageOutput(stage=SymphonyStage.COMPLETE)
        assert o.artifacts == []
        assert o.metrics == {}

    def test_custom_values(self):
        o = StageOutput(stage=SymphonyStage.IMPLEMENTATION, artifacts=["file1.py"], metrics={"score": 0.9})
        assert o.artifacts == ["file1.py"]
        assert o.metrics["score"] == 0.9


class TestAgentCapability:
    def test_defaults(self):
        c = AgentCapability(name="code_review")
        assert c.name == "code_review"
        assert c.proficiency == 0.8
        assert c.tags == ()

    def test_custom_proficiency(self):
        c = AgentCapability(name="testing", proficiency=0.95, tags=("python", "pytest"))
        assert c.proficiency == 0.95
        assert "python" in c.tags


class TestAgentProfile:
    def test_defaults(self):
        p = AgentProfile(agent_id="a1")
        assert p.current_load == 0.0
        assert p.max_capacity == 10
        assert p.specialization is None

    def test_with_capabilities(self):
        caps = {AgentCapability(name="code"): 0.9}
        p = AgentProfile(agent_id="a1", capabilities=caps)
        assert len(p.capabilities) == 1

    def test_historical_performance(self):
        p = AgentProfile(agent_id="a1", historical_performance={"task1": 0.8, "task2": 0.9})
        assert p.historical_performance["task1"] == 0.8


class TestTaskRequirement:
    def test_defaults(self):
        tr = TaskRequirement(task_id="t1")
        assert tr.complexity == 5
        assert tr.priority == 5
        assert tr.required_capabilities == set()

    def test_custom_values(self):
        caps = {AgentCapability(name="code")}
        tr = TaskRequirement(task_id="t1", required_capabilities=caps, complexity=8, priority=1)
        assert tr.complexity == 8
        assert tr.priority == 1


class TestMatchResult:
    def test_defaults(self):
        r = MatchResult(task_id="t1", agent_id="a1", score=0.95)
        assert r.score_breakdown == {}
        assert r.reasoning == ""

    def test_with_breakdown(self):
        r = MatchResult(task_id="t1", agent_id="a1", score=0.85, score_breakdown={"capability": 0.9})
        assert r.score_breakdown["capability"] == 0.9


class TestTriggerModels:
    def test_trigger_defaults(self):
        t = Trigger(id="tr1", name="test")
        assert t.trigger_type == TriggerType.CONDITION_MET
        assert t.priority == 50
        assert t.enabled is True

    def test_trigger_custom(self):
        t = Trigger(id="tr2", name="timer", trigger_type=TriggerType.TIMER, priority=100, enabled=False)
        assert t.trigger_type == TriggerType.TIMER
        assert t.enabled is False

    def test_trigger_result(self):
        tr = TriggerResult(trigger_id="tr1", triggered=True, action_result="done", message="triggered")
        assert tr.triggered is True
        assert tr.action_result == "done"
