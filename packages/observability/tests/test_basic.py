"""Tests for the observability package."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestSLOImports:
    def test_import_slo_status(self):
        from observability.slo import SLOStatus

        s = SLOStatus(p99_ms=100.0, availability_pct=99.9, window_hours=24.0)
        assert s.p99_ms == 100.0
        assert s.availability_pct == 99.9
        assert s.window_hours == 24.0

    def test_import_slo_tracker(self):
        from observability.slo import SLOTracker

        t = SLOTracker()
        assert t is not None


class TestAlertImports:
    def test_import_alert_rule(self):
        from observability.alerts import AlertRule

        r = AlertRule(name="test", condition="p99_ms > 500", severity="warning")
        assert r.name == "test"
        assert r.condition == "p99_ms > 500"
        assert r.severity == "warning"

    def test_import_alert(self):
        from observability.alerts import Alert

        a = Alert(
            rule_name="test", service="s", metric="m",
            current_value=1.0, severity="info", message="ok",
        )
        assert a.rule_name == "test"

    def test_import_alert_manager(self):
        from observability.alerts import AlertManager

        m = AlertManager()
        assert m is not None


class TestMetricsImports:
    def test_import_metrics_collector(self):
        from observability.metrics import MetricsCollector

        m = MetricsCollector()
        assert m is not None


class TestSLOTracker:
    def test_track_and_get_slo_empty(self):
        from observability.slo import SLOTracker

        t = SLOTracker()
        s = t.get_slo("svc", "m")
        assert s.p99_ms == 0.0
        assert s.availability_pct == 100.0

    def test_track_and_get_slo_basic(self):
        from observability.slo import SLOTracker

        t = SLOTracker()
        for v in [10, 20, 30, 500, 600]:
            t.track("api", "latency_ms", float(v))
        s = t.get_slo("api", "latency_ms", threshold_ms=499)
        assert s.p99_ms == 600.0
        assert s.availability_pct == 60.0  # 3/5 <= 499

    def test_clear_all(self):
        from observability.slo import SLOTracker

        t = SLOTracker()
        t.track("s", "m", 1.0)
        assert t.clear() == 1
        assert t.clear() == 0

    def test_clear_scoped(self):
        from observability.slo import SLOTracker

        t = SLOTracker()
        t.track("a", "m", 1.0)
        t.track("b", "m", 2.0)
        assert t.clear(service="a") == 1
        s = t.get_slo("a", "m")
        assert s.p99_ms == 0.0
        s2 = t.get_slo("b", "m")
        assert s2.p99_ms == 2.0


class TestAlertManager:
    def test_add_rule_and_check_no_alert(self):
        from observability.alerts import AlertManager, AlertRule

        m = AlertManager()
        m.add_rule(AlertRule("ok", "p99_ms > 500", "warning"))
        alerts = m.check({"p99_ms": 200})
        assert len(alerts) == 0

    def test_check_fires_alert(self):
        from observability.alerts import AlertManager, AlertRule

        m = AlertManager()
        m.add_rule(AlertRule("high", "p99_ms > 500", "critical"))
        alerts = m.check({"p99_ms": 999})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "high"
        assert alerts[0].severity == "critical"

    def test_check_unknown_metric_no_alert(self):
        from observability.alerts import AlertManager, AlertRule

        m = AlertManager()
        m.add_rule(AlertRule("x", "missing > 10"))
        alerts = m.check({"other": 5})
        assert len(alerts) == 0

    def test_invalid_severity(self):
        import pytest

        from observability.alerts import AlertRule

        with pytest.raises(ValueError):
            AlertRule(name="x", condition="a > 1", severity="unknown")


class TestMetricsCollector:
    def test_counter_increment(self):
        from observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.counter("req_total", {"method": "GET"})
        mc.counter("req_total", {"method": "GET"})
        mc.counter("req_total", {"method": "POST"})
        out = mc.to_prometheus()
        assert 'req_total{method="GET"} 2' in out
        assert 'req_total{method="POST"} 1' in out

    def test_gauge(self):
        from observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.gauge("mem", 1024.0)
        mc.gauge("mem", 2048.0)  # overwrites
        out = mc.to_prometheus()
        assert "mem 2048" in out

    def test_histogram(self):
        from observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.histogram("latency", 10.0)
        mc.histogram("latency", 200.0)
        out = mc.to_prometheus()
        assert "# TYPE latency histogram" in out
        assert "latency_sum 210" in out
        assert "latency_count 2" in out

    def test_prometheus_format_header(self):
        from observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.counter("hello", help_text="a greeting counter")
        out = mc.to_prometheus()
        assert '# HELP hello a greeting counter' in out
        assert "# TYPE hello counter" in out

    def test_labels_sorting(self):
        from observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.gauge("g", 5.0, {"b": "2", "a": "1"})
        out = mc.to_prometheus()
        # Labels must be sorted alphabetically
        assert 'g{a="1",b="2"} 5' in out


class TestPackageInitExport:
    def test_top_level_exports(self):
        from observability import (
            Alert,
            AlertManager,
            AlertRule,
            MetricsCollector,
            SLOStatus,
            SLOTracker,
        )
        assert Alert is not None
        assert AlertManager is not None
        assert AlertRule is not None
        assert MetricsCollector is not None
        assert SLOStatus is not None
        assert SLOTracker is not None
