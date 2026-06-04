from __future__ import annotations

"""Telos entity lifecycle — TCF (Trigger-Condition-Force) state machine.

Migrated from agentmesh/packages/toolkit/src/lifecycle/.

This complements the existing kairon_lib.lifecycle module (RFC governance)
by providing a generic entity lifecycle manager.
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class EntityState:
    current: str = "initialized"
    previous: str | None = None
    timestamp: float = 0.0


@dataclass
class EntityEvent:
    type: str = ""
    timestamp: float = 0.0
    data: Any = None
    actor: str | None = None


# Predefined states and actions
INITIALIZED = "initialized"
ACTIVE = "active"
INACTIVE = "inactive"
ARCHIVED = "archived"
DELETED = "deleted"

ACTION_TRIGGERS: dict[str, str] = {
    "activate": ACTIVE,
    "deactivate": INACTIVE,
    "archive": ARCHIVED,
    "delete": DELETED,
    "restore": ACTIVE,
}

DEFAULT_TRANSITIONS: dict[str, list[str]] = {
    "*": [INITIALIZED, ACTIVE, INACTIVE, ARCHIVED, DELETED],
}


# ---------------------------------------------------------------------------
# TelosContext
# ---------------------------------------------------------------------------

class TelosContext:
    """Entity lifecycle manager using the TCF (Trigger-Condition-Force) model.

    Tracks state transitions, attribute changes, and event history.
    """

    def __init__(
        self,
        entity_id: str | None = None,
        attributes: dict[str, Any] | None = None,
        entity_type: str = "default",
    ) -> None:
        self._id = entity_id or f"ent-{uuid.uuid4().hex[:8]}"
        self._type = entity_type
        self._attributes: dict[str, Any] = dict(attributes or {})
        self._state = EntityState(current=INITIALIZED, timestamp=time.time())
        self._history: list[EntityEvent] = []
        self._transitions: dict[str, list[str]] = dict(DEFAULT_TRANSITIONS)
        self._record_event("created", {"attributes": self._attributes})

    # -- Accessors --

    @property
    def id(self) -> str:
        return self._id

    @property
    def type(self) -> str:
        return self._type

    @property
    def state(self) -> EntityState:
        return EntityState(**self._state.__dict__)

    @property
    def attributes(self) -> dict[str, Any]:
        return dict(self._attributes)

    def get_attribute(self, key: str) -> Any:
        return self._attributes.get(key)

    def set_attribute(self, key: str, value: Any) -> None:
        old = self._attributes.get(key)
        self._attributes[key] = value
        self._record_event("attribute_changed", {"key": key, "old_value": old, "new_value": value})

    def set_attributes(self, attrs: dict[str, Any]) -> None:
        for k, v in attrs.items():
            self.set_attribute(k, v)

    def get_history(self) -> list[EntityEvent]:
        return list(self._history)

    def get_history_by_type(self, event_type: str) -> list[EntityEvent]:
        return [e for e in self._history if e.type == event_type]

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self._id,
            "type": self._type,
            "attributes": self._attributes,
            "state": self._state.__dict__,
            "history": [e.__dict__ for e in self._history],
        }

    # -- State management --

    def can_transition_to(self, target: str) -> bool:
        current = self._state.current
        allowed = self._transitions.get(current, []) + self._transitions.get("*", [])
        return target in allowed

    def transition(self, target: str) -> bool:
        if not self.can_transition_to(target):
            msg = f"State transition not allowed: {self._state.current} -> {target}"
            raise ValueError(msg)
        old = self._state.current
        self._state = EntityState(current=target, previous=old, timestamp=time.time())
        self._record_event("state_changed", {"from": old, "to": target})
        return True

    def apply(self, action: str) -> None:
        self._record_event("action", {"action": action})
        target = ACTION_TRIGGERS.get(action)
        if target and self.can_transition_to(target):
            self.transition(target)

    def is_active(self) -> bool:
        return self._state.current == ACTIVE

    # -- TCF model --

    def check_trigger(self, trigger: str) -> bool:
        self._record_event("trigger_checked", {"trigger": trigger})
        return True

    def evaluate(self, trigger: str, condition: Callable[[TelosContext], bool]) -> bool:
        try:
            return condition(self)
        except Exception:
            self._record_event("condition_error", {"trigger": trigger})
            return False

    # -- Internal --

    def _record_event(self, event_type: str, data: Any = None) -> None:
        self._history.append(EntityEvent(type=event_type, timestamp=time.time(), data=data))

    def add_transition_rule(self, from_state: str, to_states: list[str]) -> None:
        self._transitions[from_state] = to_states
