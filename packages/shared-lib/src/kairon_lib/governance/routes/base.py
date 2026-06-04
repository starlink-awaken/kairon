from __future__ import annotations

"""
Base class for governance route handlers.

Provides the ``BaseGovernanceRouter`` abstract interface that concrete
routers (approval, hive, veto, xai) extend.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseGovernanceRouter(ABC):
    """Abstract base for all governance route handlers.

    Subclasses implement ``_handler`` (or ``_initialize_handler``) to
    process incoming URIs and return structured responses.
    """

    def __init__(self) -> None:
        self.status: str = "ACTIVE"

    @abstractmethod
    async def _handler(self, uri: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Process a governance route and return a response dict."""
        ...

    async def handle(self, uri: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Public entry-point that delegates to ``_handler``."""
        return await self._handler(uri, params)

    def to_dict(self) -> dict[str, Any]:
        """Return a diagnostic summary of this router."""
        return {
            "type": type(self).__name__,
            "status": self.status,
        }
