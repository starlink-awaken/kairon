"""Basic tests for gc-engine package."""

from __future__ import annotations


from gc_engine import (
    DistillationEngine,
    GCEngine,
    MemoryExcretionPipeline,
    RetentionPolicy,
)
from gc_engine.archiver import ArchiveEntry, ArchiveManager, ArchivePolicy, StorageTier, TieredStorage
from gc_engine.gc_core import GCStats
from gc_engine.lifecycle import DecayConfig, LifecycleManager, LifecycleRecord


class TestGCEngineBasic:
    """Core functionality and edge case tests."""

    def test_import(self):
        """All expected exports are importable."""
        assert DistillationEngine is not None
        assert GCEngine is not None
        assert MemoryExcretionPipeline is not None
        assert RetentionPolicy is not None
        assert GCStats is not None
        assert ArchiveEntry is not None
        assert ArchiveManager is not None
        assert ArchivePolicy is not None
        assert StorageTier is not None
        assert TieredStorage is not None
        assert DecayConfig is not None
        assert LifecycleManager is not None
        assert LifecycleRecord is not None

    def test_gc_engine_empty_sweep_twice(self):
        """Sweeping an empty engine twice is safe."""
        engine = GCEngine()
        assert engine.sweep() == []
        assert engine.sweep() == []

    def test_gc_engine_mark_same_id_different_reasons(self):
        """Marking same id overwrites reason and counts as one entry."""
        engine = GCEngine()
        engine.mark("a", "reason1")
        engine.mark("a", "reason2")
        stats = engine.get_stats()
        assert stats.entries_marked == 1

    def test_memory_pipeline_empty_entries(self):
        """Pipeline with no entries handles identify and excrete."""
        pipeline = MemoryExcretionPipeline()
        assert pipeline.identify_stale(30) == []
        assert pipeline.excrete(["x"]) == []
        assert pipeline.excrete([]) == []

    def test_retention_policy_minimal_config(self):
        """RetentionPolicy with empty rules keeps everything."""
        policy = RetentionPolicy()
        assert policy.should_keep({"id": "a"}, {}) is True
        assert policy.should_keep({}, {}) is True

    def test_distillation_empty_method(self):
        """Distillation with empty entries returns empty for all methods."""
        engine = DistillationEngine()
        assert engine.distill([], method="concat_titles") == ""
        assert engine.distill([], method="truncate_content") == ""
        assert engine.distill([], method="first") == ""
