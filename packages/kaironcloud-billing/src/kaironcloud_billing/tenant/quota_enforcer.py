from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: "@CloudArchitect"
Layer: L3
Domain: D-Cloud
Summary: "QuotaEnforcer — Enforces resource quotas and rate limits for tenants."
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# QuotaEnforcer ≡ Organ
# 内涵 ≝ {Resource_Quota_Enforcement, Rate_Limiting, Usage_Tracking}
# 外延 ≝ {e | e ∈ D-Cloud ∧ enforces(e, Quota)}
# 功能 ⊢ {Check_Compute, Check_Storage, Check_Rate_Limit, Track_Usage}
# =============================================================================
import logging
import time
from dataclasses import dataclass, field

from kaironcloud_billing.organs.tenant.manager import TenantManager
from kaironcloud_billing.organs.tenant.models import ResourceQuota

_log = logging.getLogger(__name__)

__all__ = ["QuotaEnforcer", "QuotaExceededError", "RateLimitExceededError"]


class QuotaExceededError(PermissionError):
    """配额超出错误"""

    def __init__(self, resource_type: str, requested: float, allowed: float, tenant_id: str) -> None:
        self.resource_type = resource_type
        self.requested = requested
        self.allowed = allowed
        self.tenant_id = tenant_id
        super().__init__(
            f"Quota exceeded for tenant {tenant_id}: requested {requested} {resource_type}, allowed {allowed}"
        )


class RateLimitExceededError(PermissionError):
    """速率限制超出错误"""

    def __init__(self, endpoint: str, retry_after: int, tenant_id: str) -> None:
        self.endpoint = endpoint
        self.retry_after = retry_after
        self.tenant_id = tenant_id
        super().__init__(
            f"Rate limit exceeded for tenant {tenant_id} on endpoint {endpoint}. Retry after {retry_after} seconds."
        )


@dataclass
class UsageMetrics:
    """使用量指标"""

    tenant_id: str
    compute_hours_used: float = 0.0
    storage_gb_used: float = 0.0
    requests_count: int = 0
    last_request_time: float = field(default_factory=time.time)
    concurrent_tasks: int = 0
    active_workers: int = 0


class QuotaEnforcer:
    """配额强制执行器

    负责强制执行租户的资源配额限制，包括：
    - 计算资源配额（compute hours, workers）
    - 存储配额
    - API速率限制

    Attributes:
        _tenant_manager: 租户管理器引用
        _usage_cache: 使用量缓存
        _rate_limit_windows: 速率限制滑动窗口
    """

    DEFAULT_WINDOW_SECONDS = 60  # 速率限制窗口大小（秒）

    def __init__(self, tenant_manager: TenantManager | None = None) -> None:
        """初始化配额强制执行器

        Args:
            tenant_manager: 租户管理器实例
        """
        self.status = "active"  # was super().__init__(metadata_path=...)
        self._tenant_manager = tenant_manager
        self._usage_cache: dict[str, UsageMetrics] = {}
        self._rate_limit_windows: dict[str, list[float]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """初始化配额强制执行器"""
        if self._initialized:
            return

        # 如果没有提供tenant_manager，创建默认实例
        if self._tenant_manager is None:
            self._tenant_manager = TenantManager()
            await self._tenant_manager.initialize()

        self._initialized = True
        _log.info("✅ [QuotaEnforcer] Initialized")

    def _get_usage(self, tenant_id: str) -> UsageMetrics:
        """获取或创建使用量指标"""
        if tenant_id not in self._usage_cache:
            self._usage_cache[tenant_id] = UsageMetrics(tenant_id=tenant_id)
        return self._usage_cache[tenant_id]

    def _get_tenant_quota(self, tenant_id: str) -> ResourceQuota | None:
        """获取租户配额"""
        if self._tenant_manager is None:
            return None
        # 同步获取租户（在异步上下文中使用run_coroutine_threadsafe或类似方法）
        import asyncio

        try:
            tenant = asyncio.get_event_loop().run_until_complete(self._tenant_manager.get_tenant(tenant_id))
            return tenant.quota if tenant and tenant.is_active else None
        except RuntimeError:
            # 没有事件循环时，直接访问缓存
            if hasattr(self._tenant_manager, "_tenants"):
                tenant = self._tenant_manager._tenants.get(tenant_id)
                return tenant.quota if tenant and tenant.is_active else None
            return None

    async def check_compute_quota(
        self,
        tenant_id: str,
        requested: int,
        resource_type: str = "workers",
    ) -> bool:
        """检查计算资源配额

        Args:
            tenant_id: 租户ID
            requested: 请求的资源数量
            resource_type: 资源类型（workers, tasks, compute_hours）

        Returns:
            是否允许请求

        Raises:
            QuotaExceededError: 如果超出配额
        """
        await self.initialize()

        quota = await self._get_quota_async(tenant_id)
        if quota is None:
            _log.warning("[QuotaEnforcer] Tenant not found: %s", tenant_id)
            return False

        usage = self._get_usage(tenant_id)

        if resource_type == "workers":
            current = usage.active_workers
            allowed = quota.max_workers
        elif resource_type == "tasks":
            current = usage.concurrent_tasks
            allowed = quota.max_concurrent_tasks
        elif resource_type == "compute_hours":
            current = usage.compute_hours_used
            allowed = quota.max_compute_hours
        else:
            _log.warning("[QuotaEnforcer] Unknown resource type: %s", resource_type)
            return False

        if current + requested > allowed:
            raise QuotaExceededError(
                resource_type=resource_type,
                requested=current + requested,
                allowed=allowed,
                tenant_id=tenant_id,
            )

        return True

    async def check_storage_quota(
        self,
        tenant_id: str,
        requested_gb: float,
    ) -> bool:
        """检查存储配额

        Args:
            tenant_id: 租户ID
            requested_gb: 请求的存储空间（GB）

        Returns:
            是否允许请求

        Raises:
            QuotaExceededError: 如果超出配额
        """
        await self.initialize()

        quota = await self._get_quota_async(tenant_id)
        if quota is None:
            _log.warning("[QuotaEnforcer] Tenant not found: %s", tenant_id)
            return False

        usage = self._get_usage(tenant_id)
        current = usage.storage_gb_used
        allowed = quota.max_storage_gb

        if current + requested_gb > allowed:
            raise QuotaExceededError(
                resource_type="storage_gb",
                requested=current + requested_gb,
                allowed=allowed,
                tenant_id=tenant_id,
            )

        return True

    async def check_rate_limit(
        self,
        tenant_id: str,
        endpoint: str = "default",
        increment: bool = True,
    ) -> bool:
        """检查API速率限制

        使用滑动窗口算法实现速率限制。

        Args:
            tenant_id: 租户ID
            endpoint: API端点标识
            increment: 是否增加请求计数

        Returns:
            是否允许请求

        Raises:
            RateLimitExceededError: 如果超出速率限制
        """
        await self.initialize()

        quota = await self._get_quota_async(tenant_id)
        if quota is None:
            _log.warning("[QuotaEnforcer] Tenant not found: %s", tenant_id)
            return False

        key = f"{tenant_id}:{endpoint}"
        now = time.time()
        window_start = now - self.DEFAULT_WINDOW_SECONDS

        # 获取或创建窗口
        if key not in self._rate_limit_windows:
            self._rate_limit_windows[key] = []

        window = self._rate_limit_windows[key]

        # 清理过期请求记录
        self._rate_limit_windows[key] = [t for t in window if t > window_start]

        # 检查是否超出限制
        current_requests = len(self._rate_limit_windows[key])
        if current_requests >= quota.max_requests_per_min:
            retry_after = int(self.DEFAULT_WINDOW_SECONDS - (now - self._rate_limit_windows[key][0]))
            raise RateLimitExceededError(
                endpoint=endpoint,
                retry_after=max(1, retry_after),
                tenant_id=tenant_id,
            )

        # 记录请求
        if increment:
            self._rate_limit_windows[key].append(now)
            usage = self._get_usage(tenant_id)
            usage.requests_count += 1
            usage.last_request_time = now

        return True

    async def _get_quota_async(self, tenant_id: str) -> ResourceQuota | None:
        """异步获取租户配额"""
        if self._tenant_manager is None:
            return None
        tenant = await self._tenant_manager.get_tenant(tenant_id)
        return tenant.quota if tenant and tenant.is_active else None

    async def record_usage(
        self,
        tenant_id: str,
        resource_type: str,
        amount: float,
    ) -> None:
        """记录资源使用

        Args:
            tenant_id: 租户ID
            resource_type: 资源类型（workers, tasks, storage_gb, compute_hours）
            amount: 使用数量（正数表示增加，负数表示减少）
        """
        usage = self._get_usage(tenant_id)

        if resource_type == "workers":
            usage.active_workers = max(0, usage.active_workers + int(amount))
        elif resource_type == "tasks":
            usage.concurrent_tasks = max(0, usage.concurrent_tasks + int(amount))
        elif resource_type == "storage_gb":
            usage.storage_gb_used = max(0.0, usage.storage_gb_used + amount)
        elif resource_type == "compute_hours":
            usage.compute_hours_used = max(0.0, usage.compute_hours_used + amount)

        _log.debug("[QuotaEnforcer] Recorded usage for %s: %s += %s", tenant_id, resource_type, amount)

    async def get_usage_metrics(self, tenant_id: str) -> UsageMetrics | None:
        """获取使用量指标

        Args:
            tenant_id: 租户ID

        Returns:
            UsageMetrics实例，如果租户不存在则返回None
        """
        await self.initialize()

        if tenant_id not in self._usage_cache:
            # 验证租户是否存在
            if self._tenant_manager:
                tenant = await self._tenant_manager.get_tenant(tenant_id)
                if tenant is None:
                    return None
            self._usage_cache[tenant_id] = UsageMetrics(tenant_id=tenant_id)

        return self._usage_cache[tenant_id]

    async def reset_usage(self, tenant_id: str) -> None:
        """重置使用量（通常用于月度结算）

        Args:
            tenant_id: 租户ID
        """
        if tenant_id in self._usage_cache:
            del self._usage_cache[tenant_id]

        # 清理速率限制窗口
        keys_to_remove = [k for k in self._rate_limit_windows if k.startswith(f"{tenant_id}:")]
        for key in keys_to_remove:
            del self._rate_limit_windows[key]

        _log.info("[QuotaEnforcer] Reset usage for tenant: %s", tenant_id)

    async def get_quota_status(
        self,
        tenant_id: str,
    ) -> dict | None:
        """获取配额状态

        Args:
            tenant_id: 租户ID

        Returns:
            配额状态字典，包含当前使用量和配额限制
        """
        await self.initialize()

        quota = await self._get_quota_async(tenant_id)
        usage = await self.get_usage_metrics(tenant_id)

        if quota is None or usage is None:
            return None

        return {
            "tenant_id": tenant_id,
            "compute": {
                "used": usage.compute_hours_used,
                "allowed": quota.max_compute_hours,
                "remaining": max(0, quota.max_compute_hours - usage.compute_hours_used),
            },
            "storage": {
                "used": usage.storage_gb_used,
                "allowed": quota.max_storage_gb,
                "remaining": max(0.0, quota.max_storage_gb - usage.storage_gb_used),
            },
            "workers": {
                "active": usage.active_workers,
                "allowed": quota.max_workers,
                "available": max(0, quota.max_workers - usage.active_workers),
            },
            "concurrent_tasks": {
                "active": usage.concurrent_tasks,
                "allowed": quota.max_concurrent_tasks,
                "available": max(0, quota.max_concurrent_tasks - usage.concurrent_tasks),
            },
            "rate_limit": {
                "window_seconds": self.DEFAULT_WINDOW_SECONDS,
                "allowed_per_window": quota.max_requests_per_min,
            },
        }
