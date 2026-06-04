"""Tests for the SLO module — SLOTracker, SLODefinition, SLOBreach, SLOCompliance."""

from datetime import datetime, timedelta, timezone

import pytest

from observability.slo import (
    SLOBreach,
    SLOCompliance,
    SLODefinition,
    SLOStatus,
    SLOTracker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker():
    return SLOTracker()


@pytest.fixture
def populated_tracker(tracker):
    """Track 100 latency values: 90 at 100ms, 10 at 900ms."""
    for _ in range(90):
        tracker.track("api-gateway", "latency_ms", 100.0)
    for _ in range(10):
        tracker.track("api-gateway", "latency_ms", 900.0)
    return tracker


# ---------------------------------------------------------------------------
# SLOStatus
# ---------------------------------------------------------------------------


class TestSLOStatus:
    def test_fields(self):
        s = SLOStatus(p99_ms=250.0, availability_pct=99.5, window_hours=24.0)
        assert s.p99_ms == 250.0
        assert s.availability_pct == 99.5
        assert s.window_hours == 24.0


# ---------------------------------------------------------------------------
# SLODefinition
# ---------------------------------------------------------------------------


class TestSLODefinition:
    def test_default_threshold_is_target_p99(self):
        d = SLODefinition(
            name="p99-latency",
            service="api",
            metric="latency_ms",
            target_p99_ms=500.0,
            target_availability=99.9,
            window_hours=1.0,
        )
        assert d.threshold_ms == 500.0

    def test_custom_threshold(self):
        d = SLODefinition(
            name="p99-latency",
            service="api",
            metric="latency_ms",
            target_p99_ms=500.0,
            target_availability=99.9,
            window_hours=1.0,
            threshold_ms=300.0,
        )
        assert d.threshold_ms == 300.0


# ---------------------------------------------------------------------------
# SLOBreach
# ---------------------------------------------------------------------------


class TestSLOBreach:
    def test_fields(self):
        b = SLOBreach(
            slo_name="test",
            service="svc",
            metric="m",
            current_p99_ms=600.0,
            current_availability=95.0,
            target_p99_ms=500.0,
            target_availability=99.0,
            breach_type="p99",
        )
        assert b.slo_name == "test"
        assert b.breach_type == "p99"
        assert b.breached_at  # ISO timestamp

    def test_breach_timestamp(self):
        b = SLOBreach(
            slo_name="t", service="s", metric="m",
            current_p99_ms=1.0, current_availability=1.0,
            target_p99_ms=1.0, target_availability=1.0,
            breach_type="none",
        )
        datetime.fromisoformat(b.breached_at)  # does not raise


# ---------------------------------------------------------------------------
# SLOCompliance
# ---------------------------------------------------------------------------


class TestSLOCompliance:
    def test_fully_compliant(self):
        c = SLOCompliance(
            slo_name="test", p99_ms=100.0, p99_compliant=True,
            availability_pct=99.99, availability_compliant=True,
            overall_compliant=True, observations=100, window_hours=24.0,
        )
        assert c.overall_compliant is True

    def test_partially_compliant(self):
        c = SLOCompliance(
            slo_name="test", p99_ms=600.0, p99_compliant=False,
            availability_pct=99.99, availability_compliant=True,
            overall_compliant=False, observations=100, window_hours=1.0,
        )
        assert c.overall_compliant is False
        assert c.p99_compliant is False


# ---------------------------------------------------------------------------
# Track method
# ---------------------------------------------------------------------------


class TestTrack:
    def test_track_stores_points(self, tracker):
        tracker.track("svc", "latency_ms", 123.0)
        key = ("svc", "latency_ms")
        assert len(tracker._store[key]) == 1
        assert tracker._store[key][0].value == 123.0

    def test_track_with_timestamp(self, tracker):
        ts = datetime.now(tz=timezone.utc) - timedelta(hours=48)
        tracker.track("svc", "latency_ms", 999.0, timestamp=ts)
        # Should still be stored
        key = ("svc", "latency_ms")
        assert len(tracker._store[key]) == 1


# ---------------------------------------------------------------------------
# GetSLO
# ---------------------------------------------------------------------------


class TestGetSLO:
    def test_slo_returns_status(self, populated_tracker):
        status = populated_tracker.get_slo("api-gateway", "latency_ms")
        assert isinstance(status, SLOStatus)
        assert status.p99_ms > 0.0
        assert 0.0 <= status.availability_pct <= 100.0

    def test_slo_p99_with_threshold(self, populated_tracker):
        status = populated_tracker.get_slo("api-gateway", "latency_ms", threshold_ms=500.0)
        # 90 of 100 values are <= 500? The 90 values at 100ms are <= 500, but the 10 at 900ms are not.
        # So availability should be exactly 90%
        assert status.availability_pct == 90.0

    def test_slo_no_data(self, tracker):
        status = tracker.get_slo("unknown", "latency_ms")
        assert status.p99_ms == 0.0
        assert status.availability_pct == 100.0

    def test_slo_window_filters_old_data(self, tracker):
        # Add data from 48h ago
        old_ts = datetime.now(tz=timezone.utc) - timedelta(hours=48)
        tracker.track("svc", "latency_ms", 999.0, timestamp=old_ts)
        # With a 1h window, no data should be considered
        status = tracker.get_slo("svc", "latency_ms", window_hours=1.0)
        assert status.p99_ms == 0.0  # no data in window
        assert status.availability_pct == 100.0


# ---------------------------------------------------------------------------
# Record Latency / Error / Success
# ---------------------------------------------------------------------------


class TestConvenienceMethods:
    def test_record_latency(self, tracker):
        tracker.record_latency("svc", 250.0)
        status = tracker.get_slo("svc", "latency_ms", window_hours=1.0)
        assert status.p99_ms == 250.0

    def test_record_error(self, tracker):
        tracker.record_error("svc")
        tracker.record_error("svc")
        # Should be stored as error_total with value 1.0
        key = ("svc", "error_total")
        assert len(tracker._store[key]) == 2
        assert all(p.value == 1.0 for p in tracker._store[key])

    def test_record_success(self, tracker):
        tracker.record_success("svc")
        key = ("svc", "error_total")
        assert tracker._store[key][0].value == 0.0


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_all(self, populated_tracker):
        removed = populated_tracker.clear()
        assert removed > 0
        assert len(populated_tracker._store) == 0

    def test_clear_by_service(self, tracker):
        tracker.record_latency("svc-a", 100.0)
        tracker.record_latency("svc-b", 200.0)
        removed = tracker.clear(service="svc-a")
        assert removed == 1
        assert ("svc-a", "latency_ms") not in tracker._store
        assert ("svc-b", "latency_ms") in tracker._store

    def test_clear_by_metric(self, tracker):
        tracker.record_latency("svc", 100.0)
        tracker.track("svc", "cpu", 50.0)
        removed = tracker.clear(metric="cpu")
        assert removed == 1
        assert ("svc", "cpu") not in tracker._store
        assert ("svc", "latency_ms") in tracker._store

    def test_clear_nonexistent(self, tracker):
        removed = tracker.clear(service="nobody")
        assert removed == 0


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------


class TestCompliance:
    def test_compliant_slo(self, populated_tracker):
        slo = SLODefinition(
            name="good-latency",
            service="api-gateway",
            metric="latency_ms",
            target_p99_ms=1000.0,
            target_availability=80.0,
            window_hours=24.0,
        )
        comp = populated_tracker.get_compliance(slo)
        assert comp.overall_compliant is True
        assert comp.p99_compliant is True
        assert comp.availability_compliant is True

    def test_non_compliant_p99(self, populated_tracker):
        slo = SLODefinition(
            name="tight-latency",
            service="api-gateway",
            metric="latency_ms",
            target_p99_ms=100.0,  # too tight
            target_availability=80.0,
            window_hours=24.0,
        )
        comp = populated_tracker.get_compliance(slo)
        assert comp.overall_compliant is False
        assert comp.p99_compliant is False

    def test_non_compliant_availability(self, populated_tracker):
        slo = SLODefinition(
            name="high-avail",
            service="api-gateway",
            metric="latency_ms",
            target_p99_ms=1000.0,
            target_availability=99.0,  # 90% actual < 99% target
            window_hours=24.0,
            threshold_ms=500.0,  # only 90 values (at 100ms) are available; 10 (at 900ms) are not
        )
        comp = populated_tracker.get_compliance(slo)
        assert comp.overall_compliant is False
        assert comp.availability_compliant is False

    def test_compliance_observation_count(self, populated_tracker):
        slo = SLODefinition(
            name="test",
            service="api-gateway",
            metric="latency_ms",
            target_p99_ms=1000.0,
            target_availability=80.0,
            window_hours=24.0,
        )
        comp = populated_tracker.get_compliance(slo)
        assert comp.observations == 100


# ---------------------------------------------------------------------------
# Breach detection
# ---------------------------------------------------------------------------


class TestBreaches:
    def test_no_breach(self, populated_tracker):
        slos = [
            SLODefinition("ok", "api-gateway", "latency_ms", 1000.0, 80.0, 24.0),
        ]
        breaches = populated_tracker.check_breaches(slos)
        assert len(breaches) == 0

    def test_p99_breach(self, populated_tracker):
        slos = [
            SLODefinition("tight", "api-gateway", "latency_ms", 100.0, 80.0, 24.0),
        ]
        breaches = populated_tracker.check_breaches(slos)
        assert len(breaches) == 1
        b = breaches[0]
        assert b.slo_name == "tight"
        assert "p99" in b.breach_type

    def test_availability_breach(self, populated_tracker):
        slos = [
            SLODefinition(
                "high-avail", "api-gateway", "latency_ms",
                1000.0, 99.0, 24.0, threshold_ms=500.0,
            ),
        ]
        breaches = populated_tracker.check_breaches(slos)
        assert len(breaches) == 1
        b = breaches[0]
        assert "availability" in b.breach_type

    def test_multiple_breaches(self, populated_tracker):
        slos = [
            SLODefinition("a", "api-gateway", "latency_ms", 100.0, 99.0, 24.0),
            SLODefinition("b", "api-gateway", "latency_ms", 1000.0, 80.0, 24.0),
        ]
        breaches = populated_tracker.check_breaches(slos)
        assert len(breaches) == 1  # only "a" breaches

    def test_breach_handler_called(self, populated_tracker):
        handler_calls = []
        populated_tracker.set_breach_handler(lambda b: handler_calls.append(b))
        slos = [
            SLODefinition("tight", "api-gateway", "latency_ms", 100.0, 80.0, 24.0),
        ]
        populated_tracker.check_breaches(slos)
        assert len(handler_calls) == 1
        assert handler_calls[0].slo_name == "tight"

    def test_breach_handler_not_called_when_compliant(self, populated_tracker):
        handler_calls = []
        populated_tracker.set_breach_handler(lambda b: handler_calls.append(b))
        slos = [
            SLODefinition("ok", "api-gateway", "latency_ms", 1000.0, 80.0, 24.0),
        ]
        populated_tracker.check_breaches(slos)
        assert len(handler_calls) == 0


# ---------------------------------------------------------------------------
# Multi-window report
# ---------------------------------------------------------------------------


class TestMultiWindowReport:
    def test_returns_all_windows(self, populated_tracker):
        report = populated_tracker.get_multi_window_report("api-gateway", "latency_ms")
        for label in ("1h", "24h", "7d"):
            assert label in report
            assert isinstance(report[label], SLOStatus)

    def test_window_values_differ(self, tracker):
        # Add data only in a recent window
        now = datetime.now(tz=timezone.utc)
        old = now - timedelta(hours=48)
        tracker.track("svc", "latency_ms", 100.0, timestamp=now)
        tracker.track("svc", "latency_ms", 900.0, timestamp=old)
        report = tracker.get_multi_window_report("svc", "latency_ms")
        # 1h should only see the recent value (p99=100, avail=100)
        assert report["1h"].p99_ms == 100.0
        assert report["1h"].availability_pct == 100.0
        # 7d should see all (p99=900, avail=50% since one <=500? 100 <= 500, 900 > 500, so 50%)
        assert report["7d"].p99_ms == 900.0
        assert report["7d"].availability_pct == 50.0


# ---------------------------------------------------------------------------
# Error budget
# ---------------------------------------------------------------------------


class TestErrorBudget:
    def test_no_errors_full_budget(self, tracker):
        tracker.record_success("svc")
        tracker.record_success("svc")
        budget = tracker.get_error_budget_remaining("svc", window_hours=24.0, target_availability=99.9)
        assert budget["error_count"] == 0
        assert budget["remaining_budget_pct"] == 100.0

    def test_all_errors_exhausted_budget(self, tracker):
        for _ in range(100):
            tracker.record_error("svc")
        budget = tracker.get_error_budget_remaining("svc", window_hours=24.0, target_availability=99.0)
        assert budget["error_count"] == 100
        assert budget["remaining_budget_pct"] < 100.0

    def test_no_data(self, tracker):
        budget = tracker.get_error_budget_remaining("nil-svc")
        assert budget["total_requests"] == 0
        assert budget["remaining_budget_pct"] == 100.0

    def test_budget_used_calculation(self, tracker):
        # 1000 requests, 5 errors. Target 99.9% → allowable = 1000 * 0.001 = 1.0
        # budget_used = 5/1*100 = 500% → capped at 100%
        for _ in range(995):
            tracker.record_success("svc")
        for _ in range(5):
            tracker.record_error("svc")
        budget = tracker.get_error_budget_remaining("svc", window_hours=24.0, target_availability=99.9)
        assert budget["total_requests"] == 1000
        assert budget["error_count"] == 5
        assert budget["error_budget_used_pct"] == 100.0  # capped
        assert budget["remaining_budget_pct"] == 0.0


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


class TestSnapshot:
    def test_snapshot_full(self, populated_tracker):
        snap = populated_tracker.get_snapshot("api-gateway")
        assert snap["service"] == "api-gateway"
        assert "latency_ms" in snap["metrics"]
        m = snap["metrics"]["latency_ms"]
        assert m["count"] == 100
        assert m["p99"] > m["p50"]

    def test_snapshot_unknown_service(self, tracker):
        snap = tracker.get_snapshot("nobody")
        assert snap["service"] == "nobody"
        assert snap["metrics"] == {}


# ---------------------------------------------------------------------------
# Percentile helper
# ---------------------------------------------------------------------------


class TestPercentileHelper:
    def test_percentile_edge_cases(self):
        from observability.slo import _percentile
        # Single value
        assert _percentile([42.0], 99.0) == 42.0
        # Empty
        assert _percentile([], 99.0) == 0.0
        # Two values, p50 → nearest-rank: ceil(0.5*2)=1 → sorted[0]=10.0
        assert _percentile([10.0, 20.0], 50.0) == 10.0
        # P99 of 1-100 with nearest-rank: rank=ceil(0.99*100)=99 → sorted[98]=99
        assert _percentile(list(range(1, 101)), 99.0) == 99.0
        # P100 should return the max
        assert _percentile(list(range(1, 101)), 100.0) == 100.0
