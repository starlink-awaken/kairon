"""Market Analyzer — metabolic market analysis for dynamic EU pricing.

Computes EU consumption multipliers based on system load and task pressure.

Key concepts:
- CPU load factor: overloaded systems pay higher EU cost
- Task pressure: more active tasks = higher multiplier
- Cached multiplier with configurable refresh interval

Merged from eu-pricing package into kaironcloud-billing pricing subpackage.
"""

from __future__ import annotations

import logging
import os
import time

_log = logging.getLogger(__name__)


class MarketAnalyzer:
    """Metabolic market analyzer for dynamic EU pricing multipliers."""

    def __init__(self) -> None:
        self.status = "active"
        self._last_update = 0.0
        self._cached_multiplier = 1.0
        self._update_interval = 10.0

    def get_current_multiplier(self) -> float:
        """Get the current metabolic pricing multiplier."""
        now = time.time()
        if now - self._last_update > self._update_interval:
            self._cached_multiplier = self._calculate_multiplier()
            self._last_update = now
        return self._cached_multiplier

    def _calculate_multiplier(self) -> float:
        """Multiplier = 1.0 (base) + Load_Impact + Scarcity_Impact."""
        multiplier = 1.0
        load1 = 0.0

        try:
            load1, _, _ = os.getloadavg()
            if load1 > 2.0:
                multiplier += (load1 - 2.0) * 0.2
        except (AttributeError, OSError):
            pass

        active_tasks = 0
        try:
            pass
        except ImportError:
            active_tasks = 0

        multiplier += (active_tasks // 5) * 0.1

        _log.debug(
            "[Market] Current EU Multiplier calculated: %.2f (Load: %.2f, ActiveTasks: %d)",
            multiplier,
            load1,
            active_tasks,
        )
        return round(multiplier, 2)


_market_analyzer: MarketAnalyzer | None = None


def get_market_analyzer() -> MarketAnalyzer:
    """Get or create the global MarketAnalyzer singleton."""
    global _market_analyzer
    if _market_analyzer is None:
        _market_analyzer = MarketAnalyzer()
    return _market_analyzer
