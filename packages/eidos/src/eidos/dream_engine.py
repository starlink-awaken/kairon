from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sage'
Layer: L3
Summary: 'DreamEngine: Background knowledge compression and mental model synthesis.'
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Dream Engine ≡ Engine
# 内涵 ≝ {Dream, Engine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, DreamEngine)}
# 功能 ⊢ {Dream_Engine, Init_Dream, Validate_Engine}
# =============================================================================

import logging
import math
from typing import Any

from nucleus.Z_Microkernel.gateways.cognitive_gateway import Gateway  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)


class DreamEngine:
    """
    [TRK-031] 梦境引擎 (DreamEngine)
    负责在系统空闲时对事实图谱进行聚类分析，提炼高阶心理模型 (Mental Models)。
    """

    def __init__(self) -> None:
        self.status = "active"

    def _fetch_recent_facts(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取最近的事实（Stub）。实际会从 FactGraph 查询。"""
        return []

    def _vector_distance(self, v1: list[float], v2: list[float]) -> float:
        """计算两个向量之间的欧氏距离。"""
        if len(v1) != len(v2):
            return 1.0
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2, strict=True)))

    def scan_knowledge_clusters(self, threshold: float = 0.5) -> list[list[dict[str, Any]]]:
        """
        基于向量距离对事实进行简单聚类。
        """
        facts = self._fetch_recent_facts()
        if not facts:
            return []

        clusters = []
        visited = set()

        for i, f1 in enumerate(facts):
            if i in visited:
                continue

            # Start a new cluster
            current_cluster = [f1]
            visited.add(i)

            if "embedding" not in f1:
                clusters.append(current_cluster)
                continue

            for j, f2 in enumerate(facts):
                if j in visited or "embedding" not in f2:
                    continue

                dist = self._vector_distance(f1["embedding"], f2["embedding"])
                if dist <= threshold:
                    current_cluster.append(f2)
                    visited.add(j)

            clusters.append(current_cluster)

        # 只返回包含多个事实的簇
        return [c for c in clusters if len(c) > 1]

    async def synthesize_mental_model(self, cluster: list[dict[str, Any]]) -> str:
        """
        将一组相关事实提炼为通用的“心理模型”。
        """
        _log.info("🧠 [DreamEngine] Synthesizing mental model for cluster of %d facts", len(cluster))

        facts_summary = "\n".join([f"- {f.get('sub')} {f.get('pred')} {f.get('obj')}" for f in cluster])

        prompt = (
            "You are the Dream Engine of SharedBrain B-OS.\n"
            "Analyze the following cluster of runtime facts and extract a high-level Mental Model (a general rule or pattern).\n"
            f"Facts:\n{facts_summary}\n\n"
            "Output a concise description of the pattern."
        )

        response = Gateway.call(prompt, iq_req=9.0, spec="philosopher")
        if response.get("status") == "success":
            return response["content"].strip()

        return "Failed to synthesize model."
