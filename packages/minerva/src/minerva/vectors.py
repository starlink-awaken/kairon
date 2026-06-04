"""Vector store abstraction — extracted from SharedBrain D_Memory vector_backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class VectorSearchResult:
    id: str
    score: float
    metadata: dict[str, Any] | None = None


class VectorStoreBackend(ABC):
    @abstractmethod
    def add(self, vectors: list[list[float]], ids: list[str], metadata: list[dict] | None = None) -> None: ...
    @abstractmethod
    def search(self, query: list[float], top_k: int = 10) -> list[VectorSearchResult]: ...
    @abstractmethod
    def get(self, id: str) -> dict | None: ...
    @abstractmethod
    def remove(self, id: str) -> None: ...
    @abstractmethod
    def count(self) -> int: ...


class VectorStoreFactory:
    _backends: dict[str, type[VectorStoreBackend]] = {}

    @classmethod
    def register(cls, name: str, backend_cls: type[VectorStoreBackend]) -> None:
        cls._backends[name] = backend_cls

    @classmethod
    def create(cls, name: str = "numpy", **kwargs: Any) -> VectorStoreBackend:
        if name not in cls._backends:
            raise ValueError(f"Unknown backend: {name}. Available: {list(cls._backends)}")
        return cls._backends[name](**kwargs)
