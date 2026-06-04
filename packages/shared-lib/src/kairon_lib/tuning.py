"""Tiered caching and feedback collection for tuning.

Port of agentmesh/packages/toolkit/src/tuning/ to Python.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    key: str = ""
    value: Any = None
    created_at: float = 0.0
    expires_at: float = 0.0
    access_count: int = 0
    last_accessed: float = 0.0


@dataclass
class CacheConfig:
    tier: str = "memory"
    max_size: int = 1000
    ttl: int = 60_000
    eviction_policy: str = "lru"  # lru | lfu | fifo


@dataclass
class TuningFeedback:
    id: str = ""
    input_: Any = None
    expected_output: Any = None
    actual_output: Any = None
    score: float = 0.0
    timestamp: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class FineTuneConfig:
    model_id: str = ""
    training_data: list[TuningFeedback] = field(default_factory=list)
    epochs: int = 3
    batch_size: int = 16
    learning_rate: float = 0.001


# ── CacheManager ──────────────────────────────────────────────────────


class CacheManager:
    """Tiered cache manager: memory -> disk -> remote."""

    def __init__(self, configs: dict[str, CacheConfig] | None = None) -> None:
        self._stores: dict[str, dict[str, CacheEntry]] = {
            "memory": {},
            "disk": {},
            "remote": {},
        }
        self._configs: dict[str, CacheConfig] = {
            "memory": CacheConfig(tier="memory", max_size=1000, ttl=60_000, eviction_policy="lru"),
            "disk": CacheConfig(tier="disk", max_size=10000, ttl=3_600_000, eviction_policy="lfu"),
            "remote": CacheConfig(tier="remote", max_size=100000, ttl=86_400_000, eviction_policy="fifo"),
        }
        if configs:
            for tier, cfg in configs.items():
                if tier in self._configs:
                    self._configs[tier] = CacheConfig(**{**self._configs[tier].__dict__, **cfg.__dict__})

    def set(self, key: str, value: Any, tier: str = "memory", ttl: int | None = None) -> None:
        store = self._stores[tier]
        cfg = self._configs[tier]
        if len(store) >= cfg.max_size:
            self._evict(tier)
        now = time.monotonic_ns() // 1_000_000
        store[key] = CacheEntry(key=key, value=value, created_at=now, expires_at=now + (ttl or cfg.ttl), access_count=0, last_accessed=now)

    def get(self, key: str, tier: str = "memory") -> Any | None:
        store = self._stores[tier]
        entry = store.get(key)
        if entry is None:
            return self._get_from_lower(key, tier)
        now = time.monotonic_ns() // 1_000_000
        if now > entry.expires_at:
            del store[key]
            return None
        entry.access_count += 1
        entry.last_accessed = now
        return entry.value

    def _get_from_lower(self, key: str, current_tier: str) -> Any | None:
        tiers = ["memory", "disk", "remote"]
        idx = tiers.index(current_tier) if current_tier in tiers else -1
        for i in range(idx + 1, len(tiers)):
            lower = tiers[i]
            entry = self._stores[lower].get(key)
            if entry is not None:
                self.set(key, entry.value, current_tier)
                return entry.value
        return None

    def _evict(self, tier: str) -> None:
        store = self._stores[tier]
        cfg = self._configs[tier]
        if not store:
            return
        items = list(store.items())
        if cfg.eviction_policy == "lru":
            idx = min(range(len(items)), key=lambda i: items[i][1].last_accessed)
        elif cfg.eviction_policy == "lfu":
            idx = min(range(len(items)), key=lambda i: items[i][1].access_count)
        else:  # fifo
            idx = min(range(len(items)), key=lambda i: items[i][1].created_at)
        del store[items[idx][0]]

    def clear(self, tier: str | None = None) -> None:
        if tier:
            self._stores[tier].clear()
        else:
            for s in self._stores.values():
                s.clear()

    def get_stats(self) -> dict[str, dict[str, int]]:
        return {t: {"size": len(s)} for t, s in self._stores.items()}


# ── FeedbackCollector ─────────────────────────────────────────────────


class FeedbackCollector:
    """Collect tool execution feedback for fine-tuning."""

    def __init__(self) -> None:
        self._feedbacks: dict[str, list[TuningFeedback]] = {}

    def collect(self, feedback: TuningFeedback) -> TuningFeedback:
        feedback.id = feedback.id or f"fb_{int(time.time() * 1000)}_{id(feedback)}"
        feedback.timestamp = feedback.timestamp or time.time()
        tool_id = feedback.context.get("toolId", "default") if feedback.context else "default"
        if tool_id not in self._feedbacks:
            self._feedbacks[tool_id] = []
        self._feedbacks[tool_id].append(feedback)
        return feedback

    def get_by_tool(self, tool_id: str) -> list[TuningFeedback]:
        return list(self._feedbacks.get(tool_id, []))

    def get_all(self) -> list[TuningFeedback]:
        result = []
        for fb_list in self._feedbacks.values():
            result.extend(fb_list)
        return result

    def get_high_quality(self, threshold: float = 0.7) -> list[TuningFeedback]:
        return [fb for fb in self.get_all() if fb.score >= threshold]

    def clear(self, tool_id: str | None = None) -> None:
        if tool_id:
            self._feedbacks.pop(tool_id, None)
        else:
            self._feedbacks.clear()

    def get_stats(self) -> dict[str, Any]:
        all_fb = self.get_all()
        by_tool = {tid: len(fbs) for tid, fbs in self._feedbacks.items()}
        avg_score = sum(fb.score for fb in all_fb) / len(all_fb) if all_fb else 0.0
        return {"total": len(all_fb), "by_tool": by_tool, "average_score": avg_score}


__all__ = [
    "CacheManager", "FeedbackCollector",
    "CacheEntry", "CacheConfig", "TuningFeedback", "FineTuneConfig",
]
