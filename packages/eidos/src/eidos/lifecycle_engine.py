from __future__ import annotations

"""
---
Type: Engine
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Layer: L3
Summary: Memory Lifecycle Engine - handles decay, forgetting, and consolidation.
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Lifecycle Engine ≡ Engine
# 内涵 ≝ {Lifecycle, Engine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, LifecycleEngine)}
# 功能 ⊢ {Lifecycle_Engine, Init_Lifecycle, Validate_Engine}
# =============================================================================

import logging
import math
import time
from typing import Any

from eidos.fact_graph import get_graph

_log = logging.getLogger(__name__)


class DecayModel:
    """基于 Ebbinghaus 遗忘曲线简化版的记忆衰减模型。"""

    def __init__(self, half_life_days: float = 7.0) -> None:
        # 半衰期（天）转化为秒
        self.halflife = half_life_days * 24 * 3600

    def calculate_current_importance(
        self, initial_importance: float, elapsed_seconds: float, access_count: int
    ) -> float:
        """计算当前重要性。

        公式: current = initial * (0.5 ^ (elapsed / halflife)) * log2(access_count + 2)
        """
        decay_factor = math.pow(0.5, elapsed_seconds / self.halflife)
        boost_factor = math.log2(access_count + 2)
        return initial_importance * decay_factor * boost_factor


class ActiveConsolidator:
    """主动固化引擎：将短期活跃事实提取并迁移至长期知识库。"""

    def __init__(self, graph: Any | None = None) -> None:
        self.graph = graph or get_graph()
        self.decay_model = DecayModel()
        self.consolidation_threshold = 2.0  # 重要性达到此值则触发固化
        self.forget_threshold = 0.1  # 重要性低于此值则触发遗忘

    def scan_and_process(self) -> dict[str, int]:
        """扫描全量事实并执行遗忘或固化逻辑。"""
        now = time.time()
        facts = self.graph.query()  # 获取所有事实

        stats = {"forgotten": 0, "consolidated": 0, "maintained": 0}

        with self.graph._get_connection() as conn:
            for fact in facts:
                fact_id = fact["id"]
                initial_imp = fact.get("importance", 1.0)
                elapsed = now - fact["timestamp"]
                access_count = fact.get("access_count", 0)

                current_imp = self.decay_model.calculate_current_importance(initial_imp, elapsed, access_count)

                # 1. 遗忘逻辑
                if current_imp < self.forget_threshold:
                    conn.execute("DELETE FROM fact_triples WHERE id = ?", (fact_id,))
                    stats["forgotten"] += 1
                    _log.debug(f"Memory forgotten: {fact_id} (imp={current_imp:.2f})")
                    continue

                # 2. 固化逻辑
                if current_imp >= self.consolidation_threshold:
                    # 模拟迁移至“长期存储”（此处仅更新 metadata 标记）
                    metadata = fact.get("metadata") or "{}"
                    import json

                    meta_dict = json.loads(metadata)
                    if not meta_dict.get("consolidated"):
                        meta_dict["consolidated"] = True
                        meta_dict["consolidated_at"] = now
                        conn.execute(
                            "UPDATE fact_triples SET metadata = ?, importance = importance * 1.5 WHERE id = ?",
                            (json.dumps(meta_dict), fact_id),
                        )
                        stats["consolidated"] += 1
                        _log.info(f"Memory consolidated: {fact_id}")
                        continue

                stats["maintained"] += 1

            conn.commit()

        # Invalidate edge cache since we modified facts via raw SQL
        if hasattr(self.graph, "_edge_cache") and (stats["forgotten"] or stats["consolidated"]):
            self.graph._edge_cache.invalidate_pattern("fact:")

        return stats


# Global singleton
global_consolidator = ActiveConsolidator()
