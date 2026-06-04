"""Tests for the metrics module — MetricsCollector."""

from observability.metrics import MetricsCollector


class TestMetricsCollector:
    """Verify MetricsCollector counter / gauge / histogram / export."""

    def test_counter_increment(self):
        mc = MetricsCollector()
        mc.counter("req_total", {"method": "GET"}, help_text="Total requests")
        mc.counter("req_total", {"method": "GET"})
        mc.counter("req_total", {"method": "POST"})
        out = mc.to_prometheus()
        assert '# HELP req_total Total requests' in out
        assert '# TYPE req_total counter' in out
        assert 'req_total{method="GET"} 2' in out
        assert 'req_total{method="POST"} 1' in out

    def test_counter_no_labels(self):
        mc = MetricsCollector()
        mc.counter("errors_total")
        mc.counter("errors_total")
        mc.counter("errors_total")
        out = mc.to_prometheus()
        assert 'errors_total 3' in out

    def test_gauge_set(self):
        mc = MetricsCollector()
        mc.gauge("memory_bytes", 1048576, {"host": "node1"})
        mc.gauge("memory_bytes", 2097152, {"host": "node1"})  # overwrite
        mc.gauge("memory_bytes", 524288, {"host": "node2"})
        out = mc.to_prometheus()
        assert 'memory_bytes{host="node1"} 2097152' in out
        assert 'memory_bytes{host="node2"} 524288' in out

    def test_gauge_overwrite_same_labels(self):
        mc = MetricsCollector()
        mc.gauge("cpu_pct", 45.0)
        mc.gauge("cpu_pct", 78.5)  # same label set (empty) → overwrite
        out = mc.to_prometheus()
        lines = [x for x in out.splitlines() if x and not x.startswith("#")]
        # Only one value line for cpu_pct
        assert len(lines) == 1
        assert 'cpu_pct 78' in lines[0]

    def test_histogram_observe(self):
        mc = MetricsCollector()
        mc.histogram("latency_ms", 12.5, help_text="Request latency")
        mc.histogram("latency_ms", 45.0)
        mc.histogram("latency_ms", 3.0)
        out = mc.to_prometheus()
        assert '# HELP latency_ms Request latency' in out
        assert '# TYPE latency_ms histogram' in out
        assert 'latency_ms_sum' in out
        assert 'latency_ms_count' in out
        # count should be 3
        assert 'latency_ms_count 3' in out
        # sum should be 12.5 + 45.0 + 3.0 = 60.5
        assert 'latency_ms_sum 60.5' in out

    def test_histogram_bucket_counts(self):
        mc = MetricsCollector()
        # All values ≤ 0.005 — they all land in the first (le=0.005) bucket
        for v in [0.001, 0.002, 0.003, 0.004, 0.005]:
            mc.histogram("fast", v)
        out = mc.to_prometheus()
        assert 'fast_bucket{le="0.005"} 5' in out
        assert 'fast_count 5' in out

    def test_histogram_inf_bucket(self):
        mc = MetricsCollector()
        mc.histogram("h", 5.0)
        mc.histogram("h", 500.0)
        out = mc.to_prometheus()
        # +Inf bucket should equal count
        assert 'h_bucket{le="+Inf"} 2' in out
        assert 'h_count 2' in out

    def test_export_empty(self):
        mc = MetricsCollector()
        out = mc.to_prometheus()
        assert out == "\n"

    def test_export_multiple_metric_types(self):
        mc = MetricsCollector()
        mc.counter("hits", help_text="Hit count")
        mc.gauge("temp", 36.6)
        mc.histogram("dur", 1.0)
        out = mc.to_prometheus()
        assert '# HELP hits' in out
        assert '# TYPE hits counter' in out
        assert '# HELP temp' in out
        assert '# TYPE temp gauge' in out
        assert '# HELP dur' in out
        assert '# TYPE dur histogram' in out

    def test_reset_by_reinstantiation(self):
        mc = MetricsCollector()
        mc.counter("c", help_text="count")
        mc.counter("c")
        assert 'c 2' in mc.to_prometheus()
        # Simulate reset with a fresh instance
        mc2 = MetricsCollector()
        assert mc2.to_prometheus() == "\n"

    def test_labels_key_order_irrelevant(self):
        mc = MetricsCollector()
        mc.counter("rpc", {"a": "1", "b": "2"})
        mc.counter("rpc", {"b": "2", "a": "1"})  # same labels, different order
        out = mc.to_prometheus()
        # Should be 2, not separate entries
        assert 'rpc{a="1",b="2"} 2' in out

    def test_counter_with_help_not_overwritten(self):
        mc = MetricsCollector()
        mc.counter("c", {}, help_text="first help")
        mc.counter("c", {}, help_text="second help")  # entry already exists
        out = mc.to_prometheus()
        # HELP line should still be "first help"
        assert '# HELP c first help' in out

    def test_gauge_nan_inf_handling(self):
        mc = MetricsCollector()
        mc.gauge("inf_g", float("inf"))
        mc.gauge("neg_inf_g", float("-inf"))
        mc.gauge("nan_g", float("nan"))
        out = mc.to_prometheus()
        assert 'inf_g +Inf' in out
        assert 'neg_inf_g -Inf' in out
        assert 'nan_g Nan' in out
