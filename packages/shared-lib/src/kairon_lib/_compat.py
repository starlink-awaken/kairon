"""
_compat.py — Compatibility stubs for types migrated from SharedBrain/nucleus.

These are placeholder definitions for types that were originally imported
from nucleus.Z_*. Each should eventually be replaced with a proper
implementation or import once the migration is complete.

managed_connection is re-exported from kairon-utils (previously defined here).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

# Re-export from kairon-utils for backward compatibility
from kairon_utils.sqlite_utils import managed_connection  # noqa: F401


class Router:
    """Stub for nucleus.Z_Microkernel.organs.uri_router.Router."""

    @classmethod
    async def call(cls, _uri: str, _payload: Any = None) -> dict[str, Any]:
        return {"status": "success", "data": None}


# ── traced decorator stubs ────────────────────────────────────────────────


class _TraceContextProtocol(Protocol):
    def add_span(self, name: str, **metadata: Any) -> Any: ...
    def finish_span(self, span: Any) -> None: ...


def get_current_trace() -> _TraceContextProtocol | None:
    return None


def start_trace(name: str = "root") -> _TraceContextProtocol | None:
    return None


def traced(
    _func: Callable[..., Any] | None = None,
    *,
    domain: str = "",
) -> Any:
    if _func is not None:
        return _func

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    return decorator
