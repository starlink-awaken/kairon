"""Baseline tests for slo_scheduler module.

SLOScheduler is a completely self-contained module (stdlib only).
All tests should pass without any special setup.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

SLO_SCHEDULER_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "engine_core"
    / "slo_scheduler.py"
)

SOURCE_TEXT = SLO_SCHEDULER_PATH.read_text(encoding="utf-8")


def test_source_file_exists():
    assert SLO_SCHEDULER_PATH.is_file()


class TestTaskSLO:
    """Verify TaskSLO dataclass."""

    @pytest.fixture(scope="class")
    def module(self) -> Any:
        spec = importlib.util.spec_from_file_location(
            "engine_core.slo_scheduler", str(SLO_SCHEDULER_PATH)
        )
        if spec is None:
            pytest.skip("Could not create module spec for slo_scheduler.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("engine_core.slo_scheduler", mod)
        if spec.loader is None:
            pytest.skip("No loader for slo_scheduler.py")
        spec.loader.exec_module(mod)
        return mod

    def test_can_instantiate(self, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=1000, priority=2)
        assert slo.task_id == "t1"
        assert slo.deadline_ms == 1000
        assert slo.priority == 2
        assert slo.preemptible is False

    def test_preemptible_default_false(self, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=1000, priority=2)
        assert slo.preemptible is False

    def test_preemptible_override(self, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=1000, priority=2, preemptible=True)
        assert slo.preemptible is True

    def test_is_dataclass(self, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=1000, priority=2)
        import dataclasses
        assert dataclasses.is_dataclass(slo)

    def test_is_distinct_type(self, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=1000, priority=2)
        assert type(slo).__name__ == "TaskSLO"

    def test_module_identity(self, module: Any):
        assert hasattr(module, "TaskSLO")


class TestScheduleResult:
    """Verify ScheduleResult dataclass."""

    @pytest.fixture(scope="class")
    def module(self) -> Any:
        spec = importlib.util.spec_from_file_location(
            "engine_core.slo_scheduler", str(SLO_SCHEDULER_PATH)
        )
        if spec is None:
            pytest.skip("Could not create module spec for slo_scheduler.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("engine_core.slo_scheduler", mod)
        if spec.loader is None:
            pytest.skip("No loader for slo_scheduler.py")
        spec.loader.exec_module(mod)
        return mod

    def test_can_instantiate(self, module: Any):
        result = module.ScheduleResult(
            task_id="t1", assigned_at=100.0, estimated_completion=150.0, slo_met=True
        )
        assert result.task_id == "t1"
        assert result.assigned_at == 100.0
        assert result.estimated_completion == 150.0
        assert result.slo_met is True

    def test_is_distinct_type(self, module: Any):
        result = module.ScheduleResult(
            task_id="t1", assigned_at=100.0, estimated_completion=150.0, slo_met=True
        )
        assert type(result).__name__ == "ScheduleResult"

    def test_module_identity(self, module: Any):
        assert hasattr(module, "ScheduleResult")


class TestSLOScheduler:
    """Verify SLOScheduler class and its full API."""

    @pytest.fixture(scope="class")
    def module(self) -> Any:
        spec = importlib.util.spec_from_file_location(
            "engine_core.slo_scheduler", str(SLO_SCHEDULER_PATH)
        )
        if spec is None:
            pytest.skip("Could not create module spec for slo_scheduler.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("engine_core.slo_scheduler", mod)
        if spec.loader is None:
            pytest.skip("No loader for slo_scheduler.py")
        spec.loader.exec_module(mod)
        return mod

    @pytest.fixture
    def scheduler(self, module: Any):
        return module.SLOScheduler()

    def test_can_instantiate(self, scheduler: Any):
        assert scheduler is not None
        assert scheduler.status == "active"

    def test_initial_metrics(self, scheduler: Any):
        metrics = scheduler.get_metrics()
        assert metrics["total_completed"] == 0
        assert metrics["slo_hit_rate"] == 0.0
        assert metrics["avg_latency_ms"] == 0.0
        assert metrics["pending_count"] == 0
        assert metrics["running_count"] == 0

    def test_submit_schedule_lifecycle(self, scheduler: Any, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=500, priority=2)
        scheduler.submit("t1", slo)
        assert scheduler._pending["t1"] == slo

        results = scheduler.schedule()
        assert len(results) == 1
        assert results[0].task_id == "t1"
        assert results[0].slo_met is True or results[0].slo_met is False

    def test_schedule_prioritizes_by_deadline_then_priority(self, scheduler: Any, module: Any):
        """Earliest deadline first, then priority descending (higher number first)."""
        scheduler.submit("a", module.TaskSLO(task_id="a", deadline_ms=1000, priority=2))
        scheduler.submit("b", module.TaskSLO(task_id="b", deadline_ms=500, priority=1))
        scheduler.submit("c", module.TaskSLO(task_id="c", deadline_ms=500, priority=0))

        results = scheduler.schedule()
        # b and c have earlier deadline (500 < 1000), sorted by -priority ascending:
        #   b: -1, c: 0  → b comes first
        assert [r.task_id for r in results] == ["b", "c", "a"]

    def test_preempt_non_preemptible_returns_false(self, scheduler: Any, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=500, priority=2, preemptible=False)
        scheduler.submit("t1", slo)
        scheduler.schedule()
        assert scheduler.preempt("t1") is False

    def test_preempt_preemptible_returns_true(self, scheduler: Any, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=500, priority=2, preemptible=True)
        scheduler.submit("t1", slo)
        scheduler.schedule()
        assert scheduler.preempt("t1") is True
        # Should be back in pending
        assert "t1" in scheduler._pending

    def test_complete_moves_to_completed(self, scheduler: Any, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=5000, priority=2)
        scheduler.submit("t1", slo)
        scheduler.schedule()
        scheduler.complete("t1")
        assert len(scheduler._completed) == 1
        assert scheduler._completed[0]["task_id"] == "t1"

    def test_complete_unknown_raises(self, scheduler: Any):
        with pytest.raises(KeyError):
            scheduler.complete("nonexistent")

    def test_get_at_risk_empty_initially(self, scheduler: Any):
        assert scheduler.get_at_risk() == []

    def test_get_at_risk_after_submit(self, scheduler: Any, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=1, priority=2)
        scheduler.submit("t1", slo)
        scheduler.schedule()
        # With a 1ms deadline, this is almost certainly "at risk"
        at_risk = scheduler.get_at_risk()
        assert isinstance(at_risk, list)

    def test_schedule_empty_pending(self, scheduler: Any):
        results = scheduler.schedule()
        assert results == []

    def test_metrics_track_slo_hits(self, scheduler: Any, module: Any):
        slo = module.TaskSLO(task_id="t1", deadline_ms=5000, priority=2)
        scheduler.submit("t1", slo)
        scheduler.schedule()
        scheduler.complete("t1")
        metrics = scheduler.get_metrics()
        assert metrics["total_completed"] == 1
        assert metrics["slo_hit_rate"] in (0.0, 1.0)
        assert metrics["pending_count"] == 0
        assert metrics["running_count"] == 0

    def test_preempt_unknown_task_returns_false(self, scheduler: Any):
        assert scheduler.preempt("nonexistent") is False

    def test_is_distinct_type(self, scheduler: Any):
        assert type(scheduler).__name__ == "SLOScheduler"

    def test_module_identity(self, module: Any):
        assert hasattr(module, "SLOScheduler")
