"""Extension system — plugin registry, adapter discovery, lifecycle management."""

import time
from dataclasses import dataclass, field
from enum import StrEnum


class ExtensionState(StrEnum):
    REGISTERED = "registered"
    LOADING = "loading"
    ACTIVE = "active"
    DISABLED = "disabled"
    FAILED = "failed"

@dataclass
class ExtensionDef:
    name: str
    version: str = "1.0.0"
    description: str = ""
    entry_point: str = ""
    capabilities: list[str] = field(default_factory=list)
    state: ExtensionState = ExtensionState.REGISTERED
    registered_at: float = field(default_factory=time.time)

class ExtensionRegistry:
    """Register, discover, and manage extensions/plugins."""

    def __init__(self):
        self._extensions: dict[str, ExtensionDef] = {}  # type: ignore[annotation-unchecked]

    def register(self, name: str, version: str = "1.0.0", capabilities: list[str] | None = None,
                 entry_point: str = "") -> str:
        ext = ExtensionDef(name=name, version=version, capabilities=capabilities or [],
                           entry_point=entry_point)
        self._extensions[name] = ext
        return name

    def activate(self, name: str) -> bool:
        ext = self._extensions.get(name)
        if ext and ext.state in (ExtensionState.REGISTERED, ExtensionState.DISABLED):
            ext.state = ExtensionState.ACTIVE
            return True
        return False

    def disable(self, name: str) -> bool:
        ext = self._extensions.get(name)
        if ext:
            ext.state = ExtensionState.DISABLED
            return True
        return False

    def find_by_capability(self, capability: str) -> list[ExtensionDef]:
        return [e for e in self._extensions.values()
                if capability in e.capabilities and e.state == ExtensionState.ACTIVE]

    def list_active(self) -> list[ExtensionDef]:
        return [e for e in self._extensions.values() if e.state == ExtensionState.ACTIVE]

    def get(self, name: str) -> ExtensionDef | None:
        return self._extensions.get(name)

    def deregister(self, name: str) -> bool:
        return self._extensions.pop(name, None) is not None
