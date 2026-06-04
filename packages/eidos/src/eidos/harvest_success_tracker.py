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
# Harvest Success Tracker ≡ Tracker
# 内涵 ≝ {Harvest, Success, Tracker}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, HarvestSuccessTracker)}
# 功能 ⊢ {Harvest_Success, Success_Tracker, Tracker_Init}
# =============================================================================

# ---
# domain: D-Memory
# layer: organ
# status: active
# ---

import logging
import time
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)

__all__ = ["HarvestAttempt", "HarvestSuccessTracker"]


@dataclass
class HarvestAttempt:
    attempt_id: str
    source: str
    target: str
    success: bool
    items_harvested: int = 0
    error: str | None = None
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0


class HarvestSuccessTracker:
    """Tracks harvest attempt outcomes and per-source reliability."""

    def __init__(self) -> None:
        super().__init__()
        self._attempts: list[HarvestAttempt] = []

    def record_attempt(self, attempt: HarvestAttempt) -> None:
        self._attempts.append(attempt)

    # -- Metrics -------------------------------------------------------------

    def _filtered(self, source: str | None) -> list[HarvestAttempt]:
        if source is None:
            return self._attempts
        return [a for a in self._attempts if a.source == source]

    def get_success_rate(self, source: str | None = None) -> float:
        filtered = self._filtered(source)
        if not filtered:
            return 0.0
        return sum(1 for a in filtered if a.success) / len(filtered)

    def get_total_harvested(self, source: str | None = None) -> int:
        return sum(a.items_harvested for a in self._filtered(source))

    def get_failing_sources(self) -> list[str]:
        sources: dict[str, list[bool]] = {}
        for a in self._attempts:
            sources.setdefault(a.source, []).append(a.success)
        return sorted(src for src, outcomes in sources.items() if sum(outcomes) / len(outcomes) < 0.5)

    def get_avg_duration(self, source: str | None = None) -> float:
        filtered = self._filtered(source)
        if not filtered:
            return 0.0
        return sum(a.duration_ms for a in filtered) / len(filtered)

    def get_recent_attempts(self, count: int = 10) -> list[HarvestAttempt]:
        return sorted(self._attempts, key=lambda a: a.timestamp, reverse=True)[:count]

    def get_source_stats(self) -> dict:
        sources: dict[str, list[HarvestAttempt]] = {}
        for a in self._attempts:
            sources.setdefault(a.source, []).append(a)
        stats: dict[str, dict] = {}
        for src, attempts in sources.items():
            successes = sum(1 for a in attempts if a.success)
            stats[src] = {
                "total_attempts": len(attempts),
                "success_rate": successes / len(attempts),
                "total_harvested": sum(a.items_harvested for a in attempts),
                "avg_duration_ms": sum(a.duration_ms for a in attempts) / len(attempts),
            }
        return stats

    def get_trend(self, source: str, window: int = 10) -> str:
        filtered = [a for a in self._attempts if a.source == source]
        filtered.sort(key=lambda a: a.timestamp)
        if len(filtered) < 2:
            return "stable"
        recent = filtered[-window:]
        mid = len(recent) // 2
        first_half = recent[:mid]
        second_half = recent[mid:]
        rate_first = sum(1 for a in first_half if a.success) / max(len(first_half), 1)
        rate_second = sum(1 for a in second_half if a.success) / max(len(second_half), 1)
        diff = rate_second - rate_first
        if diff > 0.1:
            return "improving"
        if diff < -0.1:
            return "degrading"
        return "stable"
