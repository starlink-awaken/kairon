"""Tests for gc-engine package."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from gc_engine import (
    DistillationEngine,
    GCEngine,
    MemoryExcretionPipeline,
    RetentionPolicy,
)
from gc_engine.gc_core import GCStats

# ---------------------------------------------------------------------------
# GCEngine
# ---------------------------------------------------------------------------

class TestGCEngine:
    def test_mark_adds_entry(self):
        engine = GCEngine()
        engine.mark("a", "obsolete")
        stats = engine.get_stats()
        assert stats.entries_marked == 1
        assert stats.entries_swept == 0

    def test_mark_overwrites_same_id(self):
        engine = GCEngine()
        engine.mark("a", "old")
        engine.mark("a", "new")
        stats = engine.get_stats()
        assert stats.entries_marked == 1  # still one id

    def test_sweep_returns_and_clears(self):
        engine = GCEngine()
        engine.mark("a", "r1")
        engine.mark("b", "r2")
        deleted = engine.sweep()
        assert sorted(deleted) == ["a", "b"]
        stats = engine.get_stats()
        assert stats.entries_marked == 0
        assert stats.entries_swept == 2

    def test_sweep_sets_last_run(self):
        engine = GCEngine()
        engine.mark("x")
        engine.sweep()
        stats = engine.get_stats()
        assert stats.last_run is not None

    def test_stats_after_multiple_sweeps(self):
        engine = GCEngine()
        engine.mark("a")
        engine.sweep()
        engine.mark("b")
        engine.mark("c")
        engine.sweep()
        stats = engine.get_stats()
        assert stats.entries_marked == 0
        assert stats.entries_swept == 3

    def test_sweep_empty_returns_empty_list(self):
        engine = GCEngine()
        deleted = engine.sweep()
        assert deleted == []

    def test_get_stats_dataclass(self):
        engine = GCEngine()
        stats = engine.get_stats()
        assert isinstance(stats, GCStats)
        assert stats.entries_marked == 0
        assert stats.entries_swept == 0
        assert stats.last_run is None


# ---------------------------------------------------------------------------
# MemoryExcretionPipeline
# ---------------------------------------------------------------------------

class TestMemoryExcretionPipeline:
    @staticmethod
    def _make_entry(eid: str, days_ago: int) -> dict:
        ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return {"id": eid, "last_accessed": ts.isoformat()}

    def test_empty_pipeline_returns_nothing(self):
        pipeline = MemoryExcretionPipeline()
        assert pipeline.identify_stale(30) == []
        assert pipeline.excrete(["a"]) == []

    def test_identify_stale_below_threshold_kept(self):
        pipeline = MemoryExcretionPipeline([
            self._make_entry("a", 5),
            self._make_entry("b", 10),
        ])
        stale = pipeline.identify_stale(days_threshold=30)
        assert stale == []

    def test_identify_stale_above_threshold(self):
        pipeline = MemoryExcretionPipeline([
            self._make_entry("a", 5),
            self._make_entry("b", 60),
        ])
        stale = pipeline.identify_stale(days_threshold=30)
        assert stale == ["b"]

    def test_identify_stale_no_last_accessed(self):
        pipeline = MemoryExcretionPipeline([
            {"id": "a"},
            self._make_entry("b", 5),
        ])
        stale = pipeline.identify_stale(days_threshold=30)
        assert "a" in stale  # never accessed → stale

    def test_excrete_removes_entries(self):
        pipeline = MemoryExcretionPipeline([
            self._make_entry("a", 5),
            self._make_entry("b", 5),
        ])
        removed = pipeline.excrete(["a"])
        assert removed == ["a"]
        # Excreting "a" again returns empty — it is already gone
        removed_again = pipeline.excrete(["a"])
        assert removed_again == []
        # "b" can still be excreted
        removed_b = pipeline.excrete(["b"])
        assert removed_b == ["b"]

    def test_excrete_returns_only_existing_ids(self):
        pipeline = MemoryExcretionPipeline([self._make_entry("a", 5)])
        removed = pipeline.excrete(["a", "nonexistent"])
        assert removed == ["a"]


# ---------------------------------------------------------------------------
# DistillationEngine
# ---------------------------------------------------------------------------

class TestDistillationEngine:
    def test_empty_entries_returns_empty(self):
        engine = DistillationEngine()
        assert engine.distill([]) == ""

    def test_concat_titles_from_dicts(self):
        engine = DistillationEngine()
        entries = [
            {"id": "1", "title": "Alpha"},
            {"id": "2", "title": "Beta"},
        ]
        result = engine.distill(entries, method="concat_titles")
        assert result == "Alpha\nBeta"

    def test_concat_titles_falls_back_to_id(self):
        engine = DistillationEngine()
        entries = [{"id": "abc"}]
        result = engine.distill(entries, method="concat_titles")
        assert result == "abc"

    def test_truncate_content_first_sentence(self):
        engine = DistillationEngine()
        entries = [
            {"content": "First sentence. Second sentence."},
            {"content": "Another thought. More details."},
        ]
        result = engine.distill(entries, method="truncate_content")
        assert result == "First sentence | Another thought"

    def test_first_method(self):
        engine = DistillationEngine()
        entries = [{"title": "T1", "content": "C1"}, {"title": "T2"}]
        result = engine.distill(entries, method="first")
        assert result == "T1: C1"

    def test_distill_respects_max_length(self):
        engine = DistillationEngine()
        entries = [{"title": "A" * 600}]
        result = engine.distill(entries, method="concat_titles", max_length=10)
        assert len(result) <= 10
        assert result.endswith("...")

    def test_distill_with_string_entries(self):
        engine = DistillationEngine()
        result = engine.distill(["hello", "world"], method="concat_titles")
        assert result == "hello\nworld"

    def test_unknown_method_message(self):
        engine = DistillationEngine()
        result = engine.distill([{"title": "X"}], method="bogus")
        assert "Unknown method" in result


# ---------------------------------------------------------------------------
# RetentionPolicy
# ---------------------------------------------------------------------------

class TestRetentionPolicy:
    def test_pinned_ids_always_kept(self):
        policy = RetentionPolicy()
        assert policy.should_keep(
            {"id": "pin-me", "importance": 0.0},
            {"pinned_ids": ["pin-me"], "min_importance": 0.5},
        ) is True

    def test_ttl_expired_returns_false(self):
        policy = RetentionPolicy()
        old_ts = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        assert policy.should_keep(
            {"id": "a", "created_at": old_ts},
            {"ttl_days": 30},
        ) is False

    def test_ttl_within_window_returns_true(self):
        policy = RetentionPolicy()
        recent = datetime.now(timezone.utc).isoformat()
        assert policy.should_keep(
            {"id": "a", "created_at": recent},
            {"ttl_days": 30},
        ) is True

    def test_ttl_no_timestamp_kept(self):
        policy = RetentionPolicy()
        assert policy.should_keep({"id": "a"}, {"ttl_days": 30}) is True

    def test_importance_below_threshold_returns_false(self):
        policy = RetentionPolicy()
        assert policy.should_keep(
            {"id": "a", "importance": 0.1},
            {"min_importance": 0.5},
        ) is False

    def test_importance_above_threshold_returns_true(self):
        policy = RetentionPolicy()
        assert policy.should_keep(
            {"id": "a", "importance": 0.8},
            {"min_importance": 0.5},
        ) is True

    def test_importance_missing_kept(self):
        policy = RetentionPolicy()
        assert policy.should_keep({"id": "a"}, {"min_importance": 0.5}) is True

    def test_default_no_rules_keeps(self):
        policy = RetentionPolicy()
        assert policy.should_keep({"id": "a"}, {}) is True

    def test_both_rules_applied(self):
        policy = RetentionPolicy()
        old_ts = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        # Expired TTL → False, importance is high but TTL check comes first
        assert policy.should_keep(
            {"id": "a", "created_at": old_ts, "importance": 0.9},
            {"ttl_days": 30, "min_importance": 0.5},
        ) is False
