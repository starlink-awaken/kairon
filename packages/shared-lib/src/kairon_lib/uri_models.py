"""URI registration models — extracted from SharedBrain D_Continuity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class UriResource:
    uri: str
    resource_type: str
    handler: str = ""
    metadata: dict[str, Any] | None = None
    ttl_seconds: int = 3600

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def is_expired(self) -> bool:
        return False  # TODO: implement TTL check

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "resource_type": self.resource_type,
            "handler": self.handler,
            "ttl_seconds": self.ttl_seconds,
        }


@dataclass
class UriRegistry:
    resources: dict[str, UriResource] | None = None

    def __post_init__(self):
        if self.resources is None:
            self.resources = {}

    def register(self, resource: UriResource) -> None:
        assert self.resources is not None
        self.resources[resource.uri] = resource

    def resolve(self, uri: str) -> UriResource | None:
        assert self.resources is not None
        return self.resources.get(uri)

    @property
    def count(self) -> int:
        assert self.resources is not None
        return len(self.resources)
