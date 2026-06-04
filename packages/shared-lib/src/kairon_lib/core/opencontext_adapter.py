"""OpenContext adapter — Open Context integration (toolkit memory/adapters/OpenContextAdapter.ts)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextItem:
    id: str; content: str; source: str; metadata: dict[str, Any] = field(default_factory=dict)  # noqa: E702


class OpenContextAdapter:
    """Integrate with Open Context protocol for shared memory."""

    def __init__(self) -> None:
        self._items: dict[str, ContextItem] = {}

    def publish(self, item: ContextItem) -> None:
        self._items[item.id] = item

    def fetch(self, context_id: str) -> ContextItem | None:
        return self._items.get(context_id)

    def search(self, source: str) -> list[ContextItem]:
        return [i for i in self._items.values() if i.source == source]
