"""Tests for kairon_lib.emergency_stop — EmergencyStop, StopEvent, StopStatus."""

import pytest
from kairon_lib.emergency_stop import EmergencyStop


class TestEmergencyStop:
    def setup_method(self):
        # Reset singleton before each test
        EmergencyStop._instance = None

    def test_initial_state(self):
        stop = EmergencyStop()
        assert stop.is_stopped() is False
        assert stop.status == "ACTIVE"

    def test_emergency_stop_activates(self):
        stop = EmergencyStop()
        event = stop.emergency_stop(reason="Security breach", actor="@Prime")
        assert event.event_type == "emergency_stop"
        assert event.actor == "@Prime"
        assert event.reason == "Security breach"
        assert stop.is_stopped() is True

    def test_emergency_stop_raises_on_empty_reason(self):
        stop = EmergencyStop()
        with pytest.raises(ValueError, match="non-empty string"):
            stop.emergency_stop(reason="", actor="@Prime")

    def test_emergency_stop_raises_on_empty_actor(self):
        stop = EmergencyStop()
        with pytest.raises(ValueError, match="non-empty string"):
            stop.emergency_stop(reason="test", actor="")

    def test_duplicate_stop_returns_existing_event(self):
        stop = EmergencyStop()
        event1 = stop.emergency_stop(reason="First", actor="@Prime")
        event2 = stop.emergency_stop(reason="Second", actor="@Prime")
        assert event2.id == event1.id  # same event returned

    def test_resume_after_stop(self):
        stop = EmergencyStop()
        stop.emergency_stop(reason="test", actor="@Prime")
        event = stop.resume(actor="@Prime", reason="All clear")
        assert event.event_type == "resume"
        assert stop.is_stopped() is False

    def test_resume_when_not_stopped(self):
        stop = EmergencyStop()
        event = stop.resume(actor="@Prime", reason="resume")
        assert event.event_type == "resume"
        assert "No-op" in event.reason

    def test_resume_raises_on_empty_actor(self):
        stop = EmergencyStop()
        with pytest.raises(ValueError, match="non-empty string"):
            stop.resume(actor="", reason="test")

    def test_get_status_when_running(self):
        stop = EmergencyStop()
        status = stop.get_status()
        assert status["stopped"] is False
        assert status["status"] == "running"

    def test_get_status_when_stopped(self):
        stop = EmergencyStop()
        stop.emergency_stop(reason="test", actor="@Prime")
        status = stop.get_status()
        assert status["stopped"] is True
        assert status["stopped_by"] == "@Prime"
        assert status["stop_reason"] == "test"

    def test_get_stop_history(self):
        stop = EmergencyStop()
        stop.emergency_stop(reason="stop1", actor="@Prime")
        stop.resume(actor="@Prime", reason="resume1")
        stop.emergency_stop(reason="stop2", actor="@Prime")
        history = stop.get_stop_history()
        assert len(history) == 3

    def test_scheduled_task_registration(self):
        stop = EmergencyStop()
        stop.register_scheduled_task("task-1")
        assert stop.is_task_active("task-1") is True

    def test_scheduled_task_blocked_when_stopped(self):
        stop = EmergencyStop()
        stop.register_scheduled_task("task-1")
        stop.emergency_stop(reason="test", actor="@Prime")
        assert stop.is_task_active("task-1") is False

    def test_scheduled_task_blocked_after_stop_then_register(self):
        stop = EmergencyStop()
        stop.emergency_stop(reason="test", actor="@Prime")
        stop.register_scheduled_task("task-2")
        assert stop.is_task_active("task-2") is False

    def test_unregister_scheduled_task(self):
        stop = EmergencyStop()
        stop.register_scheduled_task("task-1")
        stop.unregister_scheduled_task("task-1")
        # After unregister, the check should return True (task not found)
        assert stop.is_task_active("task-1") is True

    def test_task_becomes_active_after_resume(self):
        stop = EmergencyStop()
        stop.register_scheduled_task("task-1")
        stop.emergency_stop(reason="test", actor="@Prime")
        stop.resume(actor="@Prime", reason="all clear")
        assert stop.is_task_active("task-1") is True

    def test_get_instance_singleton(self):
        EmergencyStop._instance = None
        s1 = EmergencyStop.get_instance()
        s2 = EmergencyStop.get_instance()
        assert s1 is s2
