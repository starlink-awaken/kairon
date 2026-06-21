"""Eidos data models — shared data classes for the D-Memory subsystem.

TODO: expand with additional model types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Lesson:
    """A lesson learned — captured insight with context and applicability."""

    id: str = ""
    title: str = ""
    content: str = ""
    context: str = ""
    source: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ttl: int = 86400
    metadata: dict[str, Any] = field(default_factory=dict)
    lesson_id: str = ""
    access_count: int = 0
    query: str = ""
    failure_pattern: dict[str, Any] = field(default_factory=dict)
    solution: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "context": self.context,
            "source": self.source,
            "tags": self.tags,
            "created_at": self.created_at,
            "ttl": self.ttl,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Lesson:
        return cls(
            id=d["id"],
            title=d["title"],
            content=d["content"],
            context=d.get("context", ""),
            source=d.get("source", ""),
            tags=d.get("tags", []),
            created_at=d.get("created_at", datetime.utcnow().isoformat()),
            ttl=d.get("ttl", 86400),
            metadata=d.get("metadata", {}),
        )


__all__ = [
    "Lesson",
]
