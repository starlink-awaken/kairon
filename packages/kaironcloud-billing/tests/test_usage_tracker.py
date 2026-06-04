"""Tests for the usage tracker."""

import os
import tempfile
from datetime import UTC, datetime

import pytest
from kaironcloud_billing.models import ResourceType
from kaironcloud_billing.usage_tracker import UsageTracker


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def tracker(temp_db):
    """Create a UsageTracker with a temp database."""
    t = UsageTracker(db_path=temp_db)
    yield t
    t.close()


class TestUsageTrackerInit:
    def test_creates_db_file(self, temp_db):
        t = UsageTracker(db_path=temp_db)
        assert os.path.exists(temp_db)
        t.close()

    def test_default_path_creates_dir(self):
        import tempfile

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "subdir", "billing_usage.db")
        t = UsageTracker(db_path=db_path)
        assert os.path.exists(db_path)
        t.close()


class TestTrackComputeTime:
    @pytest.mark.asyncio
    async def test_basic_tracking(self, tracker):
        record = await tracker.track_compute_time(
            tenant_id="tenant-1",
            duration_ms=3600000,  # 1 hour
        )
        assert record.tenant_id == "tenant-1"
        assert record.resource_type == ResourceType.COMPUTE
        assert record.quantity == 1.0  # 3600000ms = 1 hour
        assert record.unit == "hours"
        assert record.metadata["worker_type"] == "default"
        assert record.metadata["duration_ms"] == 3600000

    @pytest.mark.asyncio
    async def test_with_custom_worker(self, tracker):
        record = await tracker.track_compute_time(tenant_id="tenant-1", duration_ms=1800000, worker_type="gpu")
        assert record.metadata["worker_type"] == "gpu"
        assert record.quantity == 0.5  # 30 minutes

    @pytest.mark.asyncio
    async def test_with_explicit_timestamp(self, tracker):
        ts = datetime(2025, 1, 15, 10, 0, tzinfo=UTC)
        record = await tracker.track_compute_time(tenant_id="tenant-1", duration_ms=1000, timestamp=ts)
        assert record.timestamp == ts


class TestTrackStorage:
    @pytest.mark.asyncio
    async def test_basic_tracking(self, tracker):
        # 1 GB in bytes
        record = await tracker.track_storage(tenant_id="tenant-1", bytes_used=1073741824)
        assert record.resource_type == ResourceType.STORAGE
        assert record.quantity == 1.0  # 1 GB
        assert record.unit == "gb"
        assert record.metadata["storage_type"] == "standard"

    @pytest.mark.asyncio
    async def test_custom_storage_type(self, tracker):
        record = await tracker.track_storage(tenant_id="tenant-1", bytes_used=1024, storage_type="archive")
        assert record.metadata["storage_type"] == "archive"


class TestTrackApiCalls:
    @pytest.mark.asyncio
    async def test_basic_tracking(self, tracker):
        record = await tracker.track_api_calls(tenant_id="tenant-1", endpoint="/api/v1/compute")
        assert record.resource_type == ResourceType.API
        assert record.quantity == 1.0
        assert record.unit == "calls"
        assert record.metadata["endpoint"] == "/api/v1/compute"

    @pytest.mark.asyncio
    async def test_batch_count(self, tracker):
        record = await tracker.track_api_calls(tenant_id="tenant-1", endpoint="/api/v1/batch", count=100)
        assert record.quantity == 100.0
        assert record.metadata["count"] == 100


class TestGetUsageReport:
    @pytest.mark.asyncio
    async def test_empty_report(self, tracker):
        report = await tracker.get_usage_report(
            tenant_id="tenant-1",
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 2, 1, tzinfo=UTC),
        )
        assert report.tenant_id == "tenant-1"
        assert report.compute_hours == 0.0
        assert report.storage_gb == 0.0
        assert report.api_calls == 0
        assert report.breakdown == []

    @pytest.mark.asyncio
    async def test_aggregates_compute(self, tracker):
        await tracker.track_compute_time(tenant_id="tenant-1", duration_ms=3600000)  # 1h
        await tracker.track_compute_time(tenant_id="tenant-1", duration_ms=1800000)  # 0.5h

        report = await tracker.get_usage_report(
            tenant_id="tenant-1",
            start_date=datetime(2020, 1, 1, tzinfo=UTC),
            end_date=datetime(2027, 1, 1, tzinfo=UTC),
        )
        assert report.compute_hours == pytest.approx(1.5)
        assert report.storage_gb == 0.0
        assert report.api_calls == 0
        assert len(report.breakdown) == 2

    @pytest.mark.asyncio
    async def test_aggregates_mixed_resources(self, tracker):
        ts_jan = datetime(2025, 1, 15, tzinfo=UTC)
        await tracker.track_compute_time(tenant_id="tenant-1", duration_ms=3600000, timestamp=ts_jan)
        await tracker.track_storage(tenant_id="tenant-1", bytes_used=2147483648, timestamp=ts_jan)  # 2GB
        await tracker.track_api_calls(tenant_id="tenant-1", endpoint="/api/test", count=50, timestamp=ts_jan)

        report = await tracker.get_usage_report(
            tenant_id="tenant-1",
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 2, 1, tzinfo=UTC),
        )
        assert report.compute_hours == 1.0
        assert report.storage_gb == 2.0
        assert report.api_calls == 50
        assert len(report.breakdown) == 3

    @pytest.mark.asyncio
    async def test_date_filtering(self, tracker):
        ts_jan = datetime(2025, 1, 15, tzinfo=UTC)
        ts_feb = datetime(2025, 2, 15, tzinfo=UTC)

        await tracker.track_compute_time(tenant_id="tenant-1", duration_ms=3600000, timestamp=ts_jan)
        await tracker.track_compute_time(tenant_id="tenant-1", duration_ms=7200000, timestamp=ts_feb)

        # Only January
        report = await tracker.get_usage_report(
            tenant_id="tenant-1",
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 1, 31, tzinfo=UTC),
        )
        assert report.compute_hours == 1.0
        assert len(report.breakdown) == 1

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, tracker):
        await tracker.track_compute_time(tenant_id="tenant-a", duration_ms=3600000)
        await tracker.track_compute_time(tenant_id="tenant-b", duration_ms=7200000)

        report_a = await tracker.get_usage_report(
            tenant_id="tenant-a",
            start_date=datetime(2022, 1, 1, tzinfo=UTC),
            end_date=datetime(2027, 1, 1, tzinfo=UTC),
        )
        assert report_a.compute_hours == 1.0

        report_b = await tracker.get_usage_report(
            tenant_id="tenant-b",
            start_date=datetime(2022, 1, 1, tzinfo=UTC),
            end_date=datetime(2027, 1, 1, tzinfo=UTC),
        )
        assert report_b.compute_hours == 2.0


class TestGetUsageSummary:
    @pytest.mark.asyncio
    async def test_default_30_days(self, tracker):
        summary = await tracker.get_usage_summary(tenant_id="tenant-1")
        assert summary["tenant_id"] == "tenant-1"
        assert "compute_hours" in summary
        assert "period_days" in summary

    @pytest.mark.asyncio
    async def test_custom_days(self, tracker):
        summary = await tracker.get_usage_summary(tenant_id="tenant-1", days=7)
        assert summary["period_days"] == 7


class TestContextManager:
    @pytest.mark.asyncio
    async def test_async_context_manager(self, temp_db):
        async with UsageTracker(db_path=temp_db) as t:
            record = await t.track_compute_time(tenant_id="tenant-1", duration_ms=1000)
            assert record.tenant_id == "tenant-1"
        # Connection closed after exiting context
