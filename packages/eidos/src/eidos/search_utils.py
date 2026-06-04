from __future__ import annotations

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 1.0.0
Owner: '@Sage'
Layer: L3
Summary: 'MonteCarloSampler: Importance sampling and ROI identification for knowledge retrieval.'
Extracted from: SharedBrain D_Memory/organs/utils/search_utils.py → eidos/search_utils.py
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Search Utils ≡ Module
# 内涵 ≝ {Search, Utils}
# 外延 ≝ {e | e ∈ Eidos ∧ implements(e, SearchUtils)}
# 功能 ⊢ {Search_Utils, Init_Search, Validate_Utils}
# =============================================================================


import math
import random
from typing import Any


class MonteCarloSampler:
    """
    Monte Carlo sampler for identifying high-value regions (ROI)
    in vector search results and performing importance sampling.
    """

    def sample_weighted(self, candidates: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
        """
        Importance sampling based on scores.
        """
        if not candidates:
            return []

        # 提取权重
        weights = [c.get("score", 0.1) for c in candidates]
        total_weight = sum(weights)
        if total_weight <= 0:
            return random.sample(candidates, min(count, len(candidates)))

        # 归一化概率
        probs = [w / total_weight for w in weights]

        # 执行采样
        results = random.choices(candidates, weights=probs, k=count)  # noqa: S311
        return results

    def _euclidean_dist(self, p1: list[float], p2: list[float]) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2, strict=True)))

    def identify_roi(self, results: list[dict[str, Any]], radius: float = 0.2) -> list[dict[str, Any]]:
        """
        Identify Region of Interest (ROI).
        Algorithm: Find clusters surrounded by high-scoring results.
        """
        if not results:
            return []

        roi_candidates = []
        for _i, r1 in enumerate(results):
            if "pos" not in r1:
                continue

            # 计算邻域内的密度与分值汇总
            neighbor_count = 0
            total_score = 0.0

            for _j, r2 in enumerate(results):
                if "pos" not in r2:
                    continue
                dist = self._euclidean_dist(r1["pos"], r2["pos"])
                if dist <= radius:
                    neighbor_count += 1
                    total_score += r2.get("score", 0.0)

            # 如果邻域内密度高且分值均值高，视为 ROI
            if neighbor_count >= 2 and (total_score / neighbor_count) >= 0.5:
                roi_candidates.append(r1)

        return roi_candidates
