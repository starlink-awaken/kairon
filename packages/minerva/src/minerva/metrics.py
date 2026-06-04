from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Metrics ≡ Module
# 内涵 ≝ {Metrics}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Metrics)}
# 功能 ⊢ {Init_Metrics, Execute_Metrics, Validate_Metrics}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
Monitoring metrics export for D-Harvest components

Exports metrics in Prometheus format for monitoring and alerting.
Metrics include insert latency, queue sizes, error rates, and harvest counts.
"""
import time
from dataclasses import dataclass, field
from pathlib import Path

# Component identifier
COMPONENT = "d_harvest"


@dataclass
class Metric:
    """Prometheus metric"""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    help_text: str = ""
    metric_type: str = "gauge"  # gauge, counter, histogram

    def to_prometheus(self) -> str:
        """Convert to Prometheus format"""
        # Add HELP and TYPE lines
        lines = []

        if self.help_text:
            lines.append(f"# HELP {COMPONENT}_{self.name} {self.help_text}")

        lines.append(f"# TYPE {COMPONENT}_{self.name} {self.metric_type}")

        # Format labels
        if self.labels:
            label_str = "{" + ", ".join(f'{k}="{v}"' for k, v in self.labels.items()) + "}"
        else:
            label_str = ""

        lines.append(f"{COMPONENT}_{self.name}{label_str} {self.value}")

        return "\n".join(lines)


class MetricsCollector:
    """
    Collect and export metrics for monitoring

    Tracks harvest performance, queue sizes, error rates, etc.
    """

    def __init__(self) -> None:
        """Initialize metrics collector"""
        self._metrics: dict[str, float] = {}
        self._start_time = time.time()

    def inc(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """
        Increment a counter metric

        Args:
            name: Metric name
            value: Increment value
            labels: Optional labels
        """
        key = self._make_key(name, labels)
        self._metrics[key] = self._metrics.get(key, 0.0) + value

    def set(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """
        Set a gauge metric

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels
        """
        key = self._make_key(name, labels)
        self._metrics[key] = value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """
        Observe a histogram value

        Args:
            name: Metric name
            value: Observed value
            labels: Optional labels
        """
        key = self._make_key(name, labels)
        # For simplicity, just store sum and count
        count_key = f"{key}_count"
        sum_key = f"{key}_sum"

        self._metrics[count_key] = self._metrics.get(count_key, 0.0) + 1
        self._metrics[sum_key] = self._metrics.get(sum_key, 0.0) + value

    def _make_key(self, name: str, labels: dict[str, str] | None) -> str:
        """Create unique key from name and labels"""
        if not labels:
            return name

        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_metric(self, name: str, labels: dict[str, str] | None = None) -> float | None:
        """
        Get metric value

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Metric value if exists
        """
        key = self._make_key(name, labels)
        return self._metrics.get(key)

    def export_prometheus(self) -> str:
        """
        Export all metrics in Prometheus format

        Returns:
            Prometheus text format string
        """
        lines = []

        for key, value in self._metrics.items():
            # Parse key back into name and labels
            if "{" in key:
                name, labels_part = key.split("{", 1)
                labels_part = labels_part.rstrip("}")
                labels = dict(label.split("=") for label in labels_part.split(","))
                # Remove quotes from label values
                labels = {k: v.strip('"') for k, v in labels.items()}
            else:
                name = key
                labels = {}

            # Determine metric type based on name
            if name.endswith("_count") or name.endswith("_total"):
                metric_type = "counter"
            elif name.endswith("_sum"):
                continue  # Skip internal sum metrics
            else:
                metric_type = "gauge"

            metric = Metric(name=name, value=value, labels=labels, metric_type=metric_type)

            lines.append(metric.to_prometheus())

        return "\n\n".join(lines)

    def save_to_file(self, path: Path) -> bool:
        """
        Export metrics to file for Prometheus to scrape

        Args:
            path: Output file path

        Returns:
            True if write successful
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w") as f:
                f.write(self.export_prometheus())

            return True

        except OSError:
            return False


class HarvestMetrics:
    """
    Domain-specific metrics for harvest operations

    Predefined metrics for common harvest operations.
    """

    def __init__(self, collector: MetricsCollector | None = None) -> None:
        """
        Initialize harvest metrics

        Args:
            collector: Optional metrics collector (creates new if None)
        """
        self.collector = collector or MetricsCollector()

    def harvest_started(self, source_id: str) -> None:
        """Record harvest start"""
        self.collector.inc("harvests_started_total", labels={"source_id": source_id})

    def harvest_completed(self, source_id: str, items_count: int, duration_ms: float) -> None:
        """Record harvest completion"""
        self.collector.inc("harvests_completed_total", labels={"source_id": source_id})

        self.collector.observe("harvest_duration_ms", duration_ms, labels={"source_id": source_id})

        self.collector.inc("items_harvested_total", items_count, labels={"source_id": source_id})

    def harvest_failed(self, source_id: str, error_type: str) -> None:
        """Record harvest failure"""
        self.collector.inc("harvests_failed_total", labels={"source_id": source_id, "error_type": error_type})

    def insert_latency(self, source_id: str, latency_ms: float) -> None:
        """Record FactGraph insert latency"""
        self.collector.observe("insert_latency_ms", latency_ms, labels={"source_id": source_id})

    def queue_size(self, queue_name: str, size: int) -> None:
        """Record queue size"""
        self.collector.set(f"{queue_name}_queue_size", size, labels={"queue": queue_name})

    def quality_gate_pass(self, source_id: str, score: float) -> None:
        """Record quality gate pass"""
        self.collector.inc("quality_gate_passed_total", labels={"source_id": source_id})

    def quality_gate_fail(self, source_id: str, score: float, reason: str) -> None:
        """Record quality gate failure"""
        self.collector.inc("quality_gate_failed_total", labels={"source_id": source_id, "reason": reason})
