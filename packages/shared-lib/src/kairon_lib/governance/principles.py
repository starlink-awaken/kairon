from __future__ import annotations

"""
Principles catalog — stores and retrieves governance/principles for scenario matching.

Provides the ``Principles`` class consumed by ``ScenarioEngine`` to look up
scenarios, principles, and reflective questions by query or by identifier.
"""

from typing import Any


class Principles:
    """Catalog of governance scenarios and their associated principles.

    This is a pass-through stub implementation.  TODO: wire up to the real
    principles store (YAML / DB / knowledge-graph).
    """

    def get_guidance(self, query: str) -> dict[str, Any]:
        """Return scenario + principles + questions matching *query*."""
        return {"scenario": None, "principles": [], "questions": []}

    def search(self, query: str) -> list[Any]:
        """Full-text search across all principles."""
        return []

    def get_all_scenarios(self) -> list[Any]:
        """Return every known scenario."""
        return []

    def match_scenario(self, query: str) -> Any:
        """Best-fit scenario dict (or ``None``) for *query*."""
        return None

    def get_by_id(self, id_: int) -> Any:
        """Look up a single principle by its numeric *id_*."""
        return None

    def get_all(self) -> list[Any]:
        """Return every principle in the catalog."""
        return []

    def get_by_level(self, level: str) -> list[Any]:
        """Return principles filtered by governance *level* (e.g. ``"L1"``)."""
        return []
