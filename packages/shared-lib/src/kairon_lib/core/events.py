"""Backward-compat module alias — re-exports from kairon_events (kairon-lib-events).

.. deprecated:: 0.5.0
    Import from ``kairon_events`` directly instead of ``kairon_lib.core.events``.
    This facade will be removed in a future version.
"""

import sys

from kairon_events import (  # noqa: F401
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

sys.modules[__name__] = sys.modules["kairon_events"]
