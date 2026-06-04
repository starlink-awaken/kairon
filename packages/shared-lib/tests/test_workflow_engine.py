"""Tests for kairon_lib.workflow_engine — WorkflowEngine."""

import time

from kairon_lib.workflow_engine import (
    GateReview,
    PhaseContext,
    Retrospective,
    WorkflowEngine,
    WorkflowPhase,
    WorkflowStatus,
    WorkstreamSpec,
)


class TestWorkflowPhase:
    def test_enum_values(self):
        assert WorkflowPhase.OBSERVE.value == "observe"
        assert WorkflowPhase.THINK.value == "think"
        assert WorkflowPhase.PLAN.value == "plan"
        assert WorkflowPhase.EXECUTE.value == "execute"
        assert WorkflowPhase.VERIFY.value == "verify"
        assert WorkflowPhase.LEARN.value == "learn"


class TestWorkflowStatus:
    def test_values(self):
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.DONE.value == "done"
        assert WorkflowStatus.FAILED.value == "failed"


class TestWorkstreamSpec:
    def test_defaults(self):
        ws = WorkstreamSpec(ws_id="ws-1", title="Auth")
        assert ws.status == WorkflowStatus.PENDING
        assert ws.tests_added == 0

    def test_start_and_complete(self):
        ws = WorkstreamSpec(ws_id="ws-1", title="Auth")
        ws.start()
        assert ws.status == WorkflowStatus.IN_PROGRESS
        assert ws.started_at is not None

        ws.complete(commit="abc123", tests_added=5)
        assert ws.status == WorkflowStatus.DONE
        assert ws.commit == "abc123"
        assert ws.tests_added == 5
        assert ws.duration_s is not None

    def test_duration_before_complete(self):
        ws = WorkstreamSpec(ws_id="ws-1", title="Test")
        assert ws.duration_s is None

    def test_duration_after_complete(self):
        ws = WorkstreamSpec(ws_id="ws-1", title="Test")
        ws.start()
        time.sleep(0.01)
        ws.complete()
        assert ws.duration_s is not None
        assert ws.duration_s > 0


class TestGateReview:
    def test_check_gate_passes(self):
        review = GateReview("OBSERVE", test_count=15, test_baseline=10, ruff_errors=0)
        assert review.tests_added == 5
        assert review.check_gate(min_tests_added=3) is True

    def test_check_gate_fails_not_enough_tests(self):
        review = GateReview("OBSERVE", test_count=11, test_baseline=10, ruff_errors=0)
        assert review.check_gate(min_tests_added=3) is False

    def test_check_gate_fails_ruff_errors(self):
        review = GateReview("OBSERVE", test_count=15, test_baseline=10, ruff_errors=5)
        assert review.check_gate(min_tests_added=3, max_ruff_errors=2) is False


class TestRetrospective:
    def test_defaults(self):
        r = Retrospective(phase_name="EXECUTE")
        assert r.what_went_well == []
        assert r.archived_at > 0


class TestPhaseContext:
    def test_record(self):
        ctx = PhaseContext(phase=WorkflowPhase.OBSERVE)
        ctx.record("requirement", "add auth")
        assert ctx.data["requirement"] == "add auth"

    def test_add_workstream(self):
        ctx = PhaseContext(phase=WorkflowPhase.PLAN)
        ws = ctx.add_workstream("ws-auth", "Auth module", owner="@Forge", tasks=["design", "implement"])
        assert ws.ws_id == "ws-auth"
        assert ws.owner == "@Forge"
        assert ws.tasks == ["design", "implement"]
        assert ws in ctx.workstreams


class TestWorkflowEngine:
    def test_initial_state(self):
        engine = WorkflowEngine(name="Test Flow")
        summary = engine.get_summary()
        assert summary["name"] == "Test Flow"
        assert summary["phases_completed"] == []
        assert summary["workstreams"] == 0

    def test_context_manager(self):
        engine = WorkflowEngine(name="CM Test")
        with engine.phase(WorkflowPhase.OBSERVE) as ctx:
            ctx.record("input", "user request")
            ctx.add_workstream("ws-1", "Discovery")

        summary = engine.get_summary()
        assert "observe" in summary["phases_completed"]
        assert summary["workstreams"] == 1

    def test_multiple_phases(self):
        engine = WorkflowEngine(name="Multi")
        with engine.phase(WorkflowPhase.OBSERVE) as ctx:
            ctx.record("req", "build X")
        with engine.phase(WorkflowPhase.THINK) as ctx:
            ctx.record("analysis", "use Y pattern")
        with engine.phase(WorkflowPhase.PLAN) as ctx:
            ctx.add_workstream("ws-a", "Module A")
            ctx.add_workstream("ws-b", "Module B")

        summary = engine.get_summary()
        assert len(summary["phases_completed"]) == 3
        assert summary["workstreams"] == 2

    def test_gate_review_and_retrospective(self):
        engine = WorkflowEngine(name="Gate Test")
        with engine.phase(WorkflowPhase.EXECUTE) as ctx:
            ctx.add_workstream("ws-1", "Feature X")
        engine.add_gate_review(
            GateReview("EXECUTE", test_count=20, test_baseline=10, ruff_errors=0)
        )
        engine.add_retrospective(
            Retrospective("EXECUTE", what_went_well=["shipped on time"])
        )

        summary = engine.get_summary()
        assert summary["gate_reviews"] == 1
        assert summary["retrospectives"] == 1

    def test_get_phase_context_not_started(self):
        engine = WorkflowEngine(name="NoCtx")
        assert engine.get_phase_context(WorkflowPhase.VERIFY) is None

    def test_phase_context_lifecycle(self):
        engine = WorkflowEngine(name="Lifecycle")
        with engine.phase(WorkflowPhase.LEARN) as ctx:
            ctx.record("lesson", "test early")
        ctx = engine.get_phase_context(WorkflowPhase.LEARN)
        assert ctx is not None
        assert ctx.data["lesson"] == "test early"

    def test_no_duplicate_phase(self):
        engine = WorkflowEngine(name="NoDup")
        with engine.phase(WorkflowPhase.OBSERVE):
            pass
        with engine.phase(WorkflowPhase.OBSERVE):
            pass  # second context doesn't overwrite the first
        summary = engine.get_summary()
        # phases_completed should have "observe" listed only once conceptually
        assert summary["phases_completed"].count("observe") == 1
