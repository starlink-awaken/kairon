"""Tests for kairon_lib.slo — Role SLO Registry."""

import time

import pytest
from kairon_lib.slo import RoleSLO, RoleSLORegistry, RoleSLOViolation


class TestRoleSLO:
    """Tests for RoleSLO dataclass."""

    def test_basic_slo(self):
        slo = RoleSLO(role_id="reviewer", metric="latency_s", target=5.0)
        assert slo.role_id == "reviewer"
        assert slo.metric == "latency_s"
        assert slo.target == 5.0
        assert slo.window_seconds == 3600
        assert slo.description == ""

    def test_with_description(self):
        slo = RoleSLO(
            role_id="analyst",
            metric="accuracy",
            target=0.95,
            window_seconds=7200,
            description="Model accuracy must exceed 95%",
        )
        assert slo.description == "Model accuracy must exceed 95%"
        assert slo.window_seconds == 7200


class TestRoleSLOViolation:
    """Tests for RoleSLOViolation dataclass."""

    def test_basic_violation(self):
        ts = time.time()
        v = RoleSLOViolation(
            role_id="reviewer",
            metric="latency_s",
            actual=10.0,
            target=5.0,
            timestamp=ts,
        )
        assert v.role_id == "reviewer"
        assert v.metric == "latency_s"
        assert v.actual == 10.0
        assert v.target == 5.0
        assert v.timestamp == ts


class TestRoleSLORegistry:
    """Tests for RoleSLORegistry — the core SLO management class."""

    @pytest.fixture
    def registry(self):
        return RoleSLORegistry()

    def test_register_slo(self, registry):
        slo = RoleSLO("reviewer", "latency_s", target=5.0)
        registry.register_slo(slo)
        assert len(registry.list_slos()) == 1

    def test_register_replaces_existing(self, registry):
        slo1 = RoleSLO("reviewer", "latency_s", target=5.0)
        slo2 = RoleSLO("reviewer", "latency_s", target=3.0)
        registry.register_slo(slo1)
        registry.register_slo(slo2)
        slos = registry.list_slos("reviewer")
        assert len(slos) == 1
        assert slos[0].target == 3.0

    # ── Metric recording ─────────────────────────────────────────

    def test_record_metric_no_slo(self, registry):
        """Recording a metric for an unregistered SLO should not crash."""
        registry.record_metric("nobody", "latency_s", 10.0)

    def test_record_metric_compliant(self, registry):
        registry.register_slo(RoleSLO("reviewer", "latency_s", target=5.0))
        registry.record_metric("reviewer", "latency_s", 3.0)
        assert len(registry.get_violations()) == 0

    def test_record_metric_violation(self, registry):
        registry.register_slo(RoleSLO("reviewer", "latency_s", target=5.0))
        registry.record_metric("reviewer", "latency_s", 10.0)
        violations = registry.get_violations()
        assert len(violations) == 1
        assert violations[0].actual == 10.0
        assert violations[0].target == 5.0

    # ── Compliance checking ──────────────────────────────────────

    def test_check_compliance_empty(self, registry):
        """No SLOs registered = empty result."""
        result = registry.check_compliance("reviewer")
        assert result == {}

    def test_check_compliance_no_samples(self, registry):
        """SLO registered but no samples = compliant."""
        registry.register_slo(RoleSLO("reviewer", "latency_s", target=5.0))
        result = registry.check_compliance("reviewer")
        assert result["latency_s"]["compliant"] is True
        assert result["latency_s"]["samples"] == 0

    def test_check_compliance_all_ok(self, registry):
        registry.register_slo(RoleSLO("reviewer", "latency_s", target=5.0))
        registry.record_metric("reviewer", "latency_s", 3.0)
        registry.record_metric("reviewer", "latency_s", 4.0)
        result = registry.check_compliance("reviewer")
        assert result["latency_s"]["compliant"] is True
        assert result["latency_s"]["samples"] == 2
        assert result["latency_s"]["violations"] == 0

    def test_check_compliance_with_violations(self, registry):
        registry.register_slo(RoleSLO("reviewer", "latency_s", target=5.0))
        registry.record_metric("reviewer", "latency_s", 3.0)
        registry.record_metric("reviewer", "latency_s", 10.0)
        registry.record_metric("reviewer", "latency_s", 4.0)
        result = registry.check_compliance("reviewer")
        assert result["latency_s"]["compliant"] is False
        assert result["latency_s"]["samples"] == 3
        assert result["latency_s"]["violations"] == 1

    def test_check_compliance_multiple_metrics(self, registry):
        registry.register_slo(RoleSLO("reviewer", "latency_s", target=5.0))
        registry.register_slo(RoleSLO("reviewer", "error_rate", target=0.05))
        registry.record_metric("reviewer", "latency_s", 3.0)
        registry.record_metric("reviewer", "error_rate", 0.01)
        result = registry.check_compliance("reviewer")
        assert len(result) == 2
        assert result["latency_s"]["compliant"] is True
        assert result["error_rate"]["compliant"] is True

    # ── Violation retrieval ──────────────────────────────────────

    def test_get_violations_all(self, registry):
        registry.register_slo(RoleSLO("r1", "latency", target=5.0))
        registry.register_slo(RoleSLO("r2", "latency", target=5.0))
        registry.record_metric("r1", "latency", 10.0)
        registry.record_metric("r2", "latency", 10.0)
        assert len(registry.get_violations()) == 2

    def test_get_violations_filtered(self, registry):
        registry.register_slo(RoleSLO("r1", "latency", target=5.0))
        registry.register_slo(RoleSLO("r2", "latency", target=5.0))
        registry.record_metric("r1", "latency", 10.0)
        registry.record_metric("r2", "latency", 10.0)
        assert len(registry.get_violations("r1")) == 1
        assert len(registry.get_violations("r3")) == 0

    # ── Compliance rate ──────────────────────────────────────────

    def test_get_compliance_rate_perfect(self, registry):
        registry.register_slo(RoleSLO("reviewer", "latency_s", target=5.0))
        registry.register_slo(RoleSLO("reviewer", "memory_mb", target=512.0))
        registry.record_metric("reviewer", "latency_s", 3.0)
        registry.record_metric("reviewer", "memory_mb", 256.0)
        assert registry.get_compliance_rate("reviewer") == 1.0

    def test_get_compliance_rate_partial(self, registry):
        registry.register_slo(RoleSLO("reviewer", "latency_s", target=5.0))
        registry.register_slo(RoleSLO("reviewer", "memory_mb", target=512.0))
        registry.record_metric("reviewer", "latency_s", 10.0)  # violation
        # memory_mb has no samples -> compliant
        assert registry.get_compliance_rate("reviewer") == 0.5

    def test_get_compliance_rate_no_slos(self, registry):
        assert registry.get_compliance_rate("nobody") == 1.0

    # ── list_slos ────────────────────────────────────────────────

    def test_list_slos_all(self, registry):
        registry.register_slo(RoleSLO("r1", "m1", target=1.0))
        registry.register_slo(RoleSLO("r2", "m2", target=2.0))
        assert len(registry.list_slos()) == 2

    def test_list_slos_filtered(self, registry):
        registry.register_slo(RoleSLO("r1", "m1", target=1.0))
        registry.register_slo(RoleSLO("r2", "m2", target=2.0))
        assert len(registry.list_slos("r1")) == 1
        assert len(registry.list_slos("r3")) == 0

    # ── At-risk roles ────────────────────────────────────────────

    def test_get_at_risk_roles_none(self, registry):
        registry.register_slo(RoleSLO("reviewer", "latency", target=5.0))
        registry.record_metric("reviewer", "latency", 3.0)
        assert registry.get_at_risk_roles() == []

    def test_get_at_risk_roles_identified(self, registry):
        registry.register_slo(RoleSLO("reviewer", "latency", target=5.0))
        registry.record_metric("reviewer", "latency", 10.0)  # violation
        at_risk = registry.get_at_risk_roles()
        assert "reviewer" in at_risk

    # ── Window-based filtering ───────────────────────────────────

    def test_window_samples_excludes_old_data(self, registry):
        """Samples outside the SLO window should not count."""
        registry.register_slo(RoleSLO("reviewer", "latency", target=5.0, window_seconds=1))
        registry.record_metric("reviewer", "latency", 10.0)
        time.sleep(1.1)  # Wait for window to expire
        result = registry.check_compliance("reviewer")
        assert result["latency"]["samples"] == 0  # Old sample excluded
        assert result["latency"]["compliant"] is True

    def test_window_samples_keeps_recent_data(self, registry):
        """Samples within the SLO window should be counted."""
        registry.register_slo(RoleSLO("reviewer", "latency", target=5.0, window_seconds=3600))
        registry.record_metric("reviewer", "latency", 3.0)
        result = registry.check_compliance("reviewer")
        assert result["latency"]["samples"] == 1
