"""Middleware modules for agentmesh gateway migration.

Provides API key authentication and request logging middleware.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agora.types import AgentMessage  # type: ignore[import-not-found]


class APIKeyAuthMiddleware:
    """API key authentication middleware.

    Checks X-API-Key header against the configured API_KEY.
    Skips auth for health check endpoints.
    """

    def __init__(self, api_key: str | None = None, skip_paths: set[str] | None = None) -> None:
        self._api_key = api_key or os.environ.get("API_KEY", "")
        self._skip_paths = skip_paths or {"/health", "/healthz"}
        env_skip = os.environ.get("API_KEY_SKIP_PATHS", "")
        if env_skip:
            self._skip_paths.update(p.strip() for p in env_skip.split(",") if p.strip())

    @property
    def is_configured(self) -> bool:
        """Whether an API key is set."""
        return bool(self._api_key)

    def authenticate(self, request_path: str, headers: dict[str, str]) -> str | None:
        """Authenticate a request.

        Returns None if authorized, or an error message string if denied.
        """
        if not self._api_key:
            return "Service not configured: missing API_KEY"
        if request_path in self._skip_paths:
            return None
        provided = headers.get("x-api-key") or headers.get("X-Api-Key") or ""
        if provided != self._api_key:
            return "Unauthorized: missing or invalid API key"
        return None


class LoggingMiddleware:
    """Request/response logging middleware."""

    def __init__(self, logger: Any | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    async def on_request(self, message: AgentMessage) -> AgentMessage:
        """Log incoming request."""
        self._logger.info(
            "Request: source=%s target=%s type=%s",
            message.source,
            message.target,
            message.type,
        )
        return message

    async def on_response(self, message: AgentMessage) -> AgentMessage:
        """Log outgoing response."""
        status = "ok" if message.error is None else f"error:{message.error.code}"
        self._logger.info(
            "Response: source=%s target=%s status=%s",
            message.source,
            message.target,
            status,
        )
        return message
