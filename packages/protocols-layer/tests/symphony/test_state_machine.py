"""Tests for symphony-protocol state machine — SymphonyStateMachine."""

from protocols_layer.symphony.models import SymphonyStage
from protocols_layer.symphony.state_machine import SymphonyStateMachine


class TestSymphonyStateMachineInit:
    """SymphonyStateMachine.__init__: initial state"""

    def test_initial_stage_is_none(self):
        sm = SymphonyStateMachine()
        assert sm.get_current_stage() is None

    def test_initial_context_empty(self):
        sm = SymphonyStateMachine()
        assert sm.get_context() == {}

    def test_initial_context_from_arg(self):
        sm = SymphonyStateMachine(initial_context={"task": "build"})
        assert sm.get_context() == {"task": "build"}

    def test_history_empty(self):
        sm = SymphonyStateMachine()
        assert sm.get_history() == []


class TestSymphonyStateMachineTransitions:
    """SymphonyStateMachine.transition: stage transition logic"""

    def test_transition_from_none_to_anchoring_success(self):
        """From None → ANCHORING with task defined"""
        sm = SymphonyStateMachine(initial_context={"task": "build feature"})
        result = sm.transition(SymphonyStage.ANCHORING)
        assert result.success is True
        assert sm.get_current_stage() == SymphonyStage.ANCHORING

    def test_transition_from_none_to_anchoring_fails_without_task(self):
        """From None → ANCHORING without task → fails"""
        sm = SymphonyStateMachine()
        result = sm.transition(SymphonyStage.ANCHORING)
        assert result.success is False
        assert "conditions not met" in result.message

    def test_anchoring_to_scaffolding_all_conditions_met(self):
        """ANCHORING → SCAFFOLDING with context_completeness, no ambiguities, truth_locked"""
        ctx = {"task": "x", "context_completeness": 0.95, "ambiguities": [], "truth_locked": True}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        result = sm.transition(SymphonyStage.SCAFFOLDING)
        assert result.success is True
        assert result.to_stage == SymphonyStage.SCAFFOLDING

    def test_anchoring_to_scaffolding_fails_low_context(self):
        """ANCHORING → SCAFFOLDING with low context → fails"""
        ctx = {"task": "x", "context_completeness": 0.5, "ambiguities": [], "truth_locked": True}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        result = sm.transition(SymphonyStage.SCAFFOLDING)
        assert result.success is False

    def test_anchoring_to_scaffolding_fails_unresolved_ambiguities(self):
        """ANCHORING → SCAFFOLDING with ambiguities → fails"""
        ctx = {"task": "x", "context_completeness": 0.95, "ambiguities": ["what?"], "truth_locked": True}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        result = sm.transition(SymphonyStage.SCAFFOLDING)
        assert result.success is False

    def test_scaffolding_to_implementation_all_conditions(self):
        """SCAFFOLDING → IMPLEMENTATION with architecture, contract, dependency_graph"""
        ctx = {"task": "x", "context_completeness": 0.95, "ambiguities": [], "truth_locked": True,
               "architecture": "layered", "contract_signed": True, "dependency_graph": {"a": ["b"]}}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        result = sm.transition(SymphonyStage.IMPLEMENTATION)
        assert result.success is True

    def test_implementation_to_polishing_all_conditions(self):
        """IMPLEMENTATION → POLISHING with code_complete, coverage, no issues"""
        ctx = {"task": "x", "context_completeness": 0.95, "ambiguities": [], "truth_locked": True,
               "architecture": "x", "contract_signed": True, "dependency_graph": {},
               "code_completion_rate": 0.95, "code_coverage": 0.80, "critical_issues": 0}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        sm.transition(SymphonyStage.IMPLEMENTATION)
        result = sm.transition(SymphonyStage.POLISHING)
        assert result.success is True

    def test_polishing_to_complete_all_conditions(self):
        """POLISHING → COMPLETE with tests_passed, performance, self_review"""
        ctx = {"task": "x", "context_completeness": 0.95, "ambiguities": [], "truth_locked": True,
               "architecture": "x", "contract_signed": True, "dependency_graph": {},
               "code_completion_rate": 0.95, "code_coverage": 0.80, "critical_issues": 0,
               "tests_passed": True, "performance_score": 0.90, "self_review_score": 0.85}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        sm.transition(SymphonyStage.IMPLEMENTATION)
        sm.transition(SymphonyStage.POLISHING)
        result = sm.transition(SymphonyStage.COMPLETE)
        assert result.success is True

    def test_polishing_to_complete_fails_low_performance(self):
        """POLISHING → COMPLETE with low performance → fails"""
        ctx = {"task": "x", "context_completeness": 0.95, "ambiguities": [], "truth_locked": True,
               "architecture": "x", "contract_signed": True, "dependency_graph": {},
               "code_completion_rate": 0.95, "code_coverage": 0.80, "critical_issues": 0,
               "tests_passed": True, "performance_score": 0.5, "self_review_score": 0.85}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        sm.transition(SymphonyStage.IMPLEMENTATION)
        sm.transition(SymphonyStage.POLISHING)
        result = sm.transition(SymphonyStage.COMPLETE)
        assert result.success is False

    def test_illegal_skip_transition(self):
        """ANCHORING → COMPLETE is illegal"""
        sm = SymphonyStateMachine(initial_context={"task": "x"})
        sm.transition(SymphonyStage.ANCHORING)
        result = sm.transition(SymphonyStage.COMPLETE)
        assert result.success is False
        assert "illegal transition" in result.message

    def test_conditions_met_and_failed_listed(self):
        """Failed transition lists which conditions passed/failed"""
        ctx = {"task": "x", "context_completeness": 0.5, "ambiguities": [], "truth_locked": True}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        result = sm.transition(SymphonyStage.SCAFFOLDING)
        assert len(result.conditions_failed) >= 1
        # context_completeness failed, ambiguity_resolved passed, truth_locked passed


class TestSymphonyStateMachineCanTransition:
    """SymphonyStateMachine.can_transition: predicate check"""

    def test_can_transition_from_none(self):
        sm = SymphonyStateMachine(initial_context={"task": "x"})
        assert sm.can_transition(SymphonyStage.ANCHORING) is True

    def test_cannot_transition_from_none_without_task(self):
        sm = SymphonyStateMachine()
        assert sm.can_transition(SymphonyStage.ANCHORING) is False

    def test_cannot_transition_illegal(self):
        sm = SymphonyStateMachine(initial_context={"task": "x"})
        sm.transition(SymphonyStage.ANCHORING)
        assert sm.can_transition(SymphonyStage.COMPLETE) is False


class TestSymphonyStateMachineInvariants:
    """SymphonyStateMachine.validate_invariants: stage invariants"""

    def test_no_violations_when_stage_none(self):
        sm = SymphonyStateMachine()
        assert sm.validate_invariants() == []

    def test_anchoring_invariants_no_violation(self):
        ctx = {"task": "x", "context_frozen": True, "truth_contradiction": False}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        assert sm.validate_invariants() == []

    def test_anchoring_invariant_violation(self):
        ctx = {"task": "x", "context_frozen": False, "truth_contradiction": False}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        assert "context_immutable" in sm.validate_invariants()

    def test_scaffolding_invariant(self):
        ctx = {"task": "x", "context_completeness": 0.95, "ambiguities": [], "truth_locked": True,
               "architecture_layers": 2}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        assert "architecture_layered" in sm.validate_invariants()

    def test_implementation_invariant_no_violation(self):
        ctx = {"task": "x", "context_completeness": 0.95, "ambiguities": [], "truth_locked": True,
               "architecture": "x", "contract_signed": True, "dependency_graph": {},
               "agent_conflict": False}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        sm.transition(SymphonyStage.IMPLEMENTATION)
        assert sm.validate_invariants() == []

    def test_polishing_invariant(self):
        ctx = {"task": "x", "context_completeness": 0.95, "ambiguities": [], "truth_locked": True,
               "architecture": "x", "contract_signed": True, "dependency_graph": {},
               "code_completion_rate": 0.95, "code_coverage": 0.80, "critical_issues": 0}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        sm.transition(SymphonyStage.IMPLEMENTATION)
        sm.transition(SymphonyStage.POLISHING)
        # Now we need to trigger the invariant violation by updating context after transition
        sm.update_context({"code_coverage": 0.5})
        assert "test_coverage_maintained" in sm.validate_invariants()


class TestSymphonyStateMachineHelpers:
    """SymphonyStateMachine utility methods"""

    def test_update_context_merges(self):
        sm = SymphonyStateMachine(initial_context={"a": 1})
        sm.update_context({"b": 2})
        assert sm.get_context() == {"a": 1, "b": 2}

    def test_get_context_returns_copy(self):
        sm = SymphonyStateMachine(initial_context={"a": 1})
        ctx = sm.get_context()
        ctx["a"] = 999
        assert sm.get_context()["a"] == 1

    def test_get_valid_transitions_from_none(self):
        sm = SymphonyStateMachine()
        assert sm.get_valid_transitions() == [SymphonyStage.ANCHORING]

    def test_get_valid_transitions_from_anchoring(self):
        sm = SymphonyStateMachine(initial_context={"task": "x"})
        sm.transition(SymphonyStage.ANCHORING)
        valid = sm.get_valid_transitions()
        assert SymphonyStage.SCAFFOLDING in valid
        assert SymphonyStage.COMPLETE not in valid

    def test_is_complete_false_initially(self):
        sm = SymphonyStateMachine()
        assert sm.is_complete() is False

    def test_is_complete_true_after_full_cycle(self):
        ctx = {
            "task": "x",
            "context_completeness": 0.95,
            "ambiguities": [],
            "truth_locked": True,
            "architecture": "x",
            "contract_signed": True,
            "dependency_graph": {},
            "code_completion_rate": 0.95,
            "code_coverage": 0.80,
            "critical_issues": 0,
            "tests_passed": True,
            "performance_score": 0.90,
            "self_review_score": 0.85,
        }
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        sm.transition(SymphonyStage.IMPLEMENTATION)
        sm.transition(SymphonyStage.POLISHING)
        sm.transition(SymphonyStage.COMPLETE)
        assert sm.is_complete() is True

    def test_get_stage_history_after_transitions(self):
        ctx = {"task": "x", "context_completeness": 0.95, "ambiguities": [], "truth_locked": True}
        sm = SymphonyStateMachine(initial_context=ctx)
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        history = sm.get_stage_history()
        assert len(history) == 1  # only exited stages are in stage_history
        assert history[0].stage == SymphonyStage.ANCHORING

    def test_set_stage_output(self):
        from protocols_layer.symphony.models import StageOutput

        sm = SymphonyStateMachine(initial_context={"task": "x"})
        sm.transition(SymphonyStage.ANCHORING)
        output = StageOutput(stage=SymphonyStage.ANCHORING, artifacts=["doc.md"])
        sm.set_stage_output(output)
        # Verify it was set (no crash)
        assert sm.get_current_stage() == SymphonyStage.ANCHORING

    def test_reset_clears_state(self):
        sm = SymphonyStateMachine(initial_context={"task": "x"})
        sm.transition(SymphonyStage.ANCHORING)
        sm.reset()
        assert sm.get_current_stage() is None
        assert sm.get_context() == {}
        assert sm.get_history() == []

    def test_reset_with_new_context(self):
        sm = SymphonyStateMachine(initial_context={"task": "x"})
        sm.reset(initial_context={"new": "ctx"})
        assert sm.get_context() == {"new": "ctx"}
