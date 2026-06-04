"""Tests for the pricing engine."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from kaironcloud_billing.models import BillStatus, TierType, UsageReport
from kaironcloud_billing.pricing import PricingModel


class TestGetTierConfig:
    def test_valid_tiers(self):
        for tier in ["free", "pro", "enterprise"]:
            config = PricingModel.get_tier_config(tier)
            assert "monthly_cost" in config
            assert "included_compute_hours" in config

    def test_invalid_tier_raises(self):
        with pytest.raises(ValueError, match="Invalid tier"):
            PricingModel.get_tier_config("nonexistent")

    def test_free_tier_cost_zero(self):
        config = PricingModel.get_tier_config("free")
        assert config["monthly_cost"] == Decimal("0")

    def test_pro_tier_cost(self):
        config = PricingModel.get_tier_config("pro")
        assert config["monthly_cost"] == Decimal("49")


class TestGetPricingTier:
    def test_returns_pricing_tier(self):
        tier = PricingModel.get_pricing_tier("pro")
        assert tier.name == "pro"
        assert tier.monthly_cost == Decimal("49")
        assert tier.included_compute_hours == 100
        assert tier.included_storage_gb == 10
        assert tier.included_api_calls == 10000
        assert tier.overage_compute_per_hour == Decimal("0.30")
        assert tier.overage_storage_per_gb == Decimal("0.08")
        assert tier.overage_api_per_1000 == Decimal("0.30")


class TestCalculateCost:
    def _make_usage(self, compute=0.0, storage=0.0, api=0):
        return UsageReport(
            tenant_id="tenant-1",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 2, 1, tzinfo=UTC),
            compute_hours=compute,
            storage_gb=storage,
            api_calls=api,
        )

    def test_free_tier_within_limits(self):
        usage = self._make_usage(compute=5, storage=0.5, api=500)
        bill = PricingModel.calculate_cost("free", usage)
        assert bill.total_cost == Decimal("0")
        assert bill.base_cost == Decimal("0")
        assert bill.overage_cost == Decimal("0")
        assert bill.status == BillStatus.DRAFT

    def test_free_tier_over_compute(self):
        usage = self._make_usage(compute=15, storage=0.5, api=500)  # 5h overage
        bill = PricingModel.calculate_cost("free", usage)
        # 5 * 0.50 = 2.50
        assert bill.base_cost == Decimal("0")
        assert bill.overage_cost == Decimal("2.50")
        assert bill.total_cost == Decimal("2.50")

    def test_free_tier_over_storage(self):
        usage = self._make_usage(compute=5, storage=3, api=500)  # 2GB overage
        bill = PricingModel.calculate_cost("free", usage)
        # 2 * 0.10 = 0.20
        assert bill.overage_cost == Decimal("0.20")
        assert bill.total_cost == Decimal("0.20")

    def test_free_tier_over_api(self):
        usage = self._make_usage(compute=5, storage=0.5, api=2000)  # 1000 overage
        bill = PricingModel.calculate_cost("free", usage)
        # 1000/1000 = 1 * 0.50 = 0.50
        assert bill.overage_cost == Decimal("0.50")
        assert bill.total_cost == Decimal("0.50")

    def test_pro_tier_within_limits(self):
        usage = self._make_usage(compute=50, storage=5, api=5000)
        bill = PricingModel.calculate_cost("pro", usage)
        assert bill.base_cost == Decimal("49")
        assert bill.overage_cost == Decimal("0")
        assert bill.total_cost == Decimal("49")

    def test_pro_tier_all_overages(self):
        usage = self._make_usage(compute=200, storage=20, api=20000)
        bill = PricingModel.calculate_cost("pro", usage)
        # compute: 100 * 0.30 = 30.00
        # storage: 10 * 0.08 = 0.80
        # api: 10000/1000 * 0.30 = 3.00
        # total overage: 33.80, total: 49 + 33.80 = 82.80
        assert bill.base_cost == Decimal("49")
        assert bill.overage_cost == Decimal("33.80")
        assert bill.total_cost == Decimal("82.80")

    def test_enterprise_within_limits(self):
        usage = self._make_usage(compute=500, storage=50, api=50000)
        bill = PricingModel.calculate_cost("enterprise", usage)
        assert bill.base_cost == Decimal("499")
        assert bill.overage_cost == Decimal("0")
        assert bill.total_cost == Decimal("499")

    def test_line_items_count_with_overage(self):
        usage = self._make_usage(compute=200, storage=20, api=20000)
        bill = PricingModel.calculate_cost("pro", usage)
        # 1 base + 3 overage = 4 line items
        assert len(bill.line_items) == 4
        # First line item is the base plan
        assert "Pro Plan" in bill.line_items[0].description

    def test_line_items_count_within_limits(self):
        usage = self._make_usage(compute=50, storage=5, api=5000)
        bill = PricingModel.calculate_cost("pro", usage)
        # 1 base only
        assert len(bill.line_items) == 1

    def test_bill_id_format(self):
        usage = self._make_usage(compute=5, storage=0.5, api=500)
        bill = PricingModel.calculate_cost("free", usage)
        assert bill.bill_id.startswith("BILL-tenant-1-202501-")

    def test_decimal_precision(self):
        """Test that calculations maintain 2-decimal precision."""
        usage = self._make_usage(compute=10.333, storage=1, api=1000)
        bill = PricingModel.calculate_cost("free", usage)
        # compute overage: 0.333 * 0.50 = 0.1665 -> 0.17
        assert bill.overage_cost == Decimal("0.17")


class TestCalculateOveragePreview:
    def _make_usage(self, compute=0.0, storage=0.0, api=0):
        return UsageReport(
            tenant_id="tenant-1",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 2, 1, tzinfo=UTC),
            compute_hours=compute,
            storage_gb=storage,
            api_calls=api,
        )

    def test_no_overage(self):
        usage = self._make_usage(compute=5, storage=0.5, api=500)
        preview = PricingModel.calculate_overage_preview("free", usage)
        assert preview["compute"]["overage"] == 0
        assert preview["storage"]["overage"] == 0
        assert preview["api"]["overage"] == 0
        assert preview["total_overage_cost"] == Decimal("0.00")

    def test_with_overage(self):
        usage = self._make_usage(compute=120, storage=15, api=15000)
        preview = PricingModel.calculate_overage_preview("pro", usage)
        assert preview["compute"]["overage"] == 20
        assert preview["storage"]["overage"] == 5
        assert preview["api"]["overage"] == 5000
        assert preview["total_overage_cost"] > Decimal("0")


class TestGetAvailableTiers:
    def test_returns_three_tiers(self):
        tiers = PricingModel.get_available_tiers()
        assert len(tiers) == 3

    def test_each_tier_has_name(self):
        tiers = PricingModel.get_available_tiers()
        names = [t["name"] for t in tiers]
        assert TierType.FREE in names
        assert TierType.PRO in names
        assert TierType.ENTERPRISE in names


class TestRecommendTier:
    def _make_usage(self, compute=0.0, storage=0.0, api=0):
        return UsageReport(
            tenant_id="tenant-1",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 2, 1, tzinfo=UTC),
            compute_hours=compute,
            storage_gb=storage,
            api_calls=api,
        )

    def test_recommend_free(self):
        usage = self._make_usage(compute=5, storage=0.5, api=500)
        assert PricingModel.recommend_tier(usage) == TierType.FREE

    def test_recommend_pro(self):
        usage = self._make_usage(compute=50, storage=5, api=5000)
        assert PricingModel.recommend_tier(usage) == TierType.PRO

    def test_recommend_enterprise(self):
        usage = self._make_usage(compute=2000, storage=200, api=200000)
        assert PricingModel.recommend_tier(usage) == TierType.ENTERPRISE

    def test_at_boundary_goes_to_lower(self):
        """At exact limits, should fit in that tier."""
        usage = self._make_usage(compute=10, storage=1, api=1000)
        assert PricingModel.recommend_tier(usage) == TierType.FREE
