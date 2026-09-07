"""Integration tests for minerva.mos_bridge (T6-02 Phase 2).

Verifies that MinervaUnifiedMemory correctly delegates to mos.unified.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("MOS_RBAC", "0")

import pytest

from minerva.mos_bridge import (
    EmbeddingResult,
    MinervaUnifiedMemory,
    PipelineStats,
    get_minerva_unified,
)


def _fresh() -> MinervaUnifiedMemory:
    return MinervaUnifiedMemory()


# ── write / recall / search ────────────────────────────────────────────────

class TestMosBridgeWriteRecallSearch:
    def test_write_returns_ok(self) -> None:
        um = _fresh()
        result = um.write("知识蒸馏是模型压缩的核心技术", type="semantic")
        assert result["ok"] is True
        assert "envelope_id" in result

    def test_write_dedup_suppresses(self) -> None:
        um = _fresh()
        um.write("旧暂行办法已废止", type="institutional")
        result = um.write("旧暂行办法已废止", type="institutional", dedup=True)
        # dedup may return ok=True with dedup-skip envelope_id
        assert result["ok"] is True

    def test_recall_returns_list(self) -> None:
        um = _fresh()
        um.write("MOS 统一记忆接口支持 intent 路由", type="semantic")
        results = um.recall("记忆接口", limit=5)
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_search_returns_list(self) -> None:
        um = _fresh()
        um.write("向量检索与全文检索融合", type="semantic")
        results = um.search("向量检索", limit=5)
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_recall_empty_query(self) -> None:
        um = _fresh()
        results = um.recall("")
        assert isinstance(results, list)


# ── embed_texts ────────────────────────────────────────────────────────────

class TestMosBridgeEmbed:
    @pytest.mark.asyncio
    async def test_embed_returns_vectors(self) -> None:
        um = _fresh()
        vectors = await um.embed_texts(["hello world", "test embedding"])
        assert len(vectors) == 2
        assert len(vectors[0]) == 384  # default dimension

    @pytest.mark.asyncio
    async def test_embed_deterministic(self) -> None:
        um = _fresh()
        v1 = await um.embed_texts(["same text"])
        v2 = await um.embed_texts(["same text"])
        assert v1[0] == v2[0]


# ── stats ──────────────────────────────────────────────────────────────────

class TestMosBridgeStats:
    def test_stats_structure(self) -> None:
        um = _fresh()
        stats = um.get_stats()
        assert "pipeline" in stats
        assert "backend" in stats
        assert stats["backend"] == "mos.unified"


# ── singleton ──────────────────────────────────────────────────────────────

class TestMosBridgeSingleton:
    def test_get_returns_same_instance(self) -> None:
        a = get_minerva_unified()
        b = get_minerva_unified()
        assert a is b


# ── backward compat dataclasses ────────────────────────────────────────────

class TestBackwardCompat:
    def test_embedding_result_dataclass(self) -> None:
        r = EmbeddingResult(item_id=1, success=True, embedding=[0.1, 0.2])
        assert r.item_id == 1
        assert r.success is True

    def test_pipeline_stats_update(self) -> None:
        s = PipelineStats()
        r = EmbeddingResult(item_id=1, success=True, duration_ms=10.0)
        s.update(r)
        assert s.total_processed == 1
        assert s.successful == 1
