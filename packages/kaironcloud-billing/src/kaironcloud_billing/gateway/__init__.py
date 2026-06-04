"""Gateway package — auth, types, and gateway server classes."""

from __future__ import annotations

from kaironcloud_billing.gateway.auth import JWTAuth
from kaironcloud_billing.gateway.types import AuthResult, Request

# Re-export from legacy gateway_main module for backward compatibility
from kaironcloud_billing.gateway_main import Gateway, GatewayRequest, GatewayResponse, GatewayRoute  # noqa: F401

__all__ = [
    "AuthResult",
    "Gateway",
    "GatewayRequest",
    "GatewayResponse",
    "GatewayRoute",
    "JWTAuth",
    "Request",
]
