"""Tenant manager — manages tenant lifecycle and lookup."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from kaironcloud_billing.organs.tenant.models import ResourceQuota

_log = logging.getLogger(__name__)


@dataclass
class Tenant:
    """Tenant representation."""

    tenant_id: str
    name: str = ""
    is_active: bool = True
    quota: ResourceQuota = field(default_factory=ResourceQuota)


class TenantManager:
    """Manages tenant lifecycle, lookup, and caching."""

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the tenant manager."""
        if self._initialized:
            return
        self._initialized = True
        _log.info("✅ [TenantManager] Initialized")

    async def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by ID.

        Args:
            tenant_id: The tenant ID to look up.

        Returns:
            Tenant if found, None otherwise.
        """
        return self._tenants.get(tenant_id)

    async def register_tenant(self, tenant: Tenant) -> None:
        """Register a new tenant.

        Args:
            tenant: The tenant to register.
        """
        self._tenants[tenant.tenant_id] = tenant
        _log.info("Registered tenant: %s", tenant.tenant_id)
