"""Tests for state_machine — PhaseStateMachine, transitions, DF-CEA risk assessment."""

import pytest
from agent_runtime.state_machine import (
    DecisionPath,
    Phase,
    PhaseHooks,
    PhaseRecord,
    PhaseStateMachine,
    RiskLevel,
    create_state_machine,
)

# ══════════════════════════════════════════════════════════════════════
# Phase Enum
# ══════════════════════════════════════════════════════════════════════


class TestPhaseEnum:
    def test_values(self):
        assert Phase.INIT == "INIT"
        assert Phase.PLAN == "PLAN"
        assert Phase.EXECUTE == "EXECUTE"
        assert Phase.VALIDATE == "VALIDATE"
        assert Phase.COMPLETE == "COMPLETE"
        assert Phase.PAUSED == "PAUSED"
        assert Phase.FAILED == "FAILED"

    def test_linear_order(self):
        from agent_runtime.state_machine import LINEAR_PHASE_ORDER
        assert LINEAR_PHASE_ORDER == [
            Phase.INIT, Phase.PLAN, Phase.EXECUTE,
            Phase.VALIDATE, Phase.COMPLETE,
        ]

    def test_decision_path_values(self):
        assert DecisionPath.EXPRESS == "express"
        assert DecisionPath.STANDARD == "standard"
        assert DecisionPath.FULL == "full"

    def test_risk_level_values(self):
        assert RiskLevel.VERY_LOW == "very_low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.CRITICAL == "critical"


# ══════════════════════════════════════════════════════════════════════
# PhaseRecord
# ══════════════════════════════════════════════════════════════════════


class TestPhaseRecord:
    def test_default_construction(self):
        r = PhaseRecord(from_phase=Phase.INIT, to_phase=Phase.PLAN)
        assert r.from_phase == Phase.INIT
        assert r.to_phase == Phase.PLAN
        assert r.decision_path == DecisionPath.STANDARD
        assert r.reason == ""

    def test_to_dict(self):
        r = PhaseRecord(
            from_phase=Phase.PLAN,
            to_phase=Phase.EXECUTE,
            reason="Proceed",
            decision_path=DecisionPath.DEEP,
        )
        d = r.to_dict()
        assert d["from"] == "PLAN"
        assert d["to"] == "EXECUTE"
        assert d["reason"] == "Proceed"
        assert d["decision_path"] == "deep"
        assert "timestamp" in d

    def test_to_dict_with_metadata(self):
        r = PhaseRecord(
            from_phase=Phase.INIT,
            to_phase=Phase.FAILED,
            metadata={"cause": "config error"},
        )
        d = r.to_dict()
        assert d["metadata"]["cause"] == "config error"


# ══════════════════════════════════════════════════════════════════════
# PhaseStateMachine — Transitions
# ══════════════════════════════════════════════════════════════════════


class TestPhaseStateMachineInitial:
    """Initial state and properties."""

    def test_default_initial_phase(self):
        sm = PhaseStateMachine()
        assert sm.current_phase == Phase.INIT
        assert sm.decision_path == DecisionPath.STANDARD
        assert sm.risk_level == RiskLevel.MEDIUM
        assert sm.history == []

    def test_custom_initial(self):
        sm = PhaseStateMachine(initial_phase=Phase.EXECUTE, decision_path=DecisionPath.EXPRESS)
        assert sm.current_phase == Phase.EXECUTE
        assert sm.decision_path == DecisionPath.EXPRESS


class TestPhaseStateMachineTransitions:
    """Legal and illegal transitions."""

    def test_valid_transition(self):
        sm = PhaseStateMachine()
        record = sm.transition_to(Phase.PLAN, "Start planning")
        assert sm.current_phase == Phase.PLAN
        assert record.from_phase == Phase.INIT
        assert record.to_phase == Phase.PLAN
        assert record.reason == "Start planning"

    def test_invalid_transition_raises(self):
        sm = PhaseStateMachine()
        with pytest.raises(ValueError, match="Invalid phase transition"):
            sm.transition_to(Phase.COMPLETE)

    def test_self_transition_rejected(self):
        sm = PhaseStateMachine(initial_phase=Phase.PLAN)
        assert not sm.can_transition_to(Phase.PLAN)

    def test_can_transition_to(self):
        sm = PhaseStateMachine()
        assert sm.can_transition_to(Phase.PLAN)
        assert sm.can_transition_to(Phase.EXECUTE)
        assert sm.can_transition_to(Phase.PAUSED)
        assert sm.can_transition_to(Phase.FAILED)
        assert not sm.can_transition_to(Phase.COMPLETE)
        assert not sm.can_transition_to(Phase.VALIDATE)

    def test_available_transitions(self):
        sm = PhaseStateMachine()
        available = sm.available_transitions
        assert Phase.PLAN in available
        assert Phase.EXECUTE in available
        assert Phase.PAUSED in available
        assert Phase.FAILED in available


class TestPhaseStateMachinePauseResume:
    """PAUSE/RESUME lifecycle."""

    def test_pause_from_init(self):
        sm = PhaseStateMachine()
        record = sm.pause("Need input")
        assert sm.current_phase == Phase.PAUSED
        assert sm.phase_before_pause == Phase.INIT
        assert record.reason == "Need input"

    def test_resume_from_pause(self):
        sm = PhaseStateMachine()
        sm.pause()
        record = sm.resume(reason="Got input")
        assert sm.current_phase == Phase.INIT
        assert record.reason == "Got input"

    def test_resume_without_pause_raises(self):
        sm = PhaseStateMachine()
        with pytest.raises(ValueError, match="Cannot resume"):
            sm.resume()

    def test_resume_after_complex_path(self):
        sm = PhaseStateMachine()
        sm.transition_to(Phase.PLAN)
        sm.transition_to(Phase.EXECUTE)
        sm.pause("Review needed")
        sm.resume()
        assert sm.current_phase == Phase.EXECUTE

    def test_resume_to_specific_target(self):
        sm = PhaseStateMachine()
        sm.pause()
        sm.resume(target=Phase.PLAN, reason="Skip ahead")
        assert sm.current_phase == Phase.PLAN


class TestPhaseStateMachineFail:
    """FAILED transitions."""

    def test_fail_from_any_active_phase(self):
        sm = PhaseStateMachine()
        record = sm.fail("Something broke", {"trace": "..."})
        assert sm.current_phase == Phase.FAILED
        assert record.reason == "Something broke"
        assert record.metadata == {"trace": "..."}

    def test_fail_and_restart(self):
        sm = PhaseStateMachine()
        sm.fail("First attempt failed")
        assert sm.current_phase == Phase.FAILED

        # Can restart from FAILED -> INIT
        sm.transition_to(Phase.INIT, "Retrying")
        assert sm.current_phase == Phase.INIT


class TestPhaseStateMachineHistory:
    """Transition history tracking."""

    def test_history_records_transitions(self):
        sm = PhaseStateMachine()
        sm.transition_to(Phase.PLAN)
        sm.transition_to(Phase.EXECUTE)
        sm.transition_to(Phase.PAUSED)
        assert len(sm.history) == 3
        assert sm.history[0].from_phase == Phase.INIT
        assert sm.history[0].to_phase == Phase.PLAN

    def test_history_immutable_copy(self):
        sm = PhaseStateMachine()
        sm.transition_to(Phase.PLAN)
        h = sm.history
        h.clear()
        assert len(sm.history) == 1


class TestPhaseStateMachineAdvance:
    """advance() auto-steps through effective sequence."""

    def test_advance_standard_path(self):
        sm = PhaseStateMachine(decision_path=DecisionPath.STANDARD)
        sm.advance()
        assert sm.current_phase == Phase.PLAN
        sm.advance()
        assert sm.current_phase == Phase.EXECUTE
        sm.advance()
        assert sm.current_phase == Phase.VALIDATE
        sm.advance()
        assert sm.current_phase == Phase.COMPLETE

    def test_advance_from_complete_raises(self):
        sm = PhaseStateMachine()
        sm.transition_to(Phase.PLAN)
        sm.transition_to(Phase.EXECUTE)
        sm.transition_to(Phase.VALIDATE)
        sm.transition_to(Phase.COMPLETE)
        with pytest.raises(ValueError, match="Cannot advance"):
            sm.advance()

    def test_advance_express_skips_plan(self):
        sm = PhaseStateMachine(decision_path=DecisionPath.EXPRESS)
        assert Phase.PLAN in sm.skipped_phases
        sm.advance()
        assert sm.current_phase == Phase.EXECUTE  # skips PLAN


class TestPhaseStateMachineDecisionPath:
    """DF-CEA risk assessment and decision path selection."""

    def test_baseline_risk_is_medium(self):
        """Without any risk keywords, baseline score is 2 (MEDIUM)."""
        sm = PhaseStateMachine()
        risk = sm.assess_risk("Minor UI tweak", ["Button color"])
        assert risk == RiskLevel.MEDIUM
        path = sm.select_decision_path(risk)
        assert path == DecisionPath.STANDARD

    def test_high_risk_from_keywords(self):
        sm = PhaseStateMachine()
        risk = sm.assess_risk(
            "Migrate database with encryption and auth",
            ["Security compliance", "SSL cert rotation", "Payment data"],
            file_count=200,
        )
        # security hits: encrypt, auth, security (3) → +2
        # infra hits: database, migration (2) → +1
        # file_count > 100 → +1
        # baseline 2 + 2 + 1 + 1 = 6 → clamped to CRITICAL
        assert risk == RiskLevel.CRITICAL

    def test_evaluate_and_select(self):
        sm = PhaseStateMachine()
        risk, path = sm.evaluate_and_select("Simple script", ["Run report"])
        assert risk == RiskLevel.MEDIUM
        assert path == DecisionPath.STANDARD

    def test_medium_is_floor(self):
        """Risk assessment starts at MEDIUM and cannot go below it."""
        sm = PhaseStateMachine()
        risk, path = sm.evaluate_and_select("Hello world", [], file_count=0)
        assert risk == RiskLevel.MEDIUM
        assert path == DecisionPath.STANDARD


class TestPhaseStateMachineSerialization:
    """to_dict / from_dict round-trip."""

    def test_round_trip(self):
        sm = PhaseStateMachine(decision_path=DecisionPath.DEEP, risk_level=RiskLevel.HIGH)
        sm.transition_to(Phase.PLAN, "Planning phase", {"scope": "full"})
        sm.transition_to(Phase.EXECUTE, "Executing")
        sm.pause("Waiting for review")

        data = sm.to_dict()
        restored = PhaseStateMachine.from_dict(data)

        assert restored.current_phase == Phase.PAUSED
        assert restored.decision_path == DecisionPath.DEEP
        assert restored.risk_level == RiskLevel.HIGH
        assert restored.phase_before_pause == Phase.EXECUTE
        assert len(restored.history) == 3
        assert restored.history[0].metadata["scope"] == "full"

    def test_from_dict_empty_history(self):
        data = {
            "current_phase": "COMPLETE",
            "history": [],
            "decision_path": "standard",
            "risk_level": "medium",
            "phase_before_pause": None,
        }
        sm = PhaseStateMachine.from_dict(data)
        assert sm.current_phase == Phase.COMPLETE
        assert sm.history == []

    def test_from_dict_with_pause_history(self):
        data = {
            "current_phase": "PAUSED",
            "history": [
                {"from": "INIT", "to": "PLAN", "timestamp": 100.0, "reason": "go",
                 "decision_path": "standard", "metadata": {}},
            ],
            "decision_path": "express",
            "risk_level": "very_low",
            "phase_before_pause": "PLAN",
        }
        sm = PhaseStateMachine.from_dict(data)
        assert sm.current_phase == Phase.PAUSED
        assert sm.decision_path == DecisionPath.EXPRESS
        assert sm.risk_level == RiskLevel.VERY_LOW
        assert sm.phase_before_pause == Phase.PLAN
        assert len(sm.history) == 1


class TestPhaseStateMachineHooks:
    """Event hooks on phase transitions."""

    def test_on_enter_hook(self):
        calls = []
        hooks = PhaseHooks(on_enter={Phase.PLAN: lambda r: calls.append(("enter", r.to_phase.value))})
        sm = PhaseStateMachine(hooks=hooks)
        sm.transition_to(Phase.PLAN)
        assert len(calls) == 1
        assert calls[0] == ("enter", "PLAN")

    def test_on_exit_hook(self):
        calls = []
        hooks = PhaseHooks(on_exit={Phase.INIT: lambda r: calls.append(("exit", r.from_phase.value))})
        sm = PhaseStateMachine(hooks=hooks)
        sm.transition_to(Phase.PLAN)
        assert len(calls) == 1
        assert calls[0] == ("exit", "INIT")

    def test_hook_error_does_not_block_transition(self):
        def failing_hook(_r):
            raise RuntimeError("Hook crashed")

        hooks = PhaseHooks(on_enter={Phase.PLAN: failing_hook})
        sm = PhaseStateMachine(hooks=hooks)
        sm.transition_to(Phase.PLAN)
        assert sm.current_phase == Phase.PLAN


class TestCreateStateMachine:
    """Factory function."""

    def test_create_default(self):
        sm = create_state_machine()
        assert isinstance(sm, PhaseStateMachine)
        assert sm.current_phase == Phase.INIT

    def test_create_custom(self):
        sm = create_state_machine(
            initial_phase=Phase.EXECUTE,
            decision_path=DecisionPath.EXPRESS,
        )
        assert sm.current_phase == Phase.EXECUTE
        assert sm.decision_path == DecisionPath.EXPRESS
