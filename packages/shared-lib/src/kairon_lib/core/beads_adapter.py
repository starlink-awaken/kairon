"""Beads adapter — beads-based memory storage (toolkit memory/adapters/BeadsAdapter.ts)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Bead:
    id: str; content: str; tags: list[str] = field(default_factory=list)  # noqa: E702
    metadata: dict[str, Any] = field(default_factory=dict)


class BeadsAdapter:
    """Store and retrieve memory as discrete 'beads'."""

    def __init__(self) -> None:
        self._beads: dict[str, Bead] = {}

    def add(self, bead: Bead) -> None:
        self._beads[bead.id] = bead

    def get(self, bead_id: str) -> Bead | None:
        return self._beads.get(bead_id)

    def search(self, query: str) -> list[Bead]:
        q = query.lower()
        return [b for b in self._beads.values() if q in b.content.lower() or any(q in t.lower() for t in b.tags)]

    def delete(self, bead_id: str) -> bool:
        return self._beads.pop(bead_id, None) is not None

    def list(self, tag: str | None = None) -> list[Bead]:
        if tag is None: return list(self._beads.values())  # noqa: E701
        return [b for b in self._beads.values() if tag in b.tags]

    @property
    def count(self) -> int:
        return len(self._beads)
