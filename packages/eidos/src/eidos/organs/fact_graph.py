"""Fact graph organ — in-memory fact graph with simple query interface.

TODO: implement full fact graph with SQLite persistence.
"""

from __future__ import annotations

from typing import Any

from ..fact_graph import FactGraph  # noqa: F401


def get_graph() -> FactGraph:
    """Return the singleton FactGraph instance."""
    return get_fact_graph()


__all__ = [
    "FactGraph",
    "get_graph",
    "get_fact_graph",
]
