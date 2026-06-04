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
# Memory Lifecycle ≡ Module
# 内涵 ≝ {Memory, Lifecycle}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, MemoryLifecycle)}
# 功能 ⊢ {Memory_Lifecycle, Init_Memory, Validate_Lifecycle}
# =============================================================================

# ---
# domain: D-Memory
# layer: organ
# status: active
# ---
"""Automated memory lifecycle with hot → warm → cold → archive aging.

Entries are added to the *hot* tier and migrate through warm → cold → archive
as they age (based on configurable TTL thresholds).  Frequently-accessed
entries are promoted back to *hot* regardless of age.
"""

import logging
import time
from dataclasses import dataclass
from typing import Literal

from eidos.organs.context_compressor import ContextCompressor, MemoryEntry  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)

Tier = Literal["hot", "warm", "cold", "archive"]
_TIER_ORDER: list[Tier] = ["hot", "warm", "cold", "archive"]


@dataclass
class LifecycleConfig:
    """Tunable thresholds that drive tier transitions."""

    hot_ttl_seconds: float = 300.0  # 5 min
    warm_ttl_seconds: float = 1800.0  # 30 min
    cold_ttl_seconds: float = 7200.0  # 2 hours
    archive_after_seconds: float = 86400.0  # 24 hours
    access_count_hot_floor: int = 3
    max_entries: int = 10_000


class MemoryLifecycleManager:
    """Four-tier memory aging engine.

    Entries flow  hot → warm → cold → archive  based on elapsed time since
    their ``timestamp``.  The ``tick()`` method runs one full classification
    pass and redistributes entries across tiers.
    """

    def __init__(
        self,
        config: LifecycleConfig,
        compressor: ContextCompressor,
    ) -> None:
        self._config = config
        self._compressor = compressor
        self._tiers: dict[str, list[MemoryEntry]] = {t: [] for t in _TIER_ORDER}

    # -- mutators -----------------------------------------------------------

    def add(self, entry: MemoryEntry) -> None:
        """Insert *entry* into the hot tier."""
        self._tiers["hot"].append(entry)
        self._enforce_capacity()

    def tick(self, now: float | None = None) -> None:
        """Run one aging cycle — reclassify every entry across all tiers."""
        now = now if now is not None else time.time()

        # Collect all non-archive entries for reclassification.
        pool: list[MemoryEntry] = []
        for tier in ("hot", "warm", "cold"):
            pool.extend(self._tiers[tier])
            self._tiers[tier] = []

        for entry in pool:
            tier = self._classify(entry, now)
            self._tiers[tier].append(entry)

    def compact_warm(self, token_budget: int) -> None:
        """Summarise warm-tier entries that exceed *token_budget* tokens."""
        warm = self._tiers["warm"]
        if not warm:
            return

        total_tokens = sum(e.token_count for e in warm)
        if total_tokens <= token_budget:
            return

        summary = self._compressor.summarize_batch(warm)
        self._tiers["warm"] = [summary]

    def archive_cold(self) -> None:
        """Move all cold-tier entries into the archive tier."""
        cold = self._tiers["cold"]
        if cold:
            self._tiers["archive"].extend(cold)
            self._tiers["cold"] = []

    def evict_archived(self, max_age: float) -> int:
        """Permanently remove archived entries older than *max_age* seconds.

        Returns the number of evicted entries.
        """
        now = time.time()
        before = len(self._tiers["archive"])
        self._tiers["archive"] = [e for e in self._tiers["archive"] if (now - e.timestamp) <= max_age]
        evicted = before - len(self._tiers["archive"])
        if evicted:
            logger.debug("evict_archived: removed %d entries", evicted)
        return evicted

    # -- queries ------------------------------------------------------------

    def get_tier(self, tier: Tier) -> list[MemoryEntry]:
        """Return a shallow copy of the entries in *tier*."""
        return list(self._tiers[tier])

    def stats(self) -> dict[str, int]:
        """Return ``{tier_name: entry_count}`` for every tier."""
        return {t: len(entries) for t, entries in self._tiers.items()}

    # -- internals ----------------------------------------------------------

    def _classify(self, entry: MemoryEntry, now: float) -> Tier:
        """Determine which tier *entry* belongs to based on age & access."""
        age = now - entry.timestamp

        if age <= self._config.hot_ttl_seconds:
            return "hot"
        if entry.access_count >= self._config.access_count_hot_floor:
            return "hot"
        if age <= self._config.warm_ttl_seconds:
            return "warm"
        if age <= self._config.cold_ttl_seconds:
            return "cold"
        return "archive"

    def _enforce_capacity(self) -> None:
        """Drop oldest archived entries when total count exceeds max."""
        total = sum(len(v) for v in self._tiers.values())
        overflow = total - self._config.max_entries
        if overflow <= 0:
            return
        archive = self._tiers["archive"]
        archive.sort(key=lambda e: e.timestamp)
        del archive[:overflow]
