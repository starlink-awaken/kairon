from __future__ import annotations

"""Plugin system — dynamic module loading with lazy resolution.

Migrated from agentmesh/packages/toolkit/src/plugin/.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol
from collections.abc import Callable

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class PluginManifest:
    name: str
    version: str
    description: str = ""


class Plugin(Protocol):
    name: str
    version: str
    description: str | None = None

    def register(self) -> dict[str, Any]:
        """Return a registration dict of module loaders."""
        ...


@dataclass
class LazyModule:
    """A lazily-loaded module reference."""

    loader: Callable[[], Any]
    _instance: Any = field(default=None, repr=False)
    _loaded: bool = field(default=False, repr=False)

    def load(self) -> Any:
        if not self._loaded:
            self._instance = self.loader()
            self._loaded = True
        return self._instance

    def is_loaded(self) -> bool:
        return self._loaded

    def get(self) -> Any | None:
        return self._instance if self._loaded else None


# ---------------------------------------------------------------------------
# Plugin Registry
# ---------------------------------------------------------------------------

class PluginRegistry:
    """Registry of plugins that supports lazy module loading."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._modules: dict[str, LazyModule] = {}
        self._debug = False

    def enable_debug(self, enabled: bool = True) -> None:
        self._debug = enabled

    def register_plugin(self, plugin: Plugin) -> None:
        self._plugins[plugin.name] = plugin
        registration = plugin.register()
        for name, loader in registration.items():
            self._modules[name] = LazyModule(loader)

    def get_plugin(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    def load_module(self, name: str) -> Any:
        lazy = self._modules.get(name)
        if lazy is None:
            raise KeyError(f"Module {name!r} not registered")
        if self._debug:
            print(f"[PluginRegistry] Loading module: {name}")
        return lazy.load()

    def list_modules(self) -> list[str]:
        return list(self._modules.keys())

    def list_plugins(self) -> list[Plugin]:
        return list(self._plugins.values())

    def is_loaded(self, name: str) -> bool:
        lazy = self._modules.get(name)
        return lazy.is_loaded() if lazy else False


# ---------------------------------------------------------------------------
# Default implementations
# ---------------------------------------------------------------------------

DEFAULT_PLUGIN_REGISTRY = PluginRegistry()


def get_default_registry() -> PluginRegistry:
    return DEFAULT_PLUGIN_REGISTRY


def reset_default_registry() -> None:
    DEFAULT_PLUGIN_REGISTRY._plugins.clear()
    DEFAULT_PLUGIN_REGISTRY._modules.clear()
