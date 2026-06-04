"""Market Analyzer — metabolic market analysis for dynamic EU pricing.

Extracted from SharedBrain D_Economy market_analyzer.py.
Computes EU consumption multipliers based on system load and task pressure.

Key concepts:
- CPU load factor: overloaded systems pay higher EU cost
- Task pressure: more active tasks → higher multiplier
- Cached multiplier with configurable refresh interval
"""

from __future__ import annotations

import logging
import os
import time

_log = logging.getLogger(__name__)


class MarketAnalyzer:
    """
    [RFC-007] 代谢市场分析器。
    职责: 根据系统实时状态计算 EU 扣费倍率。
    """

    def __init__(self) -> None:
        self.status = "active"
        self._last_update = 0.0
        self._cached_multiplier = 1.0
        self._update_interval = 10.0  # 10秒刷新一次

    def get_current_multiplier(self) -> float:
        """获取当前的代谢扣费倍率。"""
        now = time.time()
        if now - self._last_update > self._update_interval:
            self._cached_multiplier = self._calculate_multiplier()
            self._last_update = now
        return self._cached_multiplier

    def _calculate_multiplier(self) -> float:
        """
        计算逻辑：
        Multiplier = 1.0 (基础) + Load_Impact + Scarcity_Impact
        """
        multiplier = 1.0

        # 1. CPU 负载影响 (Load Factor)
        load1 = 0.0
        try:
            load1, _, _ = os.getloadavg()
            # 负载超过 2.0 开始加价，每增加 1.0 负载加价 20%
            if load1 > 2.0:
                load_impact = (load1 - 2.0) * 0.2
                multiplier += load_impact
        except (AttributeError, OSError):
            pass

        # 2. 任务压力影响 (Execution Load Scarcity)
        # TODO-migrate: was `from organs.D_Execution.organs.execution_coordinator import Coordinator`
        # Use engine_core equivalent when available:
        active_tasks = 0
        try:
            # TODO-migrate: from engine_core.execution_coordinator import Coordinator
            # active_tasks = len(Coordinator.list_active_sessions()) if hasattr(Coordinator, "list_active_sessions") else 0
            pass
        except ImportError:
            active_tasks = 0

        # 每 5 个活跃任务增加 10% 溢价
        task_impact = (active_tasks // 5) * 0.1
        multiplier += task_impact

        _log.debug(
            "[Market] Current EU Multiplier calculated: %.2f (Load: %.2f, ActiveTasks: %d)",
            multiplier,
            load1,
            active_tasks,
        )
        return round(multiplier, 2)


# 全局单例
_market_analyzer: MarketAnalyzer | None = None


def get_market_analyzer() -> MarketAnalyzer:
    """Get or create the global MarketAnalyzer singleton."""
    global _market_analyzer
    if _market_analyzer is None:
        _market_analyzer = MarketAnalyzer()
    return _market_analyzer
