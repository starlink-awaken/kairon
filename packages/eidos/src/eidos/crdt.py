"""CRDT primitives — extracted from SharedBrain D_Continuity and D_Memory."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class VectorClock:
    node_id: str
    counter: int = 0

    def increment(self) -> int:
        self.counter += 1
        return self.counter

    def merge(self, other: VectorClock) -> None:
        if self.node_id == other.node_id:
            self.counter = max(self.counter, other.counter)

    def to_dict(self) -> dict[str, int]:
        return {self.node_id: self.counter}

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> list[VectorClock]:
        return [cls(node_id=k, counter=v) for k, v in data.items()]


class LWWRegister:
    def __init__(self, value: Any = None, timestamp: float | None = None) -> None:
        self.value = value
        self.timestamp = timestamp or time.time()

    def set(self, value: Any, timestamp: float | None = None) -> None:
        ts = timestamp or time.time()
        if ts >= self.timestamp:
            self.value = value
            self.timestamp = ts

    def get(self) -> Any:
        return self.value


class ORSet:
    def __init__(self) -> None:
        self._elements: dict[str, set[str]] = {}  # element -> {tag_ids}

    def add(self, element: str, tag: str | None = None) -> None:
        tag = tag or f"{element}-{time.time()}"
        if element not in self._elements:
            self._elements[element] = set()
        self._elements[element].add(tag)

    def remove(self, element: str) -> None:
        if element in self._elements:
            del self._elements[element]

    def contains(self, element: str) -> bool:
        return element in self._elements and len(self._elements[element]) > 0

    def items(self) -> set[str]:
        return {e for e, tags in self._elements.items() if tags}

    def merge(self, other: ORSet) -> None:
        for element, tags in other._elements.items():
            if element not in self._elements:
                self._elements[element] = set()
            self._elements[element] |= tags
