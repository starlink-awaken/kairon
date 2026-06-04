"""Gateway types — AuthResult and Request used across gateway modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuthResult:
    """Result of an authentication attempt."""

    success: bool
    tenant_id: str | None = None
    user_id: str | None = None
    email: str | None = None
    roles: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    claims: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class Request:
    """Minimal HTTP request representation for gateway auth."""

    method: str = "GET"
    path: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    query_params: dict[str, str] = field(default_factory=dict)

    def get_header(self, name: str, default: str = "") -> str:
        return self.headers.get(name, default)
