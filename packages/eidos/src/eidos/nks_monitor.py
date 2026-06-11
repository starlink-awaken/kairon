# ---
# domain: D-Memory
# layer: organ
# status: active
# ---
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "Must provide production monitoring for NKS system"
Summary: "NKSMonitor - Production monitoring, health checks, and metrics for NKS"
Tags:
- nks
- monitoring
- metrics
- health-check
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Monitor ≡ Monitor
# 内涵 ≝ {Monitor}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, Monitor)}
# 功能 ⊢ {Init_Monitor, Execute_Monitor, Validate_Monitor}
# =============================================================================

_log = logging.getLogger(__name__)

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class ComponentHealth:
    """Health status of an NKS component."""

    component: str
    status: str  # "healthy", "degraded", "unhealthy"
    last_check: float
    response_time_ms: float
    error_count: int
    details: dict = field(default_factory=dict)


@dataclass
class NKSMetrics:
    """Metrics snapshot for NKS system."""

    timestamp: float

    # Graph metrics
    entity_count: int = 0
    relation_count: int = 0
    candidate_count: int = 0

    # Performance metrics
    avg_query_time_ms: float = 0.0
    avg_extraction_time_ms: float = 0.0
    cache_hit_rate: float = 0.0

    # EU metrics
    eu_consumed_1h: float = 0.0
    eu_consumed_24h: float = 0.0

    # Error metrics
    error_rate_1h: float = 0.0
    failed_extractions: int = 0
    failed_queries: int = 0

    # System metrics
    memory_usage_mb: float = 0.0
    cpu_percent: float = 0.0


@dataclass
class Alert:
    """Alert notification."""

    level: str  # "info", "warning", "critical"
    component: str
    message: str
    timestamp: float
    value: float
    threshold: float

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "component": self.component,
            "message": self.message,
            "timestamp": self.timestamp,
            "value": self.value,
            "threshold": self.threshold,
        }


class NKSMonitor:
    """
    Production monitoring for NKS system.

    Provides health checks, metrics collection, alerting,
    and dashboard data export.
    """

    def __init__(
        self,
        graph_store: Any,
        query_engine: Any,
        check_interval: int = 60,
        metrics_history_size: int = 1440,  # 24h at 1min intervals
    ) -> None:
        self.status = "active"

        self.store = graph_store
        self.engine = query_engine
        self.check_interval = check_interval
        self.metrics_history: deque[NKSMetrics] = deque(maxlen=metrics_history_size)

        # Operation counters for metrics
        self._operation_counts: dict[str, int] = {"extract": 0, "query": 0, "index": 0}
        self._operation_times: dict[str, list[float]] = {"extract": [], "query": [], "index": []}
        self._eu_consumed: list[tuple[float, float]] = []  # (timestamp, amount)
        self._errors: deque[tuple[float, str]] = deque(maxlen=1000)  # (timestamp, operation)

        # Alert handlers
        self._alert_handlers: list[Callable[[Alert], None]] = []

        # Lock for thread safety
        self._lock = threading.RLock()

        self.logger = logging.getLogger(__name__)
        self._deduct_metabolic_tax(amount=5.0)

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount

    def add_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add an alert handler."""
        with self._lock:
            self._alert_handlers.append(handler)

    def _send_alert(self, alert: Alert) -> None:
        """Send alert to all handlers."""
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except (TypeError, ValueError, AttributeError, RuntimeError) as e:
                if hasattr(self, "logger"):
                    self.logger.error(f"Alert handler failed: {e}")

    def check_health(self) -> dict[str, ComponentHealth]:
        """
        Check health of all NKS components.

        Returns:
            Dict mapping component name to ComponentHealth
        """
        health = {}

        # Check GraphStore
        start = time.time()
        try:
            stats = self.store.get_graph_stats()
            health["graph_store"] = ComponentHealth(
                component="graph_store",
                status="healthy",
                last_check=time.time(),
                response_time_ms=(time.time() - start) * 1000,
                error_count=0,
                details=stats,
            )
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            health["graph_store"] = ComponentHealth(
                component="graph_store",
                status="unhealthy",
                last_check=time.time(),
                response_time_ms=(time.time() - start) * 1000,
                error_count=1,
                details={"error": str(e)},
            )

        # Check QueryEngine
        start = time.time()
        try:
            # Try a simple query
            _ = self.engine.get_centrality_scores(top_n=1)
            health["query_engine"] = ComponentHealth(
                component="query_engine",
                status="healthy",
                last_check=time.time(),
                response_time_ms=(time.time() - start) * 1000,
                error_count=0,
                details={},
            )
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            health["query_engine"] = ComponentHealth(
                component="query_engine",
                status="unhealthy",
                last_check=time.time(),
                response_time_ms=(time.time() - start) * 1000,
                error_count=1,
                details={"error": str(e)},
            )

        # Check overall status
        healthy_count = sum(1 for h in health.values() if h.status == "healthy")
        if healthy_count < len(health):
            health["overall"] = ComponentHealth(
                component="overall",
                status="degraded" if healthy_count > 0 else "unhealthy",
                last_check=time.time(),
                response_time_ms=0,
                error_count=len(health) - healthy_count,
                details={"healthy_components": healthy_count, "total": len(health)},
            )
        else:
            health["overall"] = ComponentHealth(
                component="overall",
                status="healthy",
                last_check=time.time(),
                response_time_ms=0,
                error_count=0,
                details={"healthy_components": healthy_count, "total": len(health)},
            )

        return health

    def collect_metrics(self) -> NKSMetrics:
        """Collect current metrics snapshot."""
        now = time.time()

        with self._lock:
            # Graph stats
            try:
                stats = self.store.get_graph_stats()
                entity_count = stats.get("entity_count", 0)
                relation_count = stats.get("relation_count", 0)
                candidate_count = stats.get("candidate_entity_count", 0)
            except (TypeError, ValueError, AttributeError, RuntimeError):
                entity_count = relation_count = candidate_count = 0

            # Performance metrics (last hour)
            hour_ago = now - 3600
            recent_query_times = [t for t in self._operation_times.get("query", []) if t > hour_ago]
            avg_query_time = sum(recent_query_times) / len(recent_query_times) if recent_query_times else 0

            recent_extract_times = [t for t in self._operation_times.get("extract", []) if t > hour_ago]
            avg_extract_time = sum(recent_extract_times) / len(recent_extract_times) if recent_extract_times else 0

            # EU consumption
            eu_1h = sum(amount for ts, amount in self._eu_consumed if ts > hour_ago)
            day_ago = now - 86400
            eu_24h = sum(amount for ts, amount in self._eu_consumed if ts > day_ago)

            # Error rate (last hour)
            recent_errors = sum(1 for ts, _ in self._errors if ts > hour_ago)
            total_ops = sum(self._operation_counts.values())
            error_rate = recent_errors / max(total_ops, 1)

            # System metrics
            memory_mb: float = 0
            cpu_percent: float = 0
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    cpu_percent = process.cpu_percent(interval=0.1)
                except (TypeError, ValueError, AttributeError, OSError):
                    pass

            metrics = NKSMetrics(
                timestamp=now,
                entity_count=entity_count,
                relation_count=relation_count,
                candidate_count=candidate_count,
                avg_query_time_ms=avg_query_time,
                avg_extraction_time_ms=avg_extract_time,
                cache_hit_rate=0.0,  # Would need cache integration
                eu_consumed_1h=eu_1h,
                eu_consumed_24h=eu_24h,
                error_rate_1h=error_rate,
                failed_extractions=sum(1 for ts, op in self._errors if op == "extract"),
                failed_queries=sum(1 for ts, op in self._errors if op == "query"),
                memory_usage_mb=memory_mb,
                cpu_percent=cpu_percent,
            )

            self.metrics_history.append(metrics)
            return metrics

    def record_operation(self, operation: str, duration_ms: float, success: bool, eu_consumed: float) -> None:
        """Record operation for metrics."""
        with self._lock:
            if operation in self._operation_counts:
                self._operation_counts[operation] += 1
                self._operation_times[operation].append(duration_ms)

            self._eu_consumed.append((time.time(), eu_consumed))

            if not success:
                self._errors.append((time.time(), operation))

    def check_alerts(self) -> list[Alert]:
        """Check for alert conditions."""
        alerts = []
        metrics = self.collect_metrics()

        # Alert thresholds
        thresholds = {
            "error_rate": 0.05,  # 5%
            "query_latency": 100,  # ms
            "cache_hit_rate": 0.5,  # 50%
            "eu_hourly": 1000,
            "entity_count": 100000,
        }

        # Check error rate
        if metrics.error_rate_1h > thresholds["error_rate"]:
            alerts.append(
                Alert(
                    level="critical",
                    component="nks",
                    message=f"Error rate is {metrics.error_rate_1h:.1%}, threshold is {thresholds['error_rate']:.1%}",
                    timestamp=time.time(),
                    value=metrics.error_rate_1h,
                    threshold=thresholds["error_rate"],
                )
            )

        # Check query latency
        if metrics.avg_query_time_ms > thresholds["query_latency"]:
            alerts.append(
                Alert(
                    level="warning",
                    component="query_engine",
                    message=f"Average query latency is {metrics.avg_query_time_ms:.1f}ms",
                    timestamp=time.time(),
                    value=metrics.avg_query_time_ms,
                    threshold=thresholds["query_latency"],
                )
            )

        # Check cache hit rate
        if metrics.cache_hit_rate < thresholds["cache_hit_rate"]:
            alerts.append(
                Alert(
                    level="warning",
                    component="cache",
                    message=f"Cache hit rate is {metrics.cache_hit_rate:.1%}",
                    timestamp=time.time(),
                    value=metrics.cache_hit_rate,
                    threshold=thresholds["cache_hit_rate"],
                )
            )

        # Check EU consumption
        if metrics.eu_consumed_1h > thresholds["eu_hourly"]:
            alerts.append(
                Alert(
                    level="warning",
                    component="economy",
                    message=f"EU consumption is {metrics.eu_consumed_1h:.1f}/hour",
                    timestamp=time.time(),
                    value=metrics.eu_consumed_1h,
                    threshold=thresholds["eu_hourly"],
                )
            )

        # Check entity count
        if metrics.entity_count > thresholds["entity_count"]:
            alerts.append(
                Alert(
                    level="info",
                    component="graph_store",
                    message=f"Entity count is {metrics.entity_count}",
                    timestamp=time.time(),
                    value=metrics.entity_count,
                    threshold=thresholds["entity_count"],
                )
            )

        # Send alerts
        for alert in alerts:
            self._send_alert(alert)

        return alerts

    def get_dashboard_data(self) -> dict:
        """Export data for dashboard."""
        health = self.check_health()
        metrics = self.collect_metrics()

        return {
            "timestamp": time.time(),
            "health": {
                name: {
                    "status": h.status,
                    "response_time_ms": h.response_time_ms,
                    "error_count": h.error_count,
                }
                for name, h in health.items()
            },
            "metrics": {
                "entity_count": metrics.entity_count,
                "relation_count": metrics.relation_count,
                "avg_query_time_ms": metrics.avg_query_time_ms,
                "cache_hit_rate": metrics.cache_hit_rate,
                "eu_consumed_1h": metrics.eu_consumed_1h,
                "error_rate_1h": metrics.error_rate_1h,
                "memory_usage_mb": metrics.memory_usage_mb,
            },
            "history": [
                {
                    "timestamp": m.timestamp,
                    "entity_count": m.entity_count,
                    "avg_query_time_ms": m.avg_query_time_ms,
                }
                for m in list(self.metrics_history)[-60:]  # Last hour
            ],
        }

    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        metrics = self.collect_metrics()
        lines = []

        lines.append("# HELP nks_entity_count Number of entities in the graph")
        lines.append("# TYPE nks_entity_count gauge")
        lines.append(f"nks_entity_count {metrics.entity_count}")

        lines.append("# HELP nks_relation_count Number of relations in the graph")
        lines.append("# TYPE nks_relation_count gauge")
        lines.append(f"nks_relation_count {metrics.relation_count}")

        lines.append("# HELP nks_query_duration_ms Average query duration")
        lines.append("# TYPE nks_query_duration_ms gauge")
        lines.append(f"nks_query_duration_ms {metrics.avg_query_time_ms}")

        lines.append("# HELP nks_cache_hit_rate Cache hit rate")
        lines.append("# TYPE nks_cache_hit_rate gauge")
        lines.append(f"nks_cache_hit_rate {metrics.cache_hit_rate}")

        lines.append("# HELP nks_error_rate Error rate (1h)")
        lines.append("# TYPE nks_error_rate gauge")
        lines.append(f"nks_error_rate {metrics.error_rate_1h}")

        lines.append("# HELP nks_eu_consumed_1h EU consumed in last hour")
        lines.append("# TYPE nks_eu_consumed_1h gauge")
        lines.append(f"nks_eu_consumed_1h {metrics.eu_consumed_1h}")

        return "\n".join(lines)

    def generate_report(self, period: str = "24h") -> dict:
        """Generate health and performance report."""
        now = time.time()

        # Determine time window
        if period == "1h":
            window = 3600
        elif period == "24h":
            window = 86400
        elif period == "7d":
            window = 7 * 86400
        else:
            window = 86400

        cutoff = now - window

        # Get historical metrics in window
        with self._lock:
            relevant_metrics = [m for m in self.metrics_history if m.timestamp > cutoff]

        if not relevant_metrics:
            return {"error": f"No metrics available for period {period}"}

        # Calculate aggregates
        avg_entities = sum(m.entity_count for m in relevant_metrics) / len(relevant_metrics)
        avg_query_time = sum(m.avg_query_time_ms for m in relevant_metrics) / len(relevant_metrics)
        max_query_time = max(m.avg_query_time_ms for m in relevant_metrics)
        total_eu = sum(m.eu_consumed_1h for m in relevant_metrics)

        # Health status
        health = self.check_health()

        return {
            "period": period,
            "generated_at": now,
            "summary": {
                "avg_entities": round(avg_entities, 0),
                "avg_query_time_ms": round(avg_query_time, 2),
                "max_query_time_ms": round(max_query_time, 2),
                "total_eu_consumed": round(total_eu, 2),
                "data_points": len(relevant_metrics),
            },
            "health": {name: h.status for name, h in health.items()},
            "current_metrics": {
                "entity_count": relevant_metrics[-1].entity_count if relevant_metrics else 0,
                "relation_count": relevant_metrics[-1].relation_count if relevant_metrics else 0,
                "error_rate": relevant_metrics[-1].error_rate_1h if relevant_metrics else 0,
            },
        }

    def run_monitoring_loop(self, stop_event: threading.Event | None = None) -> None:
        """Run continuous monitoring (for daemon mode)."""
        self.logger.info("Starting NKS monitoring loop")

        while stop_event is None or not stop_event.is_set():
            try:
                # Collect metrics
                self.collect_metrics()

                # Check health
                health = self.check_health()
                unhealthy = [h for h in health.values() if h.status != "healthy"]
                if unhealthy:
                    self.logger.warning(f"Unhealthy components: {[h.component for h in unhealthy]}")

                # Check alerts
                alerts = self.check_alerts()
                for alert in alerts:
                    self.logger.warning(f"Alert [{alert.level}]: {alert.message}")

            except (TypeError, ValueError, AttributeError, RuntimeError) as e:
                self.logger.error(f"Monitoring error: {e}")

            # Sleep until next check
            if stop_event:
                stop_event.wait(self.check_interval)
            else:
                time.sleep(self.check_interval)

    def ping(self) -> bool:
        """Health check."""
        try:
            health = self.check_health()
            return health.get("overall", ComponentHealth("overall", "unhealthy", 0, 0, 0)).status == "healthy"
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return False


# BOS-URI Handler
class NKSMonitorURIHandler:
    """URI handler for NKS monitor."""

    def __init__(self, monitor: NKSMonitor) -> None:
        super().__init__()
        self.monitor = monitor

    def handle(self, uri: str, params: dict) -> dict:
        """Handle BOS-URI requests."""
        action = uri.split("/")[-1]

        if action == "health":
            health = self.monitor.check_health()
            return {name: {"status": h.status, "details": h.details} for name, h in health.items()}

        elif action == "metrics":
            metrics = self.monitor.collect_metrics()
            return {
                "entity_count": metrics.entity_count,
                "relation_count": metrics.relation_count,
                "avg_query_time_ms": metrics.avg_query_time_ms,
                "eu_consumed_1h": metrics.eu_consumed_1h,
            }

        elif action == "report":
            period = params.get("period", "24h")
            return self.monitor.generate_report(period)

        elif action == "prometheus":
            return {"metrics": self.monitor.export_prometheus_metrics()}

        else:
            return {"error": f"Unknown action: {action}"}
