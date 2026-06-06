"""Tests for symphony-protocol trigger engine — TriggerEngine."""

from unittest.mock import MagicMock

import pytest
from symphony_protocol.models import Trigger
from symphony_protocol.triggers import (
    TriggerEngine,
    create_default_triggers,
    setup_trigger_engine,
)


class TestTriggerEngineInit:
    """TriggerEngine.__init__: initial state"""

    def test_no_stage_manager_by_default(self):
        engine = TriggerEngine()
        assert engine._stage_manager is None

    def test_empty_triggers(self):
        engine = TriggerEngine()
        assert engine.get_all_triggers() == []

    def test_empty_history(self):
        engine = TriggerEngine()
        assert engine.get_history() == []


class TestTriggerEngineRegistration:
    """TriggerEngine: register, unregister, enable, disable triggers"""

    def test_register_trigger(self):
        engine = TriggerEngine()
        t = Trigger(id="tr1", name="test", condition=lambda ctx: True, action=lambda: None)
        engine.register_trigger(t)
        assert engine.get_trigger("tr1") == t
        assert len(engine.get_all_triggers()) == 1

    def test_unregister_trigger(self):
        engine = TriggerEngine()
        t = Trigger(id="tr1", name="test", condition=lambda ctx: True, action=lambda: None)
        engine.register_trigger(t)
        engine.unregister_trigger("tr1")
        assert engine.get_trigger("tr1") is None

    def test_unregister_nonexistent_does_not_raise(self):
        engine = TriggerEngine()
        engine.unregister_trigger("nonexistent")  # should not raise

    def test_enable_trigger(self):
        engine = TriggerEngine()
        t = Trigger(id="tr1", name="test", enabled=False)
        engine.register_trigger(t)
        engine.enable_trigger("tr1")
        assert engine.get_trigger("tr1").enabled is True

    def test_enable_nonexistent_does_not_raise(self):
        engine = TriggerEngine()
        engine.enable_trigger("nonexistent")

    def test_disable_trigger(self):
        engine = TriggerEngine()
        t = Trigger(id="tr1", name="test", enabled=True)
        engine.register_trigger(t)
        engine.disable_trigger("tr1")
        assert engine.get_trigger("tr1").enabled is False

    def test_disable_nonexistent_does_not_raise(self):
        engine = TriggerEngine()
        engine.disable_trigger("nonexistent")


class TestTriggerEngineEvaluate:
    """TriggerEngine.evaluate_and_trigger: condition evaluation"""

    def test_trigger_fires_when_condition_met(self):
        engine = TriggerEngine()
        action = MagicMock(return_value="done")
        t = Trigger(id="tr1", name="test", condition=lambda ctx: True, action=action)
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger({"key": "value"})
        assert len(results) == 1
        assert results[0].triggered is True
        assert results[0].action_result == "done"
        action.assert_called_once()

    def test_trigger_does_not_fire_when_condition_not_met(self):
        engine = TriggerEngine()
        action = MagicMock()
        t = Trigger(id="tr1", name="test", condition=lambda ctx: False, action=action)
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger({"key": "value"})
        assert len(results) == 1
        assert results[0].triggered is False
        action.assert_not_called()

    def test_disabled_triggers_are_skipped(self):
        engine = TriggerEngine()
        t = Trigger(id="tr1", name="test", condition=lambda ctx: True, enabled=False)
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger({})
        assert len(results) == 0

    def test_triggers_sorted_by_priority(self):
        engine = TriggerEngine()
        call_order = []

        low = Trigger(id="low", name="low", priority=10, condition=lambda ctx: True, action=lambda: call_order.append("low"))
        high = Trigger(id="high", name="high", priority=100, condition=lambda ctx: True, action=lambda: call_order.append("high"))
        engine.register_trigger(low)
        engine.register_trigger(high)
        engine.evaluate_and_trigger({})
        assert call_order == ["high", "low"]

    def test_context_from_stage_manager_when_not_provided(self):
        sm = MagicMock()
        sm.get_context.return_value = {"key": "from_sm"}
        engine = TriggerEngine(stage_manager=sm)
        t = Trigger(id="tr1", name="test", condition=lambda ctx: ctx.get("key") == "from_sm")
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger()
        assert results[0].triggered is True

    def test_empty_context_when_no_stage_manager(self):
        engine = TriggerEngine()
        t = Trigger(id="tr1", name="test", condition=lambda ctx: ctx == {})
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger()
        assert results[0].triggered is True

    def test_exception_in_trigger_caught(self):
        engine = TriggerEngine()
        def failing_condition(ctx):
            raise RuntimeError("condition failed")
        t = Trigger(id="tr1", name="fail", condition=failing_condition)
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger({})
        assert results[0].triggered is False
        assert "执行失败" in results[0].message

    def test_history_updated(self):
        engine = TriggerEngine()
        t = Trigger(id="tr1", name="test", condition=lambda ctx: True)
        engine.register_trigger(t)
        engine.evaluate_and_trigger({})
        engine.evaluate_and_trigger({})
        assert len(engine.get_history()) == 2

    def test_clear_history(self):
        engine = TriggerEngine()
        t = Trigger(id="tr1", name="test", condition=lambda ctx: True)
        engine.register_trigger(t)
        engine.evaluate_and_trigger({})
        engine.clear_history()
        assert engine.get_history() == []


class TestTriggerEngineSetStageManager:
    """TriggerEngine.set_stage_manager: inject stage manager"""

    def test_set_stage_manager(self):
        engine = TriggerEngine()
        sm = MagicMock()
        engine.set_stage_manager(sm)
        assert engine._stage_manager == sm


class TestTriggerEngineStatus:
    """TriggerEngine.get_status: status summary"""

    def test_status_shows_counts(self):
        engine = TriggerEngine()
        t1 = Trigger(id="tr1", name="one", enabled=True)
        t2 = Trigger(id="tr2", name="two", enabled=False)
        engine.register_trigger(t1)
        engine.register_trigger(t2)
        status = engine.get_status()
        assert status["total_triggers"] == 2
        assert status["enabled_triggers"] == 1
        assert status["disabled_triggers"] == 1
        assert status["is_running"] is False
        assert status["history_count"] == 0


class TestTriggerEngineMonitoring:
    """TriggerEngine monitoring lifecycle"""

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self):
        engine = TriggerEngine()
        assert engine._running is False

        task = await engine.start_monitoring_task(interval=0.01)
        assert engine._running is True

        engine.stop_monitoring()
        assert engine._running is False

        task.cancel()

    @pytest.mark.asyncio
    async def test_monitoring_evaluates_triggers(self):
        engine = TriggerEngine()
        action = MagicMock()
        t = Trigger(id="tr1", name="test", condition=lambda ctx: True, action=action)
        engine.register_trigger(t)

        monitoring_task = await engine.start_monitoring_task(interval=0.01)
        await asyncio.sleep(0.05)
        engine.stop_monitoring()
        monitoring_task.cancel()
        # At least one evaluation should have occurred
        assert len(engine.get_history()) >= 1


# Need asyncio for monitoring tests
import asyncio


class TestCreateDefaultTriggers:
    """create_default_triggers: factory for standard triggers"""

    def test_returns_four_triggers(self):
        sm = MagicMock()
        triggers = create_default_triggers(sm)
        assert len(triggers) == 4

    def test_triggers_have_correct_ids(self):
        sm = MagicMock()
        triggers = create_default_triggers(sm)
        ids = {t.id for t in triggers}
        assert ids == {"anchoring_to_scaffolding", "scaffolding_to_implementation",
                        "implementation_to_polishing", "polishing_to_complete"}

    def test_anchoring_trigger_condition(self):
        sm = MagicMock()
        triggers = create_default_triggers(sm)
        anchor = [t for t in triggers if t.id == "anchoring_to_scaffolding"][0]
        # Condition met
        assert anchor.condition({"context_completeness": 0.95, "ambiguities": [], "truth_locked": True}) is True
        # Condition not met
        assert anchor.condition({"context_completeness": 0.5, "ambiguities": [], "truth_locked": True}) is False

    def test_triggers_have_priority_100(self):
        sm = MagicMock()
        triggers = create_default_triggers(sm)
        for t in triggers:
            assert t.priority == 100


class TestSetupTriggerEngine:
    """setup_trigger_engine: factory function"""

    def test_returns_trigger_engine(self):
        sm = MagicMock()
        engine = setup_trigger_engine(sm)
        assert isinstance(engine, TriggerEngine)

    def test_registers_four_default_triggers(self):
        sm = MagicMock()
        engine = setup_trigger_engine(sm)
        assert len(engine.get_all_triggers()) == 4

    def test_stage_manager_is_set(self):
        sm = MagicMock()
        engine = setup_trigger_engine(sm)
        assert engine._stage_manager == sm
