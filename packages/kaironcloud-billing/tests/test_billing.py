"""Tests for billing: bill_generator, tenant_models."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

# ── Tenant Models ───────────────────────────────────────────
from kaironcloud_billing.tenant_models import ResourceQuota, Tenant, TenantTier


class TestTenantTier:
    def test_values(self):
        assert TenantTier.FREE.value == "free"
        assert TenantTier.PRO.value == "pro"
        assert TenantTier.ENTERPRISE.value == "enterprise"


class TestResourceQuota:
    def test_defaults(self):
        q = ResourceQuota()
        assert q.max_workers == 5
        assert q.max_storage_gb == 1.0
        assert q.max_compute_hours == 100

    def test_to_dict(self):
        q = ResourceQuota(max_workers=10, max_storage_gb=5.0)
        d = q.to_dict()
        assert d["max_workers"] == 10
        assert d["max_storage_gb"] == 5.0

    def test_from_dict(self):
        q = ResourceQuota.from_dict({"max_workers": 20, "max_storage_gb": 10.0})
        assert q.max_workers == 20
        assert q.max_storage_gb == 10.0

    def test_from_dict_partial(self):
        q = ResourceQuota.from_dict({"max_workers": 15})
        assert q.max_workers == 15
        assert q.max_storage_gb == 1.0  # default

    def test_for_tier_free(self):
        q = ResourceQuota.for_tier(TenantTier.FREE)
        assert q.max_workers == 5
        assert q.max_api_keys == 2

    def test_for_tier_pro(self):
        q = ResourceQuota.for_tier(TenantTier.PRO)
        assert q.max_workers == 20
        assert q.max_api_keys == 10

    def test_for_tier_enterprise(self):
        q = ResourceQuota.for_tier(TenantTier.ENTERPRISE)
        assert q.max_workers == 100
        assert q.max_api_keys == 100


class TestTenant:
    def test_create_free(self):
        t = Tenant.create("test-tenant")
        assert t.name == "test-tenant"
        assert t.tier == TenantTier.FREE
        assert t.is_active is True
        assert len(t.tenant_id) > 0

    def test_create_pro(self):
        t = Tenant.create("pro-tenant", tier=TenantTier.PRO)
        assert t.tier == TenantTier.PRO
        assert t.quota.max_workers == 20

    def test_create_with_custom_quota(self):
        q = ResourceQuota(max_workers=50)
        t = Tenant.create("custom", quota=q)
        assert t.quota.max_workers == 50

    def test_to_dict(self):
        t = Tenant.create("test")
        d = t.to_dict()
        assert d["name"] == "test"
        assert d["tier"] == "free"
        assert d["is_active"] is True

    def test_from_dict(self):
        t = Tenant.from_dict({"name": "restored", "tier": "pro"})
        assert t.name == "restored"
        assert t.tier == TenantTier.PRO

    def test_from_dict_with_timestamps(self):
        now = datetime.now(UTC)
        t = Tenant.from_dict({
            "name": "ts-tenant",
            "tier": "enterprise",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })
        assert t.tier == TenantTier.ENTERPRISE

    def test_update_tier(self):
        t = Tenant.create("test", tier=TenantTier.FREE)
        t.update_tier(TenantTier.PRO)
        assert t.tier == TenantTier.PRO
        assert t.quota.max_workers == 20

    def test_update_quota(self):
        t = Tenant.create("test")
        new_q = ResourceQuota(max_workers=99)
        t.update_quota(new_q)
        assert t.quota.max_workers == 99

    def test_deactivate(self):
        t = Tenant.create("test")
        t.deactivate()
        assert t.is_active is False

    def test_activate(self):
        t = Tenant.create("test")
        t.deactivate()
        t.activate()
        assert t.is_active is True


# ── Bill Generator ──────────────────────────────────────────

from kaironcloud_billing.bill_generator import BillGenerator
from kaironcloud_billing.models import BillStatus, TierType, UsageReport
from kaironcloud_billing.usage_tracker import UsageTracker


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    import os
    try:
        os.unlink(path)
    except OSError:
        pass


class TestBillGenerator:
    def test_init_creates_tables(self, temp_db):
        BillGenerator(temp_db)
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            assert "bills" in tables
            assert "tenant_subscriptions" in tables

    @pytest.mark.asyncio
    async def test_update_tenant_subscription(self, temp_db):
        gen = BillGenerator(temp_db)
        sub = await gen.update_tenant_subscription("tenant-1", TierType.PRO)
        assert sub.tenant_id == "tenant-1"
        assert sub.tier == "pro"

    @pytest.mark.asyncio
    async def test_get_tenant_subscription(self, temp_db):
        gen = BillGenerator(temp_db)
        await gen.update_tenant_subscription("tenant-1", TierType.PRO)
        sub = await gen.get_tenant_subscription("tenant-1")
        assert sub is not None
        assert sub.tier == "pro"

    @pytest.mark.asyncio
    async def test_get_tenant_subscription_not_found(self, temp_db):
        gen = BillGenerator(temp_db)
        sub = await gen.get_tenant_subscription("nonexistent")
        assert sub is None

    def test_get_tenant_tier_default_free(self, temp_db):
        gen = BillGenerator(temp_db)
        tier = gen._get_tenant_tier("unknown")
        assert tier == TierType.FREE

    def test_get_tenant_tier_stored(self, temp_db):
        import asyncio
        gen = BillGenerator(temp_db)
        asyncio.run(gen.update_tenant_subscription("t2", TierType.ENTERPRISE))
        tier = gen._get_tenant_tier("t2")
        assert tier == TierType.ENTERPRISE

    @pytest.mark.asyncio
    async def test_generate_monthly_bill_no_tracker(self, temp_db):
        gen = BillGenerator(temp_db)
        with pytest.raises(ValueError, match="UsageTracker"):
            await gen.generate_monthly_bill("t1", 2026, 6)

    @pytest.mark.asyncio
    async def test_generate_monthly_bill(self, temp_db):
        mock_tracker = AsyncMock(spec=UsageTracker)
        mock_tracker.get_usage_report.return_value = UsageReport(
            tenant_id="t1",
            period_start=datetime(2026, 6, 1),
            period_end=datetime(2026, 7, 1),
            compute_hours=50,
            storage_gb=2.0,
            api_calls=5000,
        )
        gen = BillGenerator(temp_db, usage_tracker=mock_tracker)
        await gen.update_tenant_subscription("t1", TierType.PRO)
        bill = await gen.generate_monthly_bill("t1", 2026, 6)
        assert bill.tenant_id == "t1"
        assert bill.total_cost > Decimal("0")

    @pytest.mark.asyncio
    async def test_get_bill_not_found(self, temp_db):
        gen = BillGenerator(temp_db)
        bill = await gen.get_bill("nonexistent")
        assert bill is None

    @pytest.mark.asyncio
    async def test_get_bill_details_no_tracker(self, temp_db):
        gen = BillGenerator(temp_db)
        with pytest.raises(ValueError, match="UsageTracker"):
            await gen.get_bill_details("b-id")

    @pytest.mark.asyncio
    async def test_export_bill_not_found(self, temp_db):
        gen = BillGenerator(temp_db)
        with pytest.raises(ValueError, match="Bill not found"):
            await gen.export_bill_pdf("nonexistent")

    @pytest.mark.asyncio
    async def test_mark_bill_paid_not_found(self, temp_db):
        gen = BillGenerator(temp_db)
        with pytest.raises(ValueError, match="Bill not found"):
            await gen.mark_bill_paid("nonexistent")

    @pytest.mark.asyncio
    async def test_mark_bill_paid(self, temp_db):
        mock_tracker = AsyncMock(spec=UsageTracker)
        mock_tracker.get_usage_report.return_value = UsageReport(
            tenant_id="t1", period_start=datetime(2026, 6, 1),
            period_end=datetime(2026, 7, 1), compute_hours=10, storage_gb=1.0, api_calls=100,
        )
        gen = BillGenerator(temp_db, usage_tracker=mock_tracker)
        await gen.update_tenant_subscription("t1", TierType.FREE)
        bill = await gen.generate_monthly_bill("t1", 2026, 6)
        paid = await gen.mark_bill_paid(bill.bill_id)
        assert paid.status == BillStatus.PAID
        assert paid.paid_at is not None

    def test_row_to_bill(self, temp_db):
        gen = BillGenerator(temp_db)
        import sqlite3
        now = datetime.now(UTC)
        with sqlite3.connect(temp_db) as conn:
            conn.execute(
                """INSERT INTO bills (bill_id, tenant_id, tier, period_start, period_end,
                   base_cost, overage_cost, total_cost, status, line_items, created_at, paid_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("b1", "t1", "free", now.isoformat(), now.isoformat(),
                 "10.00", "5.00", "15.00", BillStatus.PENDING.value,
                 json.dumps([{"description": "compute", "quantity": 10, "unit_price": "1.00", "amount": "10.00"}]),
                 now.isoformat(), None),
            )
        bill = gen._row_to_bill(
            ("b1", "t1", "free", now.isoformat(), now.isoformat(),
             "10.00", "5.00", "15.00", BillStatus.PENDING.value,
             json.dumps([{"description": "compute", "quantity": 10, "unit_price": "1.00", "amount": "10.00"}]),
             now.isoformat(), None)
        )
        assert bill.bill_id == "b1"
        assert bill.total_cost == Decimal("15.00")
        assert bill.status == BillStatus.PENDING

    def test_close(self, temp_db):
        gen = BillGenerator(temp_db)
        gen.close()  # should not raise
