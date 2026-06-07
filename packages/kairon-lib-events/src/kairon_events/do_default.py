"""P58-W0 kairon_events do_default — 真业务 (调 kairon_events EventBus 真模块)."""
from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 kairon_events do_default: 真调 make_event / get_event_bus / register."""
    try:
        from kairon_events import (
            EventType,
            get_event_bus,
            make_event,
        )
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "make")
    try:
        if action == "make":
            event = make_event(
                event_type=args.get("event_type", "test.ping"),
                source=args.get("source", "kairon_events.do_default"),
                payload=args.get("payload", {"k": "v"}),
            )
            return {
                "_method": "do_default", "_action": "make",
                "event_id": event.event_id,
                "event_type": event.event_type,
                "source": event.source,
                "has_timestamp": bool(event.timestamp),
            }
        if action == "bus_status":
            bus = get_event_bus()
            return {
                "_method": "do_default", "_action": "bus_status",
                "bus_type": type(bus).__name__,
                "is_null": bus.__class__.__name__ == "_NullEventBus",
            }
        if action == "event_types":
            return {
                "_method": "do_default", "_action": "event_types",
                "types": [et.value for et in EventType],
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
