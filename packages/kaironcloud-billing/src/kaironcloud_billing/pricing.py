"""定价模型

定义B-OS Cloud的定价套餐和费用计算逻辑
"""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .models import Bill, BillLineItem, BillStatus, PricingTier, TierType, UsageReport


class PricingModel:
    """定价模型

    管理不同套餐的定价规则和费用计算

    Attributes:
        TIERS: 预定义套餐配置
    """

    TIERS: dict[str, dict[str, Any]] = {
        TierType.FREE: {
            "monthly_cost": Decimal("0"),
            "included_compute_hours": 10,
            "included_storage_gb": 1,
            "included_api_calls": 1000,
            "overage_compute_per_hour": Decimal("0.50"),
            "overage_storage_per_gb": Decimal("0.10"),
            "overage_api_per_1000": Decimal("0.50"),
        },
        TierType.PRO: {
            "monthly_cost": Decimal("49"),
            "included_compute_hours": 100,
            "included_storage_gb": 10,
            "included_api_calls": 10000,
            "overage_compute_per_hour": Decimal("0.30"),
            "overage_storage_per_gb": Decimal("0.08"),
            "overage_api_per_1000": Decimal("0.30"),
        },
        TierType.ENTERPRISE: {
            "monthly_cost": Decimal("499"),
            "included_compute_hours": 1000,
            "included_storage_gb": 100,
            "included_api_calls": 100000,
            "overage_compute_per_hour": Decimal("0.20"),
            "overage_storage_per_gb": Decimal("0.05"),
            "overage_api_per_1000": Decimal("0.10"),
        },
    }

    @classmethod
    def get_tier_config(cls, tier: str) -> dict[str, Any]:
        """获取套餐配置

        Args:
            tier: 套餐类型

        Returns:
            套餐配置字典

        Raises:
            ValueError: 套餐类型无效
        """
        if tier not in cls.TIERS:
            raise ValueError(f"Invalid tier: {tier}. Valid tiers: {list(cls.TIERS.keys())}")
        return cls.TIERS[tier]

    @classmethod
    def get_pricing_tier(cls, tier: str) -> PricingTier:
        """获取定价套餐对象

        Args:
            tier: 套餐类型

        Returns:
            PricingTier对象
        """
        config = cls.get_tier_config(tier)
        return PricingTier(
            name=tier,
            monthly_cost=config["monthly_cost"],
            included_compute_hours=config["included_compute_hours"],
            included_storage_gb=config["included_storage_gb"],
            included_api_calls=config["included_api_calls"],
            overage_compute_per_hour=config["overage_compute_per_hour"],
            overage_storage_per_gb=config["overage_storage_per_gb"],
            overage_api_per_1000=config["overage_api_per_1000"],
        )

    @classmethod
    def calculate_cost(cls, tier: str, usage: UsageReport) -> Bill:
        """根据使用量和套餐计算费用

        Args:
            tier: 套餐类型
            usage: 使用报告

        Returns:
            计算后的账单对象
        """
        config = cls.get_tier_config(tier)

        base_cost = config["monthly_cost"]

        line_items = []
        overage_cost = Decimal("0")

        # 计算计算时间超额
        compute_overage = max(0, usage.compute_hours - config["included_compute_hours"])
        if compute_overage > 0:
            compute_cost = Decimal(str(compute_overage)) * config["overage_compute_per_hour"]
            compute_cost = compute_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            overage_cost += compute_cost
            line_items.append(
                BillLineItem(
                    description=f"Compute Overage ({compute_overage:.2f} hours)",
                    quantity=compute_overage,
                    unit_price=config["overage_compute_per_hour"],
                    amount=compute_cost,
                    resource_type="compute",
                )
            )

        # 计算存储超额
        storage_overage = max(0, usage.storage_gb - config["included_storage_gb"])
        if storage_overage > 0:
            storage_cost = Decimal(str(storage_overage)) * config["overage_storage_per_gb"]
            storage_cost = storage_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            overage_cost += storage_cost
            line_items.append(
                BillLineItem(
                    description=f"Storage Overage ({storage_overage:.2f} GB)",
                    quantity=storage_overage,
                    unit_price=config["overage_storage_per_gb"],
                    amount=storage_cost,
                    resource_type="storage",
                )
            )

        # 计算API调用超额
        api_overage = max(0, usage.api_calls - config["included_api_calls"])
        if api_overage > 0:
            api_units = api_overage / 1000
            api_cost = Decimal(str(api_units)) * config["overage_api_per_1000"]
            api_cost = api_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            overage_cost += api_cost
            line_items.append(
                BillLineItem(
                    description=f"API Calls Overage ({api_overage:,} calls)",
                    quantity=api_overage,
                    unit_price=config["overage_api_per_1000"] / 1000,
                    amount=api_cost,
                    resource_type="api",
                )
            )

        # 基础套餐费用行项目
        if base_cost > 0:
            line_items.insert(
                0,
                BillLineItem(
                    description=f"{tier.title()} Plan - Monthly Subscription",
                    quantity=1,
                    unit_price=base_cost,
                    amount=base_cost,
                ),
            )
        else:
            line_items.insert(
                0,
                BillLineItem(
                    description="Free Plan",
                    quantity=1,
                    unit_price=Decimal("0"),
                    amount=Decimal("0"),
                ),
            )

        total_cost = base_cost + overage_cost

        bill_id = f"BILL-{usage.tenant_id}-{usage.period_start.strftime('%Y%m')}-{datetime.now(UTC).strftime('%H%M%S')}"

        return Bill(
            bill_id=bill_id,
            tenant_id=usage.tenant_id,
            tier=tier,
            period_start=usage.period_start,
            period_end=usage.period_end,
            base_cost=base_cost,
            overage_cost=overage_cost,
            total_cost=total_cost,
            status=BillStatus.DRAFT,
            line_items=line_items,
        )

    @classmethod
    def calculate_overage_preview(cls, tier: str, usage: UsageReport) -> dict[str, Any]:
        """计算超额费用预览

        不生成完整账单，仅返回超额相关信息

        Args:
            tier: 套餐类型
            usage: 使用报告

        Returns:
            超额信息字典
        """
        config = cls.get_tier_config(tier)

        compute_overage = max(0, usage.compute_hours - config["included_compute_hours"])
        storage_overage = max(0, usage.storage_gb - config["included_storage_gb"])
        api_overage = max(0, usage.api_calls - config["included_api_calls"])

        compute_cost = Decimal(str(compute_overage)) * config["overage_compute_per_hour"]
        storage_cost = Decimal(str(storage_overage)) * config["overage_storage_per_gb"]
        api_cost = Decimal(str(api_overage / 1000)) * config["overage_api_per_1000"]

        return {
            "tier": tier,
            "base_cost": config["monthly_cost"],
            "compute": {
                "used": usage.compute_hours,
                "included": config["included_compute_hours"],
                "overage": compute_overage,
                "cost": compute_cost.quantize(Decimal("0.01")),
            },
            "storage": {
                "used": usage.storage_gb,
                "included": config["included_storage_gb"],
                "overage": storage_overage,
                "cost": storage_cost.quantize(Decimal("0.01")),
            },
            "api": {
                "used": usage.api_calls,
                "included": config["included_api_calls"],
                "overage": api_overage,
                "cost": api_cost.quantize(Decimal("0.01")),
            },
            "total_overage_cost": (compute_cost + storage_cost + api_cost).quantize(Decimal("0.01")),
        }

    @classmethod
    def get_available_tiers(cls) -> list:
        """获取所有可用套餐列表

        Returns:
            套餐信息列表
        """
        return [
            {
                "name": TierType(tier),
                **{k: (float(v) if isinstance(v, Decimal) else v) for k, v in config.items()},
            }
            for tier, config in cls.TIERS.items()
        ]

    @classmethod
    def recommend_tier(cls, usage: UsageReport) -> TierType:
        """根据使用量推荐套餐

        推荐逻辑：
        1. 如果当前使用量超出某个套餐的包含范围，推荐能完全覆盖的套餐
        2. 如果多个套餐都能覆盖，选择价格最低的

        Args:
            usage: 使用报告

        Returns:
            推荐的套餐名称
        """
        can_fit_free = (
            usage.compute_hours <= cls.TIERS[TierType.FREE]["included_compute_hours"]
            and usage.storage_gb <= cls.TIERS[TierType.FREE]["included_storage_gb"]
            and usage.api_calls <= cls.TIERS[TierType.FREE]["included_api_calls"]
        )

        can_fit_pro = (
            usage.compute_hours <= cls.TIERS[TierType.PRO]["included_compute_hours"]
            and usage.storage_gb <= cls.TIERS[TierType.PRO]["included_storage_gb"]
            and usage.api_calls <= cls.TIERS[TierType.PRO]["included_api_calls"]
        )

        if can_fit_free:
            return TierType.FREE
        elif can_fit_pro:
            return TierType.PRO
        else:
            return TierType.ENTERPRISE

    @classmethod
    def _estimate_total_cost(cls, tier: str, usage: UsageReport) -> Decimal:
        """估算指定套餐的总费用"""
        config = cls.get_tier_config(tier)
        base_cost = config["monthly_cost"]

        compute_overage = max(0, usage.compute_hours - config["included_compute_hours"])
        storage_overage = max(0, usage.storage_gb - config["included_storage_gb"])
        api_overage = max(0, usage.api_calls - config["included_api_calls"])

        overage_cost = (
            Decimal(str(compute_overage)) * config["overage_compute_per_hour"]
            + Decimal(str(storage_overage)) * config["overage_storage_per_gb"]
            + Decimal(str(api_overage / 1000)) * config["overage_api_per_1000"]
        )

        return base_cost + overage_cost
