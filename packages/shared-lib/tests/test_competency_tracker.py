"""Tests for kairon_lib.competency_tracker — CompetencyLevel, CompetencyTracker."""

import pytest
from kairon_lib.competency_tracker import CompetencyLevel, CompetencyRecord, CompetencyTracker


class TestCompetencyLevel:
    def test_ordering(self):
        assert CompetencyLevel.NOVICE < CompetencyLevel.BEGINNER
        assert CompetencyLevel.BEGINNER < CompetencyLevel.INTERMEDIATE
        assert CompetencyLevel.INTERMEDIATE < CompetencyLevel.ADVANCED
        assert CompetencyLevel.ADVANCED < CompetencyLevel.EXPERT


class TestCompetencyTracker:
    def test_assess_new_skill(self):
        tracker = CompetencyTracker()
        tracker.assess("agent-1", "python", CompetencyLevel.ADVANCED)
        record = tracker.get_competency("agent-1", "python")
        assert record is not None
        assert record.level == CompetencyLevel.ADVANCED
        assert record.skill == "python"

    def test_assess_updates_existing(self):
        tracker = CompetencyTracker()
        tracker.assess("agent-1", "python", CompetencyLevel.INTERMEDIATE)
        tracker.assess("agent-1", "python", CompetencyLevel.EXPERT)
        record = tracker.get_competency("agent-1", "python")
        assert record.level == CompetencyLevel.EXPERT

    def test_assess_with_evidence(self):
        tracker = CompetencyTracker()
        tracker.assess("agent-1", "python", CompetencyLevel.ADVANCED, ["passed-cert", "completed-project"])
        record = tracker.get_competency("agent-1", "python")
        assert "passed-cert" in record.evidence
        assert "completed-project" in record.evidence

    def test_assess_appends_evidence(self):
        tracker = CompetencyTracker()
        tracker.assess("agent-1", "python", CompetencyLevel.INTERMEDIATE, ["first-evidence"])
        tracker.assess("agent-1", "python", CompetencyLevel.ADVANCED, ["second-evidence"])
        record = tracker.get_competency("agent-1", "python")
        assert "first-evidence" in record.evidence
        assert "second-evidence" in record.evidence

    def test_get_competency_nonexistent(self):
        tracker = CompetencyTracker()
        assert tracker.get_competency("unknown", "skill") is None

    def test_get_profile(self):
        tracker = CompetencyTracker()
        tracker.assess("agent-1", "python", CompetencyLevel.ADVANCED)
        tracker.assess("agent-1", "java", CompetencyLevel.INTERMEDIATE)
        tracker.assess("agent-2", "go", CompetencyLevel.EXPERT)
        profile = tracker.get_profile("agent-1")
        assert len(profile) == 2
        assert profile[0].agent_id == "agent-1"

    def test_find_experts(self):
        tracker = CompetencyTracker()
        tracker.assess("agent-1", "python", CompetencyLevel.EXPERT)
        tracker.assess("agent-2", "python", CompetencyLevel.INTERMEDIATE)
        tracker.assess("agent-3", "python", CompetencyLevel.ADVANCED)
        experts = tracker.find_experts("python")
        assert "agent-1" in experts
        assert "agent-2" not in experts
        assert "agent-3" in experts

    def test_get_skill_gap(self):
        tracker = CompetencyTracker()
        tracker.assess("agent-1", "python", CompetencyLevel.ADVANCED)
        required = {"python": CompetencyLevel.EXPERT, "java": CompetencyLevel.INTERMEDIATE}
        gaps = tracker.get_skill_gap("agent-1", required)
        assert "python" in gaps  # ADVANCED < EXPERT
        current, required_level = gaps["python"]
        assert current == CompetencyLevel.ADVANCED
        assert required_level == CompetencyLevel.EXPERT
        assert "java" in gaps
        assert gaps["java"][0] is None  # no assessment

    def test_get_skill_gap_no_gaps(self):
        tracker = CompetencyTracker()
        tracker.assess("agent-1", "python", CompetencyLevel.EXPERT)
        required = {"python": CompetencyLevel.EXPERT}
        gaps = tracker.get_skill_gap("agent-1", required)
        assert gaps == {}

    def test_suggest_training(self):
        tracker = CompetencyTracker()
        tracker.assess("agent-1", "python", CompetencyLevel.NOVICE)
        tracker.assess("agent-1", "java", CompetencyLevel.EXPERT)
        suggestions = tracker.suggest_training("agent-1")
        assert "python" in suggestions
        assert "java" not in suggestions

    def test_get_team_coverage(self):
        tracker = CompetencyTracker()
        tracker.assess("agent-1", "python", CompetencyLevel.ADVANCED)
        tracker.assess("agent-2", "python", CompetencyLevel.NOVICE)
        coverage = tracker.get_team_coverage(["python", "rust"])
        assert coverage["python"]["covered"] is True
        assert "agent-1" in coverage["python"]["experts"]
        assert coverage["rust"]["covered"] is False
