"""OntoDerive Engine protocols — formal interfaces for toolforge and engine components."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ToolForgeInterface(Protocol):
    """Protocol for tool forge matching engines."""

    def match(self, goal: str, context: str = "") -> list[dict[str, Any]]:
        """Match tools against a goal and context string."""
        ...


__all__ = [
    "ToolForgeInterface",
]
