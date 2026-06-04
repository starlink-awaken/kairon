"""Kairon shared library - common utilities and base models."""

__version__ = "0.4.0"

# Backward-compat re-exports
from kairon_lib.events import (  # noqa: F401
    BOSEvent,
    BosEvent,
    EventBusProtocol,
    EventType,
    get_event_bus,
    get_global_event_bus,
    make_event,
    register_global_event_bus,
)



