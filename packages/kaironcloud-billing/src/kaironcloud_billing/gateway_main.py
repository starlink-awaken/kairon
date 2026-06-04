from __future__ import annotations

"""
---
Type: Organ | Status: ACTIVE | Layer: L3 | Domain: D-Cloud
Summary: Cloud API Gateway -- routing, httpx forwarding, error handling.
Source: SharedBrain D_Cloud/organs/gateway/server.py, router.py, types.py
---
"""
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

_log = logging.getLogger(__name__)

__all__ = ["GatewayRoute", "GatewayRequest", "GatewayResponse", "Gateway"]


@dataclass
class GatewayRequest:
    """Normalised inbound request."""

    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    client_ip: str = ""


@dataclass
class GatewayResponse:
    """Normalised outbound response."""

    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def json(cls, data: dict[str, Any], status: int = 200) -> GatewayResponse:
        return cls(
            status=status,
            body=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

    @classmethod
    def error(cls, message: str, status: int = 400, code: str = "") -> GatewayResponse:
        payload: dict[str, Any] = {"error": message, "status": status}
        if code:
            payload["code"] = code
        return cls.json(payload, status)


@dataclass
class GatewayRoute:
    """A single route mapping.

    Attributes:
        path: URL path prefix (e.g. ``/api/v1/execute``).
        service_url: Target backend URL (e.g. ``http://localhost:8081``).
        methods: Allowed HTTP methods (default all).
        auth_required: Whether JWT authentication is needed.
    """

    path: str
    service_url: str
    methods: list[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    auth_required: bool = True


class Gateway:
    """Cloud API Gateway.

    Maintains a route table and forwards matching requests to backend
    services via **httpx**. Supports path-based routing with method
    filtering, structured error responses, and request-id tracking.
    """

    def __init__(self) -> None:
        self._routes: list[GatewayRoute] = []
        self._client: httpx.AsyncClient | None = None

    def add_route(
        self,
        path: str,
        service_url: str,
        methods: list[str] | None = None,
        auth_required: bool = True,
    ) -> GatewayRoute:
        """Register a new route. Returns the created GatewayRoute."""
        route = GatewayRoute(
            path=path,
            service_url=service_url.rstrip("/"),
            methods=methods or ["GET", "POST", "PUT", "DELETE"],
            auth_required=auth_required,
        )
        self._routes.append(route)
        _log.info("Added route: %s -> %s", path, service_url)
        return route

    def remove_route(self, path: str, service_url: str | None = None) -> bool:
        """Remove matching routes. Returns True if any was removed."""
        before = len(self._routes)
        self._routes = [
            r
            for r in self._routes
            if not (r.path == path and (service_url is None or r.service_url == service_url))
        ]
        return len(self._routes) < before

    def match_route(self, method: str, path: str) -> GatewayRoute | None:
        """Find the first route matching *method* and *path* (prefix match)."""
        for route in self._routes:
            if method in route.methods and path.startswith(route.path):
                return route
        return None

    async def forward(self, request: GatewayRequest) -> GatewayResponse:
        """Match a route and forward *request* to the backend.

        Returns a GatewayResponse (success or structured error).
        """
        route = self.match_route(request.method, request.path)
        if route is None:
            return GatewayResponse.error(
                f"No route matches {request.method} {request.path}",
                status=404,
                code="route_not_found",
            )

        error_resp = self._validate(request)
        if error_resp is not None:
            return error_resp

        suffix = request.path[len(route.path):] if request.path.startswith(route.path) else request.path
        target_url = f"{route.service_url}{suffix}"

        try:
            return await self._do_forward(route, request, target_url)
        except httpx.HTTPError as exc:
            _log.error("Upstream error: %s -> %s: %s", request.path, target_url, exc)
            return GatewayResponse.error("Upstream service error", status=502, code="upstream_error")
        except (OSError, ConnectionError, TimeoutError) as exc:
            _log.error("Connection failed: %s -> %s: %s", request.path, target_url, exc)
            return GatewayResponse.error("Service unavailable", status=503, code="service_unavailable")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _do_forward(self, route: GatewayRoute, request: GatewayRequest, target_url: str) -> GatewayResponse:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        response = await self._client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.query_params,
            content=request.body,
        )
        return GatewayResponse(
            status=response.status_code,
            body=response.content,
            headers={**dict(response.headers), "X-Request-ID": str(uuid.uuid4())[:8]},
        )

    @staticmethod
    def _validate(request: GatewayRequest) -> GatewayResponse | None:
        if not request.method:
            return GatewayResponse.error("Method is required", status=400, code="bad_request")
        if not request.path or not request.path.startswith("/"):
            return GatewayResponse.error("Invalid path", status=400, code="bad_request")
        return None
