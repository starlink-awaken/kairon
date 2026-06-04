"""Tests for kairon_lib.decision_journal — DecisionEntry, DecisionJournal."""

import pytest

try:
    from kairon_lib.decision_journal import DecisionJournal
except ImportError:
    pytestmark = pytest.mark.skip(reason="test requires archived kairon_lib module")  # type: ignore[name-defined]


class TestDecisionJournal:
    def test_record_decision(self):
        dj = DecisionJournal()
        entry = dj.record_decision(
            title="Add feature X",
            context="Need to improve performance",
            decision="Implement X using Y",
            rationale="Y is faster",
            alternatives=["Z", "W"],
            author="agent-1",
            tags=["performance"],
        )
        assert entry.decision_id.startswith("DEC-")
        assert entry.title == "Add feature X"
        assert entry.author == "agent-1"
        assert entry.tags == ["performance"]

    def test_get_decision(self):
        dj = DecisionJournal()
        entry = dj.record_decision("Title", "Ctx", "Dec", "Why", ["Alt"], "auth")
        fetched = dj.get_decision(entry.decision_id)
        assert fetched is not None
        assert fetched.decision_id == entry.decision_id

    def test_get_decision_not_found(self):
        dj = DecisionJournal()
        assert dj.get_decision("nonexistent") is None

    def test_search_by_title(self):
        dj = DecisionJournal()
        dj.record_decision("Performance Optimization", "ctx", "dec1", "why", [], "auth", tags=["perf"])
        dj.record_decision("Security Update", "ctx", "dec2", "why", [], "auth", tags=["security"])
        results = dj.search("performance")
        assert len(results) == 1
        assert results[0].title == "Performance Optimization"

    def test_search_by_context(self):
        dj = DecisionJournal()
        dj.record_decision("T1", "Database migration plan", "dec", "why", [], "auth")
        results = dj.search("migration")
        assert len(results) == 1

    def test_search_tags(self):
        dj = DecisionJournal()
        dj.record_decision("T1", "ctx", "dec", "why", [], "auth", tags=["critical", "urgent"])
        dj.record_decision("T2", "ctx", "dec", "why", [], "auth", tags=["normal"])
        results = dj.search("urgent")
        assert len(results) == 1

    def test_search_no_match(self):
        dj = DecisionJournal()
        dj.record_decision("T1", "ctx", "dec", "why", [], "auth")
        results = dj.search("nonexistent")
        assert results == []

    def test_record_outcome(self):
        dj = DecisionJournal()
        entry = dj.record_decision("T1", "ctx", "dec", "why", [], "auth")
        dj.record_outcome(entry.decision_id, "successful")
        assert entry.outcome == "successful"

    def test_record_outcome_not_found(self):
        dj = DecisionJournal()
        with pytest.raises(KeyError, match="not found"):
            dj.record_outcome("nonexistent", "outcome")

    def test_list_decisions(self):
        dj = DecisionJournal()
        dj.record_decision("T1", "ctx", "dec", "why", [], "auth", tags=["tag1"])
        dj.record_decision("T2", "ctx", "dec", "why", [], "auth", tags=["tag2"])
        all_decisions = dj.list_decisions()
        assert len(all_decisions) == 2
        tag1_decisions = dj.list_decisions(tag="tag1")
        assert len(tag1_decisions) == 1

    def test_get_timeline(self):
        dj = DecisionJournal()
        e1 = dj.record_decision("T1", "ctx", "dec", "why", [], "auth")
        dj.record_decision("T2", "ctx", "dec", "why", [], "auth")
        timeline = dj.get_timeline()
        assert len(timeline) == 2
        assert timeline[0].decision_id == e1.decision_id

    def test_export_journal(self):
        dj = DecisionJournal()
        dj.record_decision("T1", "ctx", "dec", "why", ["alt1"], "author-1", tags=["tag1"])
        exported = dj.export_journal()
        assert len(exported) == 1
        assert exported[0]["title"] == "T1"
        assert exported[0]["author"] == "author-1"
        assert exported[0]["alternatives"] == ["alt1"]
