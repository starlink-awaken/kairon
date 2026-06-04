"""Tests for the alerts module — AlertManager, AlertRule, Alert."""

import pytest

from observability.alerts import Alert, AlertManager, AlertRule


class TestAlertRule:
    """Verify AlertRule creation and validation."""

    def test_valid_severities(self):
        for sev in ("info", "warning", "critical"):
            rule = AlertRule("test", "cpu > 90", severity=sev)
            assert rule.severity == sev

    def test_invalid_severity(self):
        with pytest.raises(ValueError, match="Unknown severity"):
            AlertRule("test", "cpu > 90", severity="unknown")

    def test_default_severity(self):
        rule = AlertRule("test", "cpu > 90")
        assert rule.severity == "warning"

    def test_rule_repr(self):
        rule = AlertRule("high-latency", "p99_ms > 500", "critical")
        assert rule.name == "high-latency"
        assert rule.condition == "p99_ms > 500"
        assert rule.severity == "critical"


class TestAlertFiring:
    """Verify that AlertManager correctly evaluates conditions and fires alerts."""

    def test_gt_condition_fires(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-cpu", "cpu > 80", "critical"))
        alerts = mgr.check({"cpu": 95.0}, service="api")
        assert len(alerts) == 1
        a = alerts[0]
        assert a.rule_name == "high-cpu"
        assert a.severity == "critical"
        assert a.service == "api"
        assert a.metric == "cpu"
        assert a.current_value == 95.0
        assert "high-cpu" in a.message
        assert "CRITICAL" in a.message

    def test_gt_condition_does_not_fire(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-cpu", "cpu > 80"))
        alerts = mgr.check({"cpu": 50.0})
        assert len(alerts) == 0

    def test_lt_condition_fires(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("low-mem", "memory_mb < 256"))
        alerts = mgr.check({"memory_mb": 128.0})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "low-mem"

    def test_lt_condition_does_not_fire(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("low-mem", "memory_mb < 256"))
        alerts = mgr.check({"memory_mb": 512.0})
        assert len(alerts) == 0

    def test_eq_condition_fires(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("zero-errors", "errors == 0"))
        alerts = mgr.check({"errors": 0.0})
        assert len(alerts) == 1

    def test_eq_condition_does_not_fire(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("zero-errors", "errors == 0"))
        alerts = mgr.check({"errors": 1.0})
        assert len(alerts) == 0

    def test_gte_condition(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-latency", "p99_ms >= 500"))
        assert len(mgr.check({"p99_ms": 500.0})) == 1
        assert len(mgr.check({"p99_ms": 499.99})) == 0

    def test_lte_condition(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("low-rate", "rate <= 10"))
        assert len(mgr.check({"rate": 10.0})) == 1
        assert len(mgr.check({"rate": 10.01})) == 0

    def test_ne_condition(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("not-zero", "val != 0"))
        assert len(mgr.check({"val": 1.0})) == 1
        assert len(mgr.check({"val": 0.0})) == 0

    def test_multiple_rules_all_fire(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-cpu", "cpu > 80"))
        mgr.add_rule(AlertRule("high-mem", "mem > 90"))
        alerts = mgr.check({"cpu": 95.0, "mem": 95.0})
        assert len(alerts) == 2

    def test_multiple_rules_some_fire(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-cpu", "cpu > 80"))
        mgr.add_rule(AlertRule("high-mem", "mem > 90"))
        alerts = mgr.check({"cpu": 95.0, "mem": 50.0})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "high-cpu"

    def test_no_metrics_no_fire(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-cpu", "cpu > 80"))
        alerts = mgr.check({})
        assert len(alerts) == 0

    def test_missing_metric_does_not_fire(self):
        """Missing metric should not fire — _eval_condition returns False."""
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-cpu", "cpu > 80"))
        alerts = mgr.check({"mem": 90.0})
        assert len(alerts) == 0


class TestAlertResolve:
    """Test that alerts are resolved when conditions are no longer met."""

    def test_resolve_pattern(self):
        """AlertManager is stateless — check returns alerts for current metrics only."""
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-cpu", "cpu > 80"))
        # Initially firing
        assert len(mgr.check({"cpu": 95.0})) == 1
        # Resolved — condition no longer met
        assert len(mgr.check({"cpu": 50.0})) == 0


class TestSilentRules:
    """Rules that don't match or have missing metrics are effectively silent."""

    def test_rule_silent_when_condition_not_met(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("silent", "val > 100"))
        mgr.add_rule(AlertRule("loud", "val > 10"))
        alerts = mgr.check({"val": 50.0})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "loud"

    def test_malformed_rule_is_silent(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("bad", "invalid condition ! @#"))
        alerts = mgr.check({"val": 1.0})
        # Malformed rules are skipped gracefully (no crash, no alert)
        assert len(alerts) == 0

    def test_mixed_valid_and_invalid_rules(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("good", "cpu > 50"))
        mgr.add_rule(AlertRule("bad", "cpu >>> 50??"))
        mgr.add_rule(AlertRule("also-good", "mem < 90"))
        alerts = mgr.check({"cpu": 80.0, "mem": 95.0})
        # good fires, bad skipped, also-good fires (mem=95 > 90? No, mem < 90 is false, so no)
        # Wait: mem < 90 with mem=95 is False, so no alert from also-good
        assert len(alerts) == 1
        assert alerts[0].rule_name == "good"


class TestAlertDataclass:
    """Verify the Alert dataclass fields."""

    def test_alert_creation(self):
        a = Alert(
            rule_name="test",
            service="svc",
            metric="cpu",
            current_value=95.0,
            severity="critical",
            message="CRITICAL: cpu=95.0 > 80",
        )
        assert a.rule_name == "test"
        assert a.service == "svc"
        assert a.metric == "cpu"
        assert a.current_value == 95.0
        assert a.severity == "critical"
        assert "CRITICAL" in a.message
        assert a.fired_at  # not empty

    def test_alert_default_fired_at(self):
        a = Alert(
            rule_name="r",
            service="s",
            metric="m",
            current_value=1.0,
            severity="info",
            message="test",
        )
        from datetime import datetime
        # Should be an ISO-formatted string
        datetime.fromisoformat(a.fired_at)  # does not raise
