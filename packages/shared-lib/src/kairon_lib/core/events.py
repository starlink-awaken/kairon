"""Shared event data model for kairon event bus systems.

This module provides the canonical ``BOSEvent`` dataclass and ``make_event``
factory used across all EventBus implementations (engine-core, agora, etc.)
It also provides a global EventBus registry so cross-package consumers can
access the engine-core EventBus singleton without fragile importlib paths.

Usage:

    .. code-block:: python

        from kairon_lib.events import BOSEvent, make_event

        # Create and publish an event
        bus = get_global_event_bus()
        if bus is not None:
            bus.publish(make_event("task_submitted", "my_worker", {"key": "val"}))

Layer: L0 (shared primitive — no dependencies on other kairon packages)
Domain: kairon shared-lib
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

_log = logging.getLogger(__name__)


# =============================================================================
# Event data model
# =============================================================================


@runtime_checkable
class EventBusProtocol(Protocol):
    """Canonical EventBus interface that all implementations must conform to.

    This protocol ensures that engine-core, agora, and any future EventBus
    implementations all expose a consistent ``publish(BOSEvent)`` method,
    enabling cross-package event publishing without fragile importlib paths.

    Usage:

        .. code-block:: python

            bus: EventBusProtocol = get_global_event_bus()
            if bus is not None:
                bus.publish(make_event("task_submitted", "my_worker", {"key": "val"}))

    Layer: L0 (shared primitive — no dependencies on other kairon packages)
    Domain: kairon shared-lib
    """

    def publish(self, event: BOSEvent) -> None:
        """Broadcast *event* to all registered consumers.

        Args:
            event: The :class:`BOSEvent` to broadcast.
        """
        ...


@dataclass
class BOSEvent:
    """A single timestamped event in the B-OS event stream.

    This is the **canonical** event data model shared across all
    EventBus implementations (engine-core, agora, minerva, etc.).

    All fields have defaults so that subclasses (e.g. minerva's
    ``KnowledgeEvent``) can override ``event_type`` and ``source``
    without violating dataclass field-ordering constraints.  When
    creating events directly, always pass explicit values.

    Attributes:
        event_type: Semantic category of the event. One of:
            ``"task_submitted"`` | ``"agent_started"`` | ``"agent_completed"`` |
            ``"agent_failed"`` | ``"consensus_reached"`` | ``"task_cancelled"`` |
            ``"knowledge_created"`` | ``"knowledge_updated"`` | ``"knowledge_deleted"``
        source:     Emitting component, e.g. ``"execution_scheduler"`` |
                    ``"hatcher"`` | ``"consensus_monitor"`` | ``"result_bus"`` |
                    ``"knowledge_store"``
        payload:    Arbitrary event-specific data dictionary.
        timestamp:  Wall-clock time as a float (``time.time()``).
        event_id:   Short unique identifier (8-char hex from uuid4).
    """

    event_type: str = ""
    source: str = ""
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid4())[:8])


# Alias for backward compatibility with code that imports ``BosEvent``
# (camelCase variant).  New code should use ``BOSEvent`` directly.
BosEvent = BOSEvent


def make_event(event_type: str, source: str, payload: dict) -> BOSEvent:
    """Convenience factory that fills in timestamp and event_id automatically.

    Args:
        event_type: Semantic category of the event.
        source:     Emitting component name.
        payload:    Arbitrary event-specific data dictionary.

    Returns:
        A fully populated :class:`BOSEvent` instance.
    """
    return BOSEvent(
        event_type=event_type,
        source=source,
        payload=payload,
        timestamp=time.time(),
        event_id=str(uuid4())[:8],
    )


# =============================================================================
# Global EventBus registry (cross-package singleton access)
# =============================================================================
#
# engine-core registers its EventBus singleton here at startup so that
# shared-lib / agora / minerva code can publish events without resorting
# to fragile ``importlib.import_module("organs.D_Execution.organs.engine.event_bus")``
# paths.
#
# This mechanism is *optional* — packages that already hold a reference
# to their local EventBus should continue using it.


_global_event_bus: Any | None = None


def register_global_event_bus(bus: Any) -> None:
    """Register the engine-core (or other) EventBus singleton.

    Called once during daemon startup from :meth:`EventBus.get_instance`.

    Args:
        bus: An EventBus instance that supports ``publish(BOSEvent)``.
    """
    global _global_event_bus
    _global_event_bus = bus
    _log.debug("[events] Global EventBus registered: %s", type(bus).__name__)


def get_global_event_bus() -> Any | None:
    """Return the registered global EventBus, or ``None`` if not yet registered.

    The returned object supports ``publish(event: BOSEvent) -> None``.
    """
    return _global_event_bus


# =============================================================================
# EventType enum (canonical shared event types)
# =============================================================================


class EventType(StrEnum):
    """Canonical event types for domain-level events.

    These are the canonical event types shared across all EventBus consumers.
    Individual domains may define additional types locally.

    Members:
        DOC_BEFORE_UPDATE:  Emitted before a document is updated.
        DOC_AFTER_UPDATE:   Emitted after a document has been updated.
    """

    DOC_BEFORE_UPDATE = "doc.before_update"
    DOC_AFTER_UPDATE = "doc.after_update"


# =============================================================================
# Null EventBus (no-op fallback)
# =============================================================================


class _NullEventBus:
    """Silent no-op bus returned when the real EventBus is unavailable.

    Conforms to :class:`EventBusProtocol` so callers can call ``publish``
    without guarding every call with a ``None`` check.
    """

    MAX_QUEUE_SIZE: int = 0
    MAX_LISTENERS: int = 0

    def publish(self, event: BOSEvent) -> None:
        """No-op publish — silently discard *event*."""
        return None

    def publish_event(self, event: Any) -> str:
        """No-op publish_event — silently discard *event*, return empty ID."""
        return ""

    def add_listener(self) -> str:
        """No-op add_listener — return a stub listener ID."""
        return "null_listener"

    def remove_listener(self, listener_id: str) -> None:
        """No-op remove_listener — silently ignore."""
        return None

    def subscribe(self, service: str, pattern: str, callback_url: str = "") -> str:
        """No-op subscribe — silently ignore registration, return stub ID."""
        return "null_sub"

    def subscribe_async(self, service: str, pattern: str, callback_url: str = "") -> str:
        """No-op async subscribe — silently ignore, return stub ID."""
        return "null_sub"

    def unsubscribe(self, sub_id: str) -> bool:
        """No-op unsubscribe — return False."""
        return False


# Singleton instance reused across all no-op references to minimise allocations.
_NULL_BUS = _NullEventBus()


def get_event_bus() -> Any:
    """Return the global EventBus, or a no-op dummy if unavailable.

    This is a convenience wrapper around :func:`get_global_event_bus` that
    never returns ``None`` — callers can safely call ``.publish()`` or
    ``.subscribe()`` on the result without an explicit guard.

    Returns:
        The registered global EventBus instance, or a :class:`_NullEventBus`
        singleton if no bus has been registered.
    """
    bus = get_global_event_bus()
    if bus is None:
        return _NULL_BUS
    return bus


__all__ = [
    "BOSEvent",
    "BosEvent",
    "EventBusProtocol",
    "EventType",
    "make_event",
    "register_global_event_bus",
    "get_global_event_bus",
    "get_event_bus",
]
