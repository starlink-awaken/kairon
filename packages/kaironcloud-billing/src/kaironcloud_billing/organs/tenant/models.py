"""Tenant resource quota models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ResourceQuota:
    """Resource quota for a tenant."""

    tenant_id: str = ""
    max_workers: int = 10
    max_concurrent_tasks: int = 5
    max_compute_hours: float = 100.0
    max_storage_gb: float = 50.0
    max_requests_per_min: int = 1000
