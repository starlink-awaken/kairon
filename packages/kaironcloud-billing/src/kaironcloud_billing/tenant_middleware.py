from __future__ import annotations

"""
---
Type: Organ | Status: ACTIVE | Layer: L3 | Domain: D-Cloud
Summary: TenantMiddleware -- extracts and validates tenant context from requests.
Source: SharedBrain D_Cloud/organs/tenant/middleware.py
---
"""
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from kaironcloud_billing.tenant_manager import TenantManager
from kaironcloud_billing.tenant_models import Tenant

_log = logging.getLogger(__name__)

__all__ = ["TenantContext", "TenantMiddleware", "RequestProtocol", "TenantNotFoundError", "TenantInactiveError"]


class TenantNotFoundError(ValueError):
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        super().__init__(f"Tenant not found: {tenant_id}")


class TenantInactiveError(PermissionError):
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        super().__init__(f"Tenant is not active: {tenant_id}")


class RequestProtocol(Protocol):
    """Structural protocol for request objects (FastAPI, Starlette, aiohttp, etc.)."""

    @property
    def headers(self) -> dict[str, str] | Any: ...


@dataclass
class TenantContext:
    """Tenant context attached to a processed request."""

    tenant_id: str
    tenant: Tenant
    request_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "tenant_name": self.tenant.name,
            "tenant_tier": self.tenant.tier.value,
            "request_id": self.request_id,
            "metadata": self.metadata,
        }


class TenantMiddleware:
    """Extract and validate tenant identity from incoming requests.

    Strategies tried in order: ``X-Tenant-ID`` header -> ``tenant_id`` query param
    -> ``X-API-Key`` header (mapped to tenant ID).

    Attributes:
        require_tenant: If True, requests without a tenant ID raise ValueError.
    """

    HEADER_NAME = "X-Tenant-ID"
    QUERY_PARAM = "tenant_id"
    API_KEY_HEADER = "X-API-Key"

    def __init__(
        self,
        tenant_manager: TenantManager | None = None,
        header_name: str = HEADER_NAME,
        query_param: str = QUERY_PARAM,
        api_key_header: str = API_KEY_HEADER,
        require_tenant: bool = True,
    ) -> None:
        self._tm = tenant_manager or TenantManager()
        self._header_name = header_name
        self._query_param = query_param
        self._api_key_header = api_key_header
        self._require_tenant = require_tenant
        self._api_key_map: dict[str, str] = {}

    def extract_tenant_id(self, request: Any) -> str | None:
        """Extract tenant ID from *request* via header, query param, or API key."""
        tid = self._get_header(request, self._header_name)
        if tid:
            return tid
        tid = self._get_query_param(request, self._query_param)
        if tid:
            return tid
        api_key = self._get_header(request, self._api_key_header)
        if api_key and api_key in self._api_key_map:
            return self._api_key_map[api_key]
        return None

    def validate_tenant(self, tenant_id: str) -> Tenant:
        """Check tenant exists and is active.

        Raises:
            TenantNotFoundError
            TenantInactiveError
        """
        tenant = self._tm.get_tenant(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id)
        if not self._tm.is_active(tenant_id):
            raise TenantInactiveError(tenant_id)
        return tenant

    def process_request(self, request: Any, request_id: str | None = None) -> TenantContext:
        """Extract -> validate -> build context.

        Raises:
            ValueError: If *require_tenant* is True and no tenant ID found.
            TenantNotFoundError
            TenantInactiveError
        """
        tenant_id = self.extract_tenant_id(request)
        if tenant_id is None:
            if self._require_tenant:
                raise ValueError("Tenant ID is required but not found in request")
            return TenantContext(
                tenant_id="anonymous",
                tenant=Tenant.create(name="anonymous"),
                request_id=request_id or str(uuid.uuid4()),
            )
        tenant = self.validate_tenant(tenant_id)
        return TenantContext(
            tenant_id=tenant_id,
            tenant=tenant,
            request_id=request_id or str(uuid.uuid4()),
            metadata={"extracted_from": self._extraction_source(request, tenant_id)},
        )

    def register_api_key(self, api_key: str, tenant_id: str) -> None:
        """Map *api_key* to *tenant_id*."""
        self._api_key_map[api_key] = tenant_id

    def unregister_api_key(self, api_key: str) -> None:
        self._api_key_map.pop(api_key, None)

    @staticmethod
    def _get_header(request: Any, name: str) -> str | None:
        headers = getattr(request, "headers", None)
        if headers is None:
            return None
        if isinstance(headers, dict):
            return headers.get(name) or headers.get(name.lower())
        return headers.get(name) or headers.get(name.lower())

    @staticmethod
    def _get_query_param(request: Any, name: str) -> str | None:
        params = getattr(request, "query_params", None)
        if params:
            return params.get(name)
        args = getattr(request, "args", None)
        if args:
            return args.get(name)
        return None

    def _extraction_source(self, request: Any, tenant_id: str) -> str:
        if self._get_header(request, self._header_name) == tenant_id:
            return f"header:{self._header_name}"
        if self._get_query_param(request, self._query_param) == tenant_id:
            return f"query:{self._query_param}"
        return "api_key"
