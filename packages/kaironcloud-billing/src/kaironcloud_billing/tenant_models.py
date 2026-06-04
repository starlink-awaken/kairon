from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: "@CloudArchitect"
Layer: L3
Domain: D-Cloud
Summary: "Tenant data models — Tenant, ResourceQuota, TenantTier definitions."
Source: SharedBrain D_Cloud/organs/tenant/models.py
Migrated: Wave 2 → kairon kaironcloud-billing
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Tenant_Models ≡ Module
# 内涵 ≝ {Tenant, ResourceQuota, TenantTier}
# 外延 ≝ {e | e ∈ D-Cloud ∧ defines(e, Tenant_Models)}
# 功能 ⊢ {Tenant_Data_Structure, Resource_Quota_Definition, Tier_Management}
# =============================================================================
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class TenantTier(Enum):
    """租户层级定义

    - FREE: 免费层，基础资源限制
    - PRO: 专业层，提升的资源限制
    - ENTERPRISE: 企业层，高级资源限制和专属支持
    """

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class ResourceQuota:
    """资源配额定义

    定义租户可以使用的各种资源的上限。

    Attributes:
        max_workers: 最大工作线程数
        max_requests_per_min: 每分钟最大请求数
        max_storage_gb: 最大存储空间(GB)
        max_compute_hours: 每月最大计算小时数
        max_concurrent_tasks: 最大并发任务数
        max_api_keys: 最大API密钥数
    """

    max_workers: int = 5
    max_requests_per_min: int = 100
    max_storage_gb: float = 1.0
    max_compute_hours: int = 100
    max_concurrent_tasks: int = 3
    max_api_keys: int = 2

    def to_dict(self) -> dict[str, Any]:
        """将配额转换为字典"""
        return {
            "max_workers": self.max_workers,
            "max_requests_per_min": self.max_requests_per_min,
            "max_storage_gb": self.max_storage_gb,
            "max_compute_hours": self.max_compute_hours,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "max_api_keys": self.max_api_keys,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceQuota:
        """从字典创建配额"""
        return cls(
            max_workers=data.get("max_workers", 5),
            max_requests_per_min=data.get("max_requests_per_min", 100),
            max_storage_gb=data.get("max_storage_gb", 1.0),
            max_compute_hours=data.get("max_compute_hours", 100),
            max_concurrent_tasks=data.get("max_concurrent_tasks", 3),
            max_api_keys=data.get("max_api_keys", 2),
        )

    @classmethod
    def for_tier(cls, tier: TenantTier) -> ResourceQuota:
        """根据层级获取默认配额

        Args:
            tier: 租户层级

        Returns:
            对应层级的默认资源配额
        """
        quotas = {
            TenantTier.FREE: cls(
                max_workers=5,
                max_requests_per_min=100,
                max_storage_gb=1.0,
                max_compute_hours=100,
                max_concurrent_tasks=3,
                max_api_keys=2,
            ),
            TenantTier.PRO: cls(
                max_workers=20,
                max_requests_per_min=1000,
                max_storage_gb=10.0,
                max_compute_hours=1000,
                max_concurrent_tasks=10,
                max_api_keys=10,
            ),
            TenantTier.ENTERPRISE: cls(
                max_workers=100,
                max_requests_per_min=10000,
                max_storage_gb=100.0,
                max_compute_hours=10000,
                max_concurrent_tasks=50,
                max_api_keys=100,
            ),
        }
        return quotas.get(tier, cls())


@dataclass
class Tenant:
    """租户实体

    B-OS Cloud 中的多租户基本单位。

    Attributes:
        tenant_id: 唯一租户标识符(UUID)
        name: 租户名称
        tier: 租户层级
        quota: 资源配额
        created_at: 创建时间
        updated_at: 最后更新时间
        is_active: 是否激活
        metadata: 扩展元数据
    """

    tenant_id: str
    name: str
    tier: TenantTier
    quota: ResourceQuota
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """初始化后处理"""
        if isinstance(self.tier, str):
            self.tier = TenantTier(self.tier)
        if isinstance(self.quota, dict):
            self.quota = ResourceQuota.from_dict(self.quota)

    def to_dict(self) -> dict[str, Any]:
        """将租户转换为字典"""
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "tier": self.tier.value,
            "quota": self.quota.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Tenant:
        """从字典创建租户

        Args:
            data: 租户数据字典

        Returns:
            Tenant实例
        """
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(UTC)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.now(UTC)

        tier = data.get("tier", "free")
        if isinstance(tier, str):
            tier = TenantTier(tier)

        quota_data = data.get("quota", {})
        if isinstance(quota_data, dict):
            quota = ResourceQuota.from_dict(quota_data)
        else:
            quota = ResourceQuota.for_tier(tier)

        return cls(
            tenant_id=data.get("tenant_id", str(uuid.uuid4())),
            name=data.get("name", "unnamed"),
            tier=tier,
            quota=quota,
            created_at=created_at,
            updated_at=updated_at,
            is_active=data.get("is_active", True),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def create(
        cls,
        name: str,
        tier: TenantTier = TenantTier.FREE,
        quota: ResourceQuota | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Tenant:
        """创建新租户

        Args:
            name: 租户名称
            tier: 租户层级，默认为FREE
            quota: 自定义配额，如不提供则使用层级默认配额
            metadata: 扩展元数据

        Returns:
            新创建的Tenant实例
        """
        if quota is None:
            quota = ResourceQuota.for_tier(tier)

        return cls(
            tenant_id=str(uuid.uuid4()),
            name=name,
            tier=tier,
            quota=quota,
            metadata=metadata or {},
        )

    def update_tier(self, new_tier: TenantTier) -> None:
        """更新租户层级

        更新层级时会自动调整配额到对应层级的默认值。

        Args:
            new_tier: 新层级
        """
        self.tier = new_tier
        self.quota = ResourceQuota.for_tier(new_tier)
        self.updated_at = datetime.now(UTC)

    def update_quota(self, new_quota: ResourceQuota) -> None:
        """更新自定义配额

        Args:
            new_quota: 新配额
        """
        self.quota = new_quota
        self.updated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        """停用租户"""
        self.is_active = False
        self.updated_at = datetime.now(UTC)

    def activate(self) -> None:
        """激活租户"""
        self.is_active = True
        self.updated_at = datetime.now(UTC)
