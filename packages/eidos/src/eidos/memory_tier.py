"""Memory tiering policy — extracted from SharedBrain D_Memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MemoryTier(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"


class MemoryType(StrEnum):
    FACT = "fact"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


@dataclass
class MemoryItem:
    item_id: str
    content: str
    memory_type: MemoryType = MemoryType.FACT
    tier: MemoryTier = MemoryTier.HOT
    access_count: int = 0
    last_accessed: float = 0.0
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def should_promote(self, threshold: int = 10) -> bool:
        return self.access_count >= threshold

    def should_demote(self, max_age_days: int = 30) -> bool:
        import time

        age_days = (time.time() - self.last_accessed) / 86400
        return age_days > max_age_days


@dataclass
class MemoryTieringPolicy:
    hot_max: int = 1000
    warm_max: int = 5000
    promotion_threshold: int = 10
    demotion_days: int = 30

    def classify_tier(self, item: MemoryItem) -> MemoryTier:
        if item.should_promote(self.promotion_threshold):
            return MemoryTier.HOT
        if item.should_demote(self.demotion_days):
            if item.tier == MemoryTier.HOT:
                return MemoryTier.WARM
            if item.tier == MemoryTier.WARM:
                return MemoryTier.COLD
        return item.tier
