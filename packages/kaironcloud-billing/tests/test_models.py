"""Tests for billing models."""

from datetime import UTC, datetime
from decimal import Decimal

from kaironcloud_billing.models import (
    Bill,
    BillDetails,
    BillLineItem,
    BillStatus,
    PricingTier,
    ResourceType,
    TenantSubscription,
    TierType,
    UsageBreakdown,
    UsageRecord,
    UsageReport,
)


class TestResourceType:
    def test_enum_values(self):
        assert ResourceType.COMPUTE == "compute"
        assert ResourceType.STORAGE == "storage"
        assert ResourceType.API == "api"

    def test_enum_is_str(self):
        assert isinstance(ResourceType.COMPUTE, str)


class TestBillStatus:
    def test_enum_values(self):
        assert BillStatus.DRAFT == "draft"
        assert BillStatus.ISSUED == "issued"
        assert BillStatus.PAID == "paid"
        assert BillStatus.OVERDUE == "overdue"
        assert BillStatus.CANCELLED == "cancelled"


class TestTierType:
    def test_enum_values(self):
        assert TierType.FREE == "free"
        assert TierType.PRO == "pro"
        assert TierType.ENTERPRISE == "enterprise"


class TestUsageRecord:
    def test_create_basic(self):
        record = UsageRecord(
            tenant_id="tenant-1",
            resource_type="compute",
            quantity=2.5,
            unit="hours",
        )
        assert record.tenant_id == "tenant-1"
        assert record.resource_type == "compute"
        assert record.quantity == 2.5
        assert record.unit == "hours"
        assert record.metadata == {}

    def test_create_with_metadata(self):
        record = UsageRecord(
            tenant_id="tenant-1",
            resource_type="compute",
            quantity=1.0,
            unit="hours",
            metadata={"worker_type": "gpu"},
        )
        assert record.metadata["worker_type"] == "gpu"

    def test_timestamp_default_utc(self):
        record = UsageRecord(
            tenant_id="tenant-1",
            resource_type="compute",
            quantity=1.0,
            unit="hours",
        )
        assert record.timestamp.tzinfo == UTC

    def test_timestamp_from_string(self):
        record = UsageRecord(
            tenant_id="tenant-1",
            resource_type="compute",
            quantity=1.0,
            unit="hours",
            timestamp="2025-01-15T10:30:00+00:00",  # type: ignore[arg-type]
        )
        assert record.timestamp == datetime(2025, 1, 15, 10, 30, tzinfo=UTC)


class TestUsageReport:
    def test_create_basic(self):
        report = UsageReport(
            tenant_id="tenant-1",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 2, 1, tzinfo=UTC),
        )
        assert report.compute_hours == 0.0
        assert report.storage_gb == 0.0
        assert report.api_calls == 0
        assert report.breakdown == []

    def test_period_from_strings(self):
        report = UsageReport(
            tenant_id="tenant-1",
            period_start="2025-01-01T00:00:00+00:00",  # type: ignore[arg-type]
            period_end="2025-02-01T00:00:00+00:00",  # type: ignore[arg-type]
        )
        assert report.period_start == datetime(2025, 1, 1, tzinfo=UTC)
        assert report.period_end == datetime(2025, 2, 1, tzinfo=UTC)


class TestBillLineItem:
    def test_create(self):
        item = BillLineItem(
            description="Test item",
            quantity=10.0,
            unit_price=Decimal("0.50"),
            amount=Decimal("5.00"),
            resource_type="compute",
        )
        assert item.description == "Test item"
        assert item.quantity == 10.0
        assert item.unit_price == Decimal("0.50")
        assert item.amount == Decimal("5.00")
        assert item.resource_type == "compute"

    def test_resource_type_optional(self):
        item = BillLineItem(description="Test", quantity=1.0, unit_price=Decimal("1"), amount=Decimal("1"))
        assert item.resource_type is None


class TestBill:
    def test_create_basic(self):
        bill = Bill(
            bill_id="BILL-001",
            tenant_id="tenant-1",
            tier="pro",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 2, 1, tzinfo=UTC),
        )
        assert bill.bill_id == "BILL-001"
        assert bill.tenant_id == "tenant-1"
        assert bill.tier == "pro"
        assert bill.base_cost == Decimal("0")
        assert bill.overage_cost == Decimal("0")
        assert bill.total_cost == Decimal("0")
        assert bill.status == "draft"

    def test_custom_costs(self):
        bill = Bill(
            bill_id="BILL-002",
            tenant_id="tenant-1",
            tier="pro",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 2, 1, tzinfo=UTC),
            base_cost=Decimal("49.00"),
            overage_cost=Decimal("15.50"),
            total_cost=Decimal("64.50"),
        )
        assert bill.base_cost == Decimal("49.00")
        assert bill.overage_cost == Decimal("15.50")
        assert bill.total_cost == Decimal("64.50")

    def test_line_items_default_empty(self):
        bill = Bill(
            bill_id="BILL-003",
            tenant_id="tenant-1",
            tier="pro",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 2, 1, tzinfo=UTC),
        )
        assert bill.line_items == []

    def test_string_conversion(self):
        bill = Bill(
            bill_id="BILL-004",
            tenant_id="tenant-1",
            tier="pro",
            period_start="2025-01-01T00:00:00+00:00",  # type: ignore[arg-type]
            period_end="2025-02-01T00:00:00+00:00",  # type: ignore[arg-type]
            created_at="2025-01-15T12:00:00+00:00",  # type: ignore[arg-type]
        )
        assert bill.period_start == datetime(2025, 1, 1, tzinfo=UTC)
        assert bill.created_at == datetime(2025, 1, 15, 12, 0, tzinfo=UTC)

    def test_decimal_quantization(self):
        """Decimal costs should be properly converted from float-like inputs."""
        bill = Bill(
            bill_id="BILL-005",
            tenant_id="tenant-1",
            tier="pro",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 2, 1, tzinfo=UTC),
            base_cost=Decimal("49.99"),  # type: ignore[arg-type]
            overage_cost=Decimal("0.01"),  # type: ignore[arg-type]
            total_cost=Decimal("50.00"),  # type: ignore[arg-type]
        )
        assert bill.base_cost == Decimal("49.99")
        assert bill.total_cost == Decimal("50.00")


class TestPricingTier:
    def test_create(self):
        tier = PricingTier(
            name="pro",
            monthly_cost=Decimal("49"),
            included_compute_hours=100,
            included_storage_gb=10,
            included_api_calls=10000,
            overage_compute_per_hour=Decimal("0.30"),
            overage_storage_per_gb=Decimal("0.08"),
            overage_api_per_1000=Decimal("0.30"),
        )
        assert tier.name == "pro"
        assert tier.monthly_cost == Decimal("49")
        assert tier.included_compute_hours == 100


class TestTenantSubscription:
    def test_create(self):
        sub = TenantSubscription(
            tenant_id="tenant-1",
            tier="pro",
            started_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        assert sub.tenant_id == "tenant-1"
        assert sub.tier == "pro"
        assert sub.billing_day == 1
        assert sub.auto_renew is True
        assert sub.status == "active"


class TestUsageBreakdown:
    def test_create(self):
        breakdown = UsageBreakdown(
            resource_type="compute",
            quantity=10.5,
            unit="hours",
            cost=Decimal("5.25"),
        )
        assert breakdown.resource_type == "compute"
        assert breakdown.quantity == 10.5
        assert breakdown.cost == Decimal("5.25")


class TestBillDetails:
    def test_create(self):
        bill = Bill(
            bill_id="BILL-001",
            tenant_id="tenant-1",
            tier="pro",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 2, 1, tzinfo=UTC),
        )
        report = UsageReport(
            tenant_id="tenant-1",
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 2, 1, tzinfo=UTC),
        )
        details = BillDetails(bill=bill, usage_report=report, tier_info={"name": "pro"})
        assert details.bill == bill
        assert details.usage_report == report
        assert details.tier_info == {"name": "pro"}
