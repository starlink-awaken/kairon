from __future__ import annotations

"""
---
Type: Organ | Status: ACTIVE | Layer: L3 | Domain: D-Cloud
Summary: TenantManager -- CRUD and lifecycle management for tenants (in-memory).
Source: SharedBrain D_Cloud/organs/tenant/manager.py
---
"""
import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from kaironcloud_billing.tenant_models import ResourceQuota, Tenant, TenantTier

_log = logging.getLogger(__name__)

__all__ = ["TenantManager", "TenantStatus", "TenantNotFoundError", "TenantConflictError"]


class TenantStatus(StrEnum):
    """Tenant lifecycle status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISABLED = "disabled"


class TenantNotFoundError(KeyError):
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        super().__init__(f"Tenant not found: {tenant_id}")


class TenantConflictError(ValueError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Tenant already exists: {name}")


class TenantManager:
    """In-memory tenant lifecycle manager.

    Provides CRUD operations and status tracking (active/suspended/disabled)
    backed by a plain dict. No external persistence.
    """

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._status: dict[str, TenantStatus] = {}

    def create_tenant(
        self,
        name: str,
        tier: TenantTier = TenantTier.FREE,
        quota: ResourceQuota | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Tenant:
        """Register a new tenant.

        Raises:
            TenantConflictError: If the name is already taken.
        """
        if any(t.name == name for t in self._tenants.values()):
            raise TenantConflictError(name)
        tenant = Tenant.create(
            name=name,
            tier=tier,
            quota=quota or ResourceQuota.for_tier(tier),
            metadata=metadata,
        )
        self._tenants[tenant.tenant_id] = tenant
        self._status[tenant.tenant_id] = TenantStatus.ACTIVE
        _log.info("Created tenant: %s (%s)", tenant.name, tenant.tenant_id)
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Fetch a tenant by ID, or None if not found."""
        return self._tenants.get(tenant_id)

    def get_tenant_by_name(self, name: str) -> Tenant | None:
        for t in self._tenants.values():
            if t.name == name:
                return t
        return None

    def get_status(self, tenant_id: str) -> TenantStatus | None:
        """Return current lifecycle status of a tenant."""
        return self._status.get(tenant_id)

    def update_tenant(
        self,
        tenant_id: str,
        name: str | None = None,
        tier: TenantTier | None = None,
        quota: ResourceQuota | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Tenant:
        """Update tenant attributes.

        Raises:
            TenantNotFoundError: If the tenant does not exist.
        """
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id)
        if name is not None:
            tenant.name = name
        if tier is not None:
            tenant.tier = tier
            tenant.quota = quota or ResourceQuota.for_tier(tier)
        if quota is not None:
            tenant.quota = quota
        if metadata is not None:
            tenant.metadata.update(metadata)
        tenant.updated_at = datetime.now(UTC)
        return tenant

    def set_status(self, tenant_id: str, status: TenantStatus) -> None:
        """Change the lifecycle status of a tenant.

        Raises:
            TenantNotFoundError: If the tenant does not exist.
        """
        if tenant_id not in self._tenants:
            raise TenantNotFoundError(tenant_id)
        self._status[tenant_id] = status
        _log.info("Tenant %s status -> %s", tenant_id, status.value)

    def is_active(self, tenant_id: str) -> bool:
        """Check if a tenant is ACTIVE. Returns False if not found."""
        return self._status.get(tenant_id) == TenantStatus.ACTIVE

    def delete_tenant(self, tenant_id: str) -> bool:
        """Permanently remove a tenant. Returns True if removed."""
        if tenant_id not in self._tenants:
            return False
        del self._tenants[tenant_id]
        self._status.pop(tenant_id, None)
        return True

    def list_tenants(self, status: TenantStatus | None = None) -> list[Tenant]:
        tenants = list(self._tenants.values())
        if status is not None:
            tenants = [t for t in tenants if self._status.get(t.tenant_id) == status]
        return tenants

    def count(self, status: TenantStatus | None = None) -> int:
        if status is None:
            return len(self._tenants)
        return sum(1 for s in self._status.values() if s == status)
