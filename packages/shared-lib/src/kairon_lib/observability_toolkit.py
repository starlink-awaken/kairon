"""Observability toolkit: tracing, event emitter, health checks, logger, metrics.

Migrated from agentmesh toolkit/src/observability/ (Tracer, EventEmitter,
HealthCheck, Logger, Metrics, types).
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

LogLevel = str  # "debug" | "info" | "warn" | "error"
HealthStatus = str  # "healthy" | "degraded" | "unhealthy"
MetricType = str  # "counter" | "gauge" | "histogram"


# ----- EventEmitter -----

EventListener = Callable[..., None]


class EventEmitter:
    """Lightweight async event emitter with priority support."""

    def __init__(self, max_listeners: int = 10) -> None:
        self._events: dict[str, list[tuple[EventListener, bool, int]]] = {}
        self._max = max_listeners

    def on(self, event: str, handler: EventListener, priority: int = 0) -> None:
        self._events.setdefault(event, []).append((handler, False, priority))
        self._events[event].sort(key=lambda x: x[2], reverse=True)
        self._warn_leak(event)

    def once(self, event: str, handler: EventListener, priority: int = 0) -> None:
        self._events.setdefault(event, []).append((handler, True, priority))
        self._events[event].sort(key=lambda x: x[2], reverse=True)

    def off(self, event: str, handler: EventListener | None = None) -> None:
        if handler is None:
            self._events.pop(event, None)
            return
        self._events[event] = [(h, o, p) for h, o, p in self._events.get(event, []) if h != handler]

    def emit(self, event: str, *args: Any) -> None:
        for handler, once, _ in list(self._events.get(event, [])):
            try:
                handler(*args)
            except Exception:
                pass
            if once:
                self.off(event, handler)

    async def emit_async(self, event: str, *args: Any) -> None:
        for handler, once, _ in list(self._events.get(event, [])):
            try:
                result = handler(*args)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass
            if once:
                self.off(event, handler)

    def listener_count(self, event: str) -> int:
        return len(self._events.get(event, []))

    def _warn_leak(self, event: str) -> None:
        if len(self._events.get(event, [])) > self._max:
            import warnings
            warnings.warn(f"Possible EventEmitter leak: {self.listener_count(event)} {event} listeners")


# ----- Tracer -----

@dataclass
class TraceSpan:
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""
    operation: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    tags: dict[str, Any] = field(default_factory=dict)
    status: str = "unset"


class Tracer(EventEmitter):
    """Distributed tracer with span creation and propagation."""

    def __init__(self, service: str = "default", sample_rate: float = 1.0, max_spans: int = 1000) -> None:
        super().__init__()
        self._service = service
        self._rate = sample_rate
        self._max = max_spans
        self._spans: list[TraceSpan] = []
        self._active: dict[str, TraceSpan] = {}

    def start_span(self, operation: str, parent: TraceSpan | None = None) -> TraceSpan:
        now = time.time()
        span = TraceSpan(
            trace_id=parent.trace_id if parent else uuid.uuid4().hex,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=parent.span_id if parent else "",
            operation=operation,
            start_time=now,
        )
        if not parent:
            sample_hash = sum(ord(c) for c in span.trace_id) % 100
            if sample_hash / 100 >= self._rate:
                return span  # sampled out, returned but not tracked
        self._active[span.span_id] = span
        self.emit("span_start", span)
        return span

    def end_span(self, span: TraceSpan) -> None:
        now = time.time()
        span.end_time = now
        span.duration_ms = (now - span.start_time) * 1000
        self._spans.append(span)
        self._active.pop(span.span_id, None)
        if len(self._spans) > self._max:
            self._spans = self._spans[-self._max:]
        self.emit("span_end", span)

    def get_spans(self) -> list[TraceSpan]:
        return list(self._spans)

    def get_stats(self) -> dict[str, Any]:
        durations = [s.duration_ms for s in self._spans if s.duration_ms > 0]
        return {
            "total_spans": len(self._spans),
            "active_spans": len(self._active),
            "error_count": sum(1 for s in self._spans if s.status == "error"),
            "avg_duration_ms": sum(durations) / max(len(durations), 1),
        }


# ----- HealthCheck -----

@dataclass
class HealthResult:
    name: str = ""
    status: HealthStatus = "healthy"
    message: str = ""
    timestamp: float = 0.0
    duration_ms: float = 0.0


class HealthChecker(EventEmitter):
    """Register and run health checks with periodic execution."""

    def __init__(self) -> None:
        super().__init__()
        self._checks: dict[str, Callable[[], Any]] = {}
        self._results: dict[str, HealthResult] = {}
        self._interval: float = 0.0
        self._timer: asyncio.Task | None = None

    def register(self, name: str, fn: Callable[[], Any]) -> None:
        self._checks[name] = fn

    def unregister(self, name: str) -> None:
        self._checks.pop(name, None)
        self._results.pop(name, None)

    async def run_all(self) -> list[HealthResult]:
        results: list[HealthResult] = []
        for name, fn in self._checks.items():
            start = time.monotonic()
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    result = await result
                if isinstance(result, str):
                    status, msg = result, ""
                elif isinstance(result, dict):
                    status = result.get("status", "healthy")
                    msg = result.get("message", "")
                else:
                    status = "healthy" if result else "unhealthy"
                    msg = str(result)
            except Exception as e:
                status, msg = "unhealthy", str(e)
            hr = HealthResult(name=name, status=status, message=msg, timestamp=time.time(), duration_ms=(time.monotonic() - start) * 1000)
            self._results[name] = hr
            results.append(hr)
        self.emit("checks_complete", results)
        return results

    def get_status(self) -> HealthStatus:
        if not self._results:
            return "healthy"
        if any(r.status == "unhealthy" for r in self._results.values()):
            return "unhealthy"
        if any(r.status == "degraded" for r in self._results.values()):
            return "degraded"
        return "healthy"

    def get_report(self) -> dict[str, Any]:
        return {"status": self.get_status(), "checks": [vars(r) for r in self._results.values()], "timestamp": time.time()}

    def start_periodic(self, interval_s: float = 60.0) -> None:
        self._interval = interval_s
        loop = asyncio.get_event_loop()
        self._timer = loop.create_task(self._periodic())

    async def _periodic(self) -> None:
        while True:
            await self.run_all()
            await asyncio.sleep(self._interval)

    def stop_periodic(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None


# ----- Logger -----

@dataclass
class LogEntry:
    timestamp: str = ""
    level: LogLevel = "info"
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Logger(EventEmitter):
    """Structured logger with file rotation, levels, and JSON/text output."""

    def __init__(self, level: LogLevel = "info", file_path: str = "", format: str = "json") -> None:
        super().__init__()
        self._level = level
        self._file = file_path
        self._fmt = format
        self._levels = {"debug": 0, "info": 1, "warn": 2, "error": 3}

    def _should_log(self, level: LogLevel) -> bool:
        return self._levels.get(level, 0) >= self._levels.get(self._level, 0)

    def log(self, level: LogLevel, message: str, **meta: Any) -> None:
        if not self._should_log(level):
            return
        entry = LogEntry(timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()), level=level, message=message, metadata=meta)
        self.emit("log", entry)
        if self._fmt == "json":
            line = json.dumps({"timestamp": entry.timestamp, "level": entry.level, "message": entry.message, **entry.metadata})
        else:
            line = f"[{entry.timestamp}] [{entry.level.upper()}] {entry.message}"
        if self._file:
            with open(self._file, "a") as f:
                f.write(line + "\n")
        else:
            print(line)

    def debug(self, msg: str, **meta: Any) -> None:
        self.log("debug", msg, **meta)

    def info(self, msg: str, **meta: Any) -> None:
        self.log("info", msg, **meta)

    def warn(self, msg: str, **meta: Any) -> None:
        self.log("warn", msg, **meta)

    def error(self, msg: str, **meta: Any) -> None:
        self.log("error", msg, **meta)


# ----- Metrics -----

class _MetricBase:
    def __init__(self, name: str, labels: dict[str, str] | None = None) -> None:
        self.name = name
        self.labels = labels or {}
        self._timestamp = time.time()


class Counter(_MetricBase):
    def __init__(self, name: str, labels: dict[str, str] | None = None) -> None:
        super().__init__(name, labels)
        self._value: float = 0.0

    def inc(self, value: float = 1.0) -> None:
        self._value += value

    def get(self) -> dict[str, Any]:
        return {"type": "counter", "name": self.name, "value": self._value, "labels": self.labels, "timestamp": time.time()}


class Gauge(_MetricBase):
    def __init__(self, name: str, labels: dict[str, str] | None = None) -> None:
        super().__init__(name, labels)
        self._value: float = 0.0

    def set(self, value: float) -> None:
        self._value = value

    def inc(self, value: float = 1.0) -> None:
        self._value += value

    def dec(self, value: float = 1.0) -> None:
        self._value -= value

    def get(self) -> dict[str, Any]:
        return {"type": "gauge", "name": self.name, "value": self._value, "labels": self.labels, "timestamp": time.time()}


class Histogram(_MetricBase):
    def __init__(self, name: str, buckets: list[float] | None = None, labels: dict[str, str] | None = None) -> None:
        super().__init__(name, labels)
        self._buckets = sorted(buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10])
        self._values: list[float] = []
        self._count: int = 0
        self._sum: float = 0.0

    def observe(self, value: float) -> None:
        self._values.append(value)
        self._count += 1
        self._sum += value

    def get(self) -> dict[str, Any]:
        sorted_vals = sorted(self._values)
        n = len(sorted_vals)
        return {
            "type": "histogram",
            "name": self.name,
            "count": self._count,
            "sum": self._sum,
            "min": sorted_vals[0] if n else 0,
            "max": sorted_vals[-1] if n else 0,
            "avg": self._sum / max(self._count, 1),
            "p50": sorted_vals[max(0, n // 2)] if n else 0,
            "p95": sorted_vals[max(0, int(n * 0.95) - 1)] if n else 0,
            "p99": sorted_vals[max(0, int(n * 0.99) - 1)] if n else 0,
            "labels": self.labels,
            "timestamp": time.time(),
        }


class Metrics(EventEmitter):
    """Metrics registry for counters, gauges, and histograms."""

    def __init__(self, prefix: str = "") -> None:
        super().__init__()
        self._prefix = prefix
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}

    def _key(self, name: str, labels: dict[str, str] | None = None) -> str:
        lbl = json.dumps(labels or {}, sort_keys=True)
        return f"{self._prefix}{name}{lbl}"

    def counter(self, name: str, labels: dict[str, str] | None = None) -> Counter:
        k = self._key(name, labels)
        if k not in self._counters:
            self._counters[k] = Counter(name, labels)
        return self._counters[k]

    def gauge(self, name: str, labels: dict[str, str] | None = None) -> Gauge:
        k = self._key(name, labels)
        if k not in self._gauges:
            self._gauges[k] = Gauge(name, labels)
        return self._gauges[k]

    def histogram(self, name: str, labels: dict[str, str] | None = None) -> Histogram:
        k = self._key(name, labels)
        if k not in self._histograms:
            self._histograms[k] = Histogram(name, labels=labels)
        return self._histograms[k]

    def get_all(self) -> list[dict[str, Any]]:
        return [m.get() for c in self._counters.values() for m in [c]] + \
               [m.get() for g in self._gauges.values() for m in [g]] + \
               [m.get() for h in self._histograms.values() for m in [h]]
