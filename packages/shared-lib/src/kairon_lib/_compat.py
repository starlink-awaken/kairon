"""
_compat.py — Compatibility stubs for types migrated from SharedBrain/nucleus.

These are placeholder definitions for types that were originally imported
from nucleus.Z_*. Each should eventually be replaced with a proper
implementation or import once the migration is complete.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any, Protocol


@contextmanager
def managed_connection(conn: sqlite3.Connection) -> Generator[sqlite3.Connection]:
    """Wrap a SQLite connection with commit/rollback/close semantics.

    Compat stub for nucleus.Z_Microkernel.utilities.sqlite_utils.managed_connection.
    """
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
