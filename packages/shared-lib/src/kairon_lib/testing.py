"""
Test configuration, structured logging, and lightweight metrics for test harnesses.

Extracted from SharedBrain D_Harness organ (harness_config, harness_logger, harness_metrics).
All SharedBrain organ dependencies removed; standalone.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger(__name__)


# =============================================================================
# TestConfig — YAML-backed test configuration
# =============================================================================


class TestConfig:
    """Test harness configuration loaded from YAML or constructed with defaults.

    Supports dot-notation key access (e.g. ``"a.b.c"``) and environment-variable
    overrides for ``LLM_PROVIDER`` and ``TOKEN_THRESHOLD``.
    """

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = data or {}
        self._apply_env_overrides()

    @classmethod
    def load(cls, config_path: str | Path) -> TestConfig:
        """Load config from a YAML file; fall back to defaults on any error."""
        try:
            path = Path(config_path)
            with path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if isinstance(data.get("harness"), dict):
                data = data["harness"]
            return cls(data)
        except (yaml.YAMLError, ValueError, OSError):
            return cls()

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Dot-notation get: ``'a.b.c'`` traverses nested dicts."""
        parts = key.split(".")
        node: Any = self._data
        for part in parts:
            if not isinstance(node, dict):
                return default
            node = node.get(part, default)
        return node if node is not None else default

    def to_dict(self) -> dict[str, Any]:
        """Return a shallow copy of the configuration data."""
        return self._data.copy()

    def _apply_env_overrides(self) -> None:
        output_reshaper = self._data.setdefault("output_reshaper", {})
        llm_provider = os.environ.get("LLM_PROVIDER")
        token_threshold = os.environ.get("TOKEN_THRESHOLD")

        if llm_provider:
            output_reshaper["llm_provider"] = llm_provider
        if token_threshold:
            try:
                output_reshaper["token_threshold"] = int(token_threshold)
            except ValueError:
                pass


# =============================================================================
# TestLogger — structured JSON event logger
# =============================================================================


class TestLogger:
    """Structured event logger for test harness audit trails.

    Logs events in JSON format to both the Python logging system and,
    optionally, to a file on disk.

    Args:
        log_dir: Optional directory path to write structured log files.
        level: Python logging level (default: ``logging.INFO``).
    """

    def __init__(self, log_dir: str | None = None, level: int = logging.INFO) -> None:
        self._level = level
        self._log_dir: Path | None = None
        self._log_file: Any = None
        self._event_count = 0

        if log_dir:
            self._log_dir = Path(log_dir)
            self._log_dir.mkdir(parents=True, exist_ok=True)
            log_path = self._log_dir / "harness_events.jsonl"
            self._log_file = open(str(log_path), "a", encoding="utf-8")

    def log_event(
        self,
        event_type: str,
        source: str = "harness",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a structured event.

        Args:
            event_type: Short identifier for the event (e.g. ``'tool_called'``).
            source: Component that generated the event.
            metadata: Optional dict with additional context.
        """
        record: dict[str, Any] = {
            "ts": time.time(),
            "event": event_type,
            "source": source,
            "meta": metadata or {},
        }
        _log.log(self._level, "[TestLogger] %s | %s | %s", event_type, source, metadata)
        if self._log_file:
            self._log_file.write(json.dumps(record) + "\n")
            self._log_file.flush()
        self._event_count += 1

    def log_error(self, message: str, source: str = "harness", **kwargs: Any) -> None:
        """Log an error-level event."""
        metadata: dict[str, object] = {"message": message}
        metadata.update(kwargs)
        self.log_event("error", source=source, metadata=metadata)

    def log_warn(self, message: str, source: str = "harness", **kwargs: Any) -> None:
        """Log a warning-level event."""
        metadata: dict[str, object] = {"message": message}
        metadata.update(kwargs)
        self.log_event("warning", source=source, metadata=metadata)

    def get_stats(self) -> dict[str, int]:
        """Return logging statistics."""
        return {"event_count": self._event_count}

    def close(self) -> None:
        """Flush and close the log file if open."""
        if self._log_file:
            self._log_file.flush()
            self._log_file.close()
            self._log_file = None

    def __del__(self) -> None:
        self.close()


# =============================================================================
# TestMetrics — lightweight in-process metrics collector
# =============================================================================


class TestMetrics:
    """Lightweight in-process metrics collector for test harnesses.

    Tracks per-tool call counts, total / average latency, and event counters.
    Designed to be dependency-free so tests run without Prometheus installed.
    """

    def __init__(self) -> None:
        self._calls: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "total_ms": 0.0, "success": 0, "error": 0}
        )
        self._events: dict[str, int] = defaultdict(int)
        self._start_time: float = time.time()

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def record_tool_call(
        self,
        tool_id: str,
        action: str,
        status: str,
        latency_ms: float,
    ) -> None:
        """Record a single tool invocation with its outcome and latency."""
        key = f"{tool_id}.{action}"
        bucket = self._calls[key]
        bucket["count"] += 1
        bucket["total_ms"] += latency_ms
        if status in ("success", "ok"):
            bucket["success"] += 1
        else:
            bucket["error"] += 1

    def record_call(
        self,
        tool_id: str,
        latency_ms: float,
        success: bool,
    ) -> None:
        """Record a call result (simplified variant without action)."""
        bucket = self._calls[tool_id]
        bucket["count"] += 1
        bucket["total_ms"] += latency_ms
        if success:
            bucket["success"] += 1
        else:
            bucket["error"] += 1

    def increment(self, event_name: str, delta: int = 1) -> None:
        """Increment a named counter."""
        self._events[event_name] += delta

    # ------------------------------------------------------------------
    # Stats / reporting
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return a snapshot of all collected metrics."""
        stats: dict[str, Any] = {
            "uptime_seconds": round(time.time() - self._start_time, 2),
            "events": dict(self._events),
            "calls": {},
        }
        for key, bucket in self._calls.items():
            count = bucket["count"]
            avg_ms = bucket["total_ms"] / count if count else 0.0
            stats["calls"][key] = {
                "count": count,
                "success": bucket["success"],
                "error": bucket["error"],
                "avg_latency_ms": round(avg_ms, 3),
                "total_latency_ms": round(bucket["total_ms"], 3),
            }
        return stats

    def reset(self) -> None:
        """Clear all collected metrics (useful for testing)."""
        self._calls.clear()
        self._events.clear()
        self._start_time = time.time()


# =============================================================================
# Re-export as legacy names for organic compatibility
# =============================================================================

HarnessConfig = TestConfig
HarnessLogger = TestLogger
HarnessMetrics = TestMetrics

__all__ = [
    "TestConfig",
    "TestLogger",
    "TestMetrics",
    "HarnessConfig",
    "HarnessLogger",
    "HarnessMetrics",
]
