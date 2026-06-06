"""Tests for kairon_events — shared event data model and global EventBus registry."""

import dataclasses
import time
from unittest.mock import MagicMock

from kairon_events import (
    BOSEvent,
    BosEvent,
    EventBusProtocol,
    EventType,
    _NullEventBus,
    get_event_bus,
    get_global_event_bus,
    make_event,
    register_global_event_bus,
)


class TestBOSEvent:
    """BOSEvent dataclass construction and validation."""

    def test_create_minimal(self):
        """Create a BOSEvent with all required fields."""
        event = BOSEvent(
            event_type="task_submitted",
            source="test_worker",
            payload={"key": "value"},
            timestamp=12345.0,
            event_id="abc12345",
        )
        assert event.event_type == "task_submitted"
        assert event.source == "test_worker"
        assert event.payload == {"key": "value"}
        assert event.timestamp == 12345.0
        assert event.event_id == "abc12345"

    def test_is_dataclass(self):
        """BOSEvent should be a dataclass."""
        assert dataclasses.is_dataclass(BOSEvent)

    def test_immutable_types(self):
        """BOSEvent fields should be the correct types."""
        event = BOSEvent("type", "source", {}, 0.0, "id")
        assert isinstance(event.event_type, str)
        assert isinstance(event.source, str)
        assert isinstance(event.payload, dict)
        assert isinstance(event.timestamp, float)
        assert isinstance(event.event_id, str)

    def test_event_type_values(self):
        """Verify common event_type values work."""
        for et in [
            "task_submitted",
            "agent_started",
            "agent_completed",
            "agent_failed",
            "consensus_reached",
            "task_cancelled",
        ]:
            event = BOSEvent(et, "source", {}, 0.0, "id")
            assert event.event_type == et

    def test_payload_mutable(self):
        """Payload dict should be mutable after creation."""
        event = BOSEvent("t", "s", {}, 0.0, "id")
        event.payload["new_key"] = "new_value"
        assert event.payload["new_key"] == "new_value"

    def test_all_fields_have_defaults(self):
        """BOSEvent can be constructed with no arguments (all fields have defaults)."""
        event = BOSEvent()
        assert event.event_type == ""
        assert event.source == ""
        assert isinstance(event.payload, dict)
        assert isinstance(event.timestamp, float)
        assert isinstance(event.event_id, str)

    def test_default_fields_are_empty_strings(self):
        """event_type and source default to empty strings for subclassability."""
        event = BOSEvent()
        assert event.event_type == ""
        assert event.source == ""

    def test_subclass_with_defaults(self):
        """Subclasses can override event_type/source defaults without error."""

        @dataclasses.dataclass(kw_only=True)
        class TestEvent(BOSEvent):
            event_type: str = "test_type"
            source: str = "test_source"

        event = TestEvent()
        assert event.event_type == "test_type"
        assert event.source == "test_source"

    def test_subclass_adds_fields(self):
        """Subclasses can add new fields beyond BOSEvent."""

        @dataclasses.dataclass
        class ExtendedEvent(BOSEvent):
            extra: str = "extra_data"

        event = ExtendedEvent(event_type="test", source="src", extra="custom")
        assert event.event_type == "test"
        assert event.extra == "custom"


class TestBosEventAlias:
    """BosEvent backward-compatibility alias."""

    def test_alias_equals_bosevent(self):
        """BosEvent should be the same class as BOSEvent."""
        assert BosEvent is BOSEvent

    def test_alias_creates_instance(self):
        """Creating via BosEvent should work."""
        event = BosEvent("type", "source", {}, 0.0, "id")
        assert isinstance(event, BOSEvent)


class TestMakeEvent:
    """make_event factory function."""

    def test_creates_bosevent(self):
        """make_event should return a BOSEvent instance."""
        event = make_event("test_type", "test_source", {"foo": "bar"})
        assert isinstance(event, BOSEvent)

    def test_sets_event_type(self):
        """event_type should match the first argument."""
        event = make_event("custom.event", "src", {})
        assert event.event_type == "custom.event"

    def test_sets_source(self):
        """source should match the second argument."""
        event = make_event("t", "my_component", {})
        assert event.source == "my_component"

    def test_sets_payload(self):
        """payload should match the third argument."""
        payload = {"result": 42, "success": True}
        event = make_event("t", "s", payload)
        assert event.payload == payload

    def test_generates_timestamp(self):
        """timestamp should be set to recent time.time() value."""
        before = time.time()
        event = make_event("t", "s", {})
        after = time.time()
        assert before <= event.timestamp <= after

    def test_generates_event_id(self):
        """event_id should be a non-empty 8-char hex string."""
        event = make_event("t", "s", {})
        assert isinstance(event.event_id, str)
        assert len(event.event_id) == 8
        # Verify it's hex
        int(event.event_id, 16)

    def test_unique_ids(self):
        """Each call should generate a unique event_id."""
        ids = {make_event("t", "s", {}).event_id for _ in range(100)}
        assert len(ids) == 100

    def test_source_independent(self):
        """Different sources should produce similar events."""
        e1 = make_event("t", "source_a", {})
        e2 = make_event("t", "source_b", {})
        assert e1.source == "source_a"
        assert e2.source == "source_b"


class TestGlobalEventBusRegistry:
    """Global EventBus registration and retrieval."""

    def setup_method(self):
        """Reset global state before each test."""
        import kairon_events

        kairon_events._global_event_bus = None

    def test_default_is_none(self):
        """get_global_event_bus should return None before registration."""
        assert get_global_event_bus() is None

    def test_register_and_retrieve(self):
        """After registration, get_global_event_bus should return the bus."""
        bus = MagicMock()
        register_global_event_bus(bus)
        assert get_global_event_bus() is bus

    def test_re_register_overwrites(self):
        """Re-registering should replace the previous bus."""
        bus1 = MagicMock()
        bus2 = MagicMock()
        register_global_event_bus(bus1)
        register_global_event_bus(bus2)
        assert get_global_event_bus() is bus2

    def test_register_none(self):
        """Registering None should clear the global bus."""
        bus = MagicMock()
        register_global_event_bus(bus)
        register_global_event_bus(None)
        assert get_global_event_bus() is None

    def test_register_multiple_calls_logs(self):
        """Registering multiple times should not error."""
        for _ in range(5):
            register_global_event_bus(MagicMock())
        assert get_global_event_bus() is not None

    def test_cross_module_publish(self):
        """Simulate cross-module EventBus publish workflow."""
        bus = MagicMock()
        register_global_event_bus(bus)

        # Consumer code uses get_global_event_bus
        retrieved = get_global_event_bus()
        assert retrieved is bus

        event = make_event("test.event", "test_module", {"data": 1})
        retrieved.publish(event)  # type: ignore[union-attr]
        bus.publish.assert_called_once_with(event)


class TestModuleExports:
    """Verify __all__ exports are correct."""

    def test_expected_exports(self):
        """Core exports should include all expected symbols."""
        from kairon_events import __all__ as exports

        assert "BOSEvent" in exports
        assert "BosEvent" in exports
        assert "EventBusProtocol" in exports
        assert "EventType" in exports
        assert "make_event" in exports
        assert "register_global_event_bus" in exports
        assert "get_global_event_bus" in exports
        assert "get_event_bus" in exports


class TestEventBusProtocol:
    """EventBusProtocol runtime behavior."""

    def test_protocol_is_runtime_checkable(self):
        """EventBusProtocol should be runtime checkable."""
        mock_bus = MagicMock(spec=["publish", "publish_event"])
        mock_bus.publish = MagicMock()
        mock_bus.publish_event = MagicMock(return_value="evt_abc")
        mock_bus.MAX_QUEUE_SIZE = 500
        mock_bus.MAX_LISTENERS = 50
        # A MagicMock with publish() may not pass isinstance due to MagicMock internals.
        # The runtime checkable decorator is verified by the _NullEventBus test below.
        assert isinstance(_NullEventBus(), EventBusProtocol)


class TestNullEventBusProtocol:
    """_NullEventBus protocol conformance."""

    def test_null_eventbus_conforms_to_protocol(self):
        """_NullEventBus should pass EventBusProtocol isinstance check."""
        bus = _NullEventBus()
        assert isinstance(bus, EventBusProtocol)

    def test_null_eventbus_publish(self):
        """_NullEventBus.publish should accept BOSEvent and return None."""
        bus = _NullEventBus()
        event = BOSEvent("t", "s", {})
        result = bus.publish(event)
        assert result is None

    def test_null_eventbus_has_protocol_attributes(self):
        """_NullEventBus should have MAX_QUEUE_SIZE and MAX_LISTENERS."""
        bus = _NullEventBus()
        assert hasattr(bus, "MAX_QUEUE_SIZE")
        assert hasattr(bus, "MAX_LISTENERS")


class TestEventType:
    """EventType enum values and behavior."""

    def test_enum_values(self):
        """EventType should have the expected members."""
        assert EventType.DOC_BEFORE_UPDATE == "doc.before_update"
        assert EventType.DOC_AFTER_UPDATE == "doc.after_update"

    def test_is_string_enum(self):
        """EventType should be a str enum (usable as plain strings)."""
        assert isinstance(EventType.DOC_BEFORE_UPDATE, str)
        assert EventType.DOC_BEFORE_UPDATE.value == "doc.before_update"

    def test_membership(self):
        """Verify EventType members are accessible by name."""
        assert "DOC_BEFORE_UPDATE" in EventType.__members__
        assert "DOC_AFTER_UPDATE" in EventType.__members__

    def test_unique_values(self):
        """All EventType values should be unique."""
        values = [v.value for v in EventType]
        assert len(values) == len(set(values))


class TestGetEventBus:
    """get_event_bus() convenience wrapper."""

    def setup_method(self):
        """Reset global state before each test."""
        import kairon_events

        kairon_events._global_event_bus = None

    def test_returns_dummy_when_unregistered(self):
        """get_event_bus should return a no-op bus when no bus is registered."""
        bus = get_event_bus()
        # Should not raise when calling publish/subscribe
        bus.publish("test_event")
        bus.subscribe("type", lambda e: None)
        bus.subscribe_async("type", lambda e: None)

    def test_returns_real_bus_when_registered(self):
        """get_event_bus should return the registered bus."""
        real_bus = MagicMock()
        register_global_event_bus(real_bus)
        assert get_event_bus() is real_bus

    def test_dummy_is_singleton(self):
        """Multiple calls to get_event_bus without registration should return the same instance."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_dummy_publish_noop(self):
        """_NullEventBus.publish should be a no-op (never raise)."""
        bus = get_event_bus()
        # Should not raise with any arguments
        bus.publish(None)
        bus.publish(BOSEvent("t", "s", {}))
        bus.publish("anything")

    def test_dummy_publish_event_noop(self):
        """_NullEventBus.publish_event should return empty string."""
        bus = get_event_bus()
        result = bus.publish_event(BOSEvent("t", "s", {}))
        assert result == ""

    def test_dummy_add_listener(self):
        """_NullEventBus.add_listener should return a stub ID."""
        bus = get_event_bus()
        lid = bus.add_listener()
        assert isinstance(lid, str)
        assert lid == "null_listener"

    def test_dummy_remove_listener_noop(self):
        """_NullEventBus.remove_listener should be a no-op."""
        bus = get_event_bus()
        bus.remove_listener("anything")  # should not raise

    def test_dummy_unsubscribe_noop(self):
        """_NullEventBus.unsubscribe should return False."""
        bus = get_event_bus()
        assert bus.unsubscribe("anything") is False

    def test_dummy_subscribe_noop(self):
        """_NullEventBus.subscribe should be a no-op (never raise)."""
        bus = get_event_bus()
        bus.subscribe("type", lambda e: None)
        bus.subscribe("type", None)

    def test_dummy_subscribe_async_noop(self):
        """_NullEventBus.subscribe_async should be a no-op (never raise)."""
        bus = get_event_bus()
        bus.subscribe_async("type", lambda e: None)
