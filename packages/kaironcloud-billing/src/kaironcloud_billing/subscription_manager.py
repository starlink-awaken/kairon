from __future__ import annotations

"""
订阅生命周期管理器

管理租户订阅的创建、升级、降级、取消等全生命周期
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .models import TierType
from .pricing import PricingModel
from .stripe_integration import StripeClient


class SubscriptionStatus(StrEnum):
    """订阅状态"""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"


class SubscriptionAction(StrEnum):
    """订阅操作"""

    CREATE = "create"
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    CANCEL = "cancel"
    REACTIVATE = "reactivate"


@dataclass
class SubscriptionChange:
    """订阅变更记录"""

    action: SubscriptionAction
    from_tier: TierType | None
    to_tier: TierType
    timestamp: datetime
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ManagedSubscription:
    """托管的订阅"""

    subscription_id: str
    tenant_id: str
    customer_id: str
    tier: TierType
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    history: list[SubscriptionChange] = field(default_factory=list)


class SubscriptionManager:
    """订阅生命周期管理器

    协调B-OS订阅状态与Stripe订阅状态，处理：
    - 套餐升级/降级
    - 计费周期管理
    - 支付失败恢复
    - 订阅历史追踪
    """

    def __init__(self, stripe_client: StripeClient | None = None) -> None:
        """初始化订阅管理器

        Args:
            stripe_client: Stripe客户端实例，默认创建新实例
        """
        self.stripe = stripe_client or StripeClient()
        self.pricing = PricingModel()
        self._subscriptions: dict[str, ManagedSubscription] = {}

    def create_subscription(
        self, tenant_id: str, email: str, tier: TierType, name: str | None = None
    ) -> ManagedSubscription:
        """为新租户创建订阅

        Args:
            tenant_id: B-OS租户ID
            email: 账单邮箱
            tier: 选择的套餐
            name: 客户名称

        Returns:
            托管的订阅对象

        Raises:
            ValueError: 免费套餐不需要Stripe订阅
        """
        if tier == TierType.FREE:
            return self._create_free_subscription(tenant_id, email)

        customer = self.stripe.create_customer(email=email, name=name, metadata={"tenant_id": tenant_id})

        price_id = self.stripe.PRICE_IDS.get(tier.value)
        if not price_id:
            raise ValueError(f"No price ID configured for tier: {tier.value}")

        stripe_sub = self.stripe.create_subscription(
            customer_id=customer.customer_id, price_id=price_id, metadata={"tenant_id": tenant_id}
        )

        managed = ManagedSubscription(
            subscription_id=stripe_sub.subscription_id,
            tenant_id=tenant_id,
            customer_id=customer.customer_id,
            tier=tier,
            status=SubscriptionStatus(stripe_sub.status),
            current_period_start=stripe_sub.current_period_start,
            current_period_end=stripe_sub.current_period_end,
            history=[
                SubscriptionChange(
                    action=SubscriptionAction.CREATE,
                    from_tier=None,
                    to_tier=tier,
                    timestamp=datetime.now(UTC),
                    reason="Initial subscription",
                )
            ],
        )

        self._subscriptions[tenant_id] = managed
        return managed

    def upgrade_subscription(self, tenant_id: str, new_tier: TierType) -> ManagedSubscription:
        """升级订阅套餐

        Args:
            tenant_id: 租户ID
            new_tier: 目标套餐（必须高于当前）

        Returns:
            更新后的订阅
        """
        current = self._subscriptions.get(tenant_id)
        if not current:
            raise ValueError(f"No subscription found for tenant: {tenant_id}")

        if current.tier == TierType.FREE:
            return self._upgrade_from_free(current, new_tier)

        new_price_id = self.stripe.PRICE_IDS.get(new_tier.value)
        if not new_price_id:
            raise ValueError(f"No price ID for tier: {new_tier.value}")

        stripe_sub = self.stripe.get_subscription(current.subscription_id)

        change = SubscriptionChange(
            action=SubscriptionAction.UPGRADE,
            from_tier=current.tier,
            to_tier=new_tier,
            timestamp=datetime.now(UTC),
        )

        current.tier = new_tier
        if stripe_sub:
            current.status = SubscriptionStatus(stripe_sub.status)
        current.history.append(change)

        return current

    def downgrade_subscription(self, tenant_id: str, new_tier: TierType) -> ManagedSubscription:
        """降级订阅套餐

        降级在当前计费周期结束后生效
        """
        current = self._subscriptions.get(tenant_id)
        if not current:
            raise ValueError(f"No subscription found for tenant: {tenant_id}")

        if new_tier == TierType.FREE:
            return self.cancel_subscription(tenant_id, at_period_end=True)

        change = SubscriptionChange(
            action=SubscriptionAction.DOWNGRADE,
            from_tier=current.tier,
            to_tier=new_tier,
            timestamp=datetime.now(UTC),
            reason="Downgrade scheduled for next period",
        )

        current.tier = new_tier
        current.history.append(change)

        return current

    def cancel_subscription(
        self, tenant_id: str, at_period_end: bool = True, reason: str | None = None
    ) -> ManagedSubscription:
        """取消订阅

        Args:
            tenant_id: 租户ID
            at_period_end: 是否在周期结束时取消
            reason: 取消原因
        """
        current = self._subscriptions.get(tenant_id)
        if not current:
            raise ValueError(f"No subscription found for tenant: {tenant_id}")

        if current.tier == TierType.FREE:
            del self._subscriptions[tenant_id]
            return current

        self.stripe.cancel_subscription(current.subscription_id, at_period_end=at_period_end)

        change = SubscriptionChange(
            action=SubscriptionAction.CANCEL,
            from_tier=current.tier,
            to_tier=TierType.FREE,
            timestamp=datetime.now(UTC),
            reason=reason or "Customer cancellation",
        )

        current.tier = TierType.FREE if not at_period_end else current.tier
        current.status = SubscriptionStatus.CANCELED if not at_period_end else current.status
        current.cancel_at_period_end = at_period_end
        current.history.append(change)

        return current

    def get_subscription(self, tenant_id: str) -> ManagedSubscription | None:
        """获取租户订阅信息"""
        return self._subscriptions.get(tenant_id)

    def sync_from_stripe(self, tenant_id: str) -> ManagedSubscription | None:
        """从Stripe同步最新状态

        用于webhook处理后的状态同步
        """
        current = self._subscriptions.get(tenant_id)
        if not current or current.tier == TierType.FREE:
            return current

        stripe_sub = self.stripe.get_subscription(current.subscription_id)
        if not stripe_sub:
            return None

        current.status = SubscriptionStatus(stripe_sub.status)
        current.current_period_start = stripe_sub.current_period_start
        current.current_period_end = stripe_sub.current_period_end
        current.cancel_at_period_end = stripe_sub.cancel_at_period_end

        return current

    def _create_free_subscription(self, tenant_id: str, email: str) -> ManagedSubscription:
        """创建免费套餐订阅（无Stripe）"""
        managed = ManagedSubscription(
            subscription_id=f"free-{tenant_id}",
            tenant_id=tenant_id,
            customer_id="",
            tier=TierType.FREE,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.max,
            history=[
                SubscriptionChange(
                    action=SubscriptionAction.CREATE,
                    from_tier=None,
                    to_tier=TierType.FREE,
                    timestamp=datetime.now(UTC),
                    reason="Free tier subscription",
                )
            ],
        )

        self._subscriptions[tenant_id] = managed
        return managed

    def _upgrade_from_free(self, current: ManagedSubscription, new_tier: TierType) -> ManagedSubscription:
        """从免费套餐升级"""
        raise ValueError("Cannot upgrade from free tier. Use create_subscription instead.")
