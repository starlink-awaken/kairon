"""Tests for symphony-protocol agent matcher — AgentMatcher."""

from unittest.mock import MagicMock

import pytest
from protocols_layer.symphony.matcher import AgentMatcher
from protocols_layer.symphony.models import AgentCapability, AgentProfile, TaskRequirement


def _make_agent(agent_id: str, capabilities: dict | None = None, specialization: str | None = None) -> AgentProfile:
    caps = {AgentCapability(name=k): v for k, v in (capabilities or {}).items()}
    return AgentProfile(
        agent_id=agent_id,
        capabilities=caps,
        specialization=specialization,
    )


def _make_task(task_id: str, capabilities: list[str] | None = None, complexity: int = 5, priority: int = 5) -> TaskRequirement:
    caps = {AgentCapability(name=c) for c in (capabilities or [])}
    return TaskRequirement(task_id=task_id, required_capabilities=caps, complexity=complexity, priority=priority)


class TestAgentMatcherInit:
    """AgentMatcher.__init__: default weights and states"""

    def test_default_weights(self):
        m = AgentMatcher()
        assert m._score_weights["capability"] == 0.42
        assert m._score_weights["reputation"] == 0.15

    def test_intervention_weight_clamped(self):
        m = AgentMatcher(intervention_weight=1.5)
        assert m._intervention_weight == 1.0

    def test_intervention_weight_negative(self):
        m = AgentMatcher(intervention_weight=-0.5)
        assert m._intervention_weight == 0.0


class TestAgentMatcherTaskDegradation:
    """AgentMatcher.apply_task_degradation: adjusts task priority based on intervention"""

    def test_low_intervention_no_change(self):
        m = AgentMatcher(intervention_weight=0.2)
        task = _make_task("t1", complexity=7, priority=5)
        result = m.apply_task_degradation(task)
        assert result.priority == 5  # unchanged

    def test_high_intervention_high_complexity_drops_priority_to_1(self):
        m = AgentMatcher(intervention_weight=0.8)
        task = _make_task("t1", complexity=7, priority=5)
        result = m.apply_task_degradation(task)
        assert result.priority == 1

    def test_medium_intervention_medium_complexity_drops_priority_by_2(self):
        m = AgentMatcher(intervention_weight=0.6)
        task = _make_task("t1", complexity=5, priority=5)
        result = m.apply_task_degradation(task)
        assert result.priority == 3

    def test_low_complexity_drops_priority_by_1(self):
        m = AgentMatcher(intervention_weight=0.5)
        task = _make_task("t1", complexity=3, priority=5)
        result = m.apply_task_degradation(task)
        assert result.priority == 4

    def test_very_low_complexity_unchanged(self):
        m = AgentMatcher(intervention_weight=0.5)
        task = _make_task("t1", complexity=1, priority=5)
        result = m.apply_task_degradation(task)
        assert result.priority == 5


class TestAgentMatcherMatch:
    """AgentMatcher.match: single task→best agent matching"""

    def test_raises_on_empty_agents(self):
        m = AgentMatcher()
        task = _make_task("t1")
        with pytest.raises(ValueError, match="agent pool is empty"):
            m.match(task, [])

    def test_single_agent_wins(self):
        m = AgentMatcher()
        agent = _make_agent("a1", capabilities={"code": 0.9})
        task = _make_task("t1", capabilities=["code"])
        winner, result = m.match(task, [agent])
        assert winner.agent_id == "a1"
        assert result.agent_id == "a1"

    def test_best_agent_wins(self):
        m = AgentMatcher()
        agents = [
            _make_agent("good", capabilities={"code": 0.9}),
            _make_agent("bad", capabilities={"code": 0.1}),
        ]
        task = _make_task("t1", capabilities=["code"])
        winner, _ = m.match(task, agents)
        assert winner.agent_id == "good"

    def test_capability_score_included_in_breakdown(self):
        m = AgentMatcher()
        agent = _make_agent("a1", capabilities={"code": 0.9})
        task = _make_task("t1", capabilities=["code"])
        _, result = m.match(task, [agent])
        assert "capability" in result.score_breakdown
        assert "performance" in result.score_breakdown
        assert "load" in result.score_breakdown
        assert "specialization" in result.score_breakdown
        assert "reputation" in result.score_breakdown

    def test_reputation_ledger_excludes_isolated_agents(self):
        m = AgentMatcher()
        ledger = MagicMock()
        ledger.is_node_circuit_open.side_effect = lambda aid: aid == "isolated"
        m.set_reputation_source(ledger)

        agents = [
            _make_agent("good", capabilities={"code": 0.9}),
            _make_agent("isolated", capabilities={"code": 0.9}),
        ]
        task = _make_task("t1", capabilities=["code"])
        winner, _ = m.match(task, agents)
        assert winner.agent_id == "good"

    def test_all_agents_isolated_raises(self):
        m = AgentMatcher()
        ledger = MagicMock()
        ledger.is_node_circuit_open.return_value = True
        m.set_reputation_source(ledger)

        agents = [_make_agent("a1", capabilities={"code": 0.9})]
        task = _make_task("t1", capabilities=["code"])
        with pytest.raises(ValueError, match="all agents isolated"):
            m.match(task, agents)

    def test_specialization_bonus(self):
        m = AgentMatcher()
        agents = [
            _make_agent("specialist", capabilities={"code": 0.8}, specialization="code"),
            _make_agent("generalist", capabilities={"code": 0.8}),
        ]
        # task_id must start with specialization domain ("code") for the bonus
        task = _make_task("code_task", capabilities=["code"])
        winner, result = m.match(task, agents)
        assert winner.agent_id == "specialist"
        assert result.score_breakdown["specialization"] >= 0.5


class TestAgentMatcherMatchMultiple:
    """AgentMatcher.match_multiple: batch task→agent assignment"""

    def test_single_task_single_agent(self):
        m = AgentMatcher()
        agent = _make_agent("a1", capabilities={"code": 0.9})
        tasks = [_make_task("t1", capabilities=["code"])]
        assignments = m.match_multiple(tasks, [agent])
        assert assignments["t1"][0] == "a1"

    def test_load_balancing_multiple_tasks(self):
        m = AgentMatcher()
        agents = [
            _make_agent("a1", capabilities={"code": 0.9}),
            _make_agent("a2", capabilities={"code": 0.9}),
        ]
        tasks = [_make_task(f"t{i}", capabilities=["code"]) for i in range(4)]
        assignments = m.match_multiple(tasks, agents, max_assignments_per_agent=3)
        assert len(assignments) == 4
        a1_count = sum(1 for v in assignments.values() if v[0] == "a1")
        assert a1_count >= 1

    def test_exceeds_max_assignments(self):
        m = AgentMatcher()
        agent = _make_agent("a1", capabilities={"code": 0.9})
        tasks = [_make_task(f"t{i}", capabilities=["code"]) for i in range(5)]
        assignments = m.match_multiple(tasks, [agent], max_assignments_per_agent=3)
        assert len(assignments) == 3  # only 3 tasks assigned due to max limit


class TestAgentMatcherRanking:
    """AgentMatcher.get_agent_ranking: ranked list of agents"""

    def test_returns_sorted_by_score(self):
        m = AgentMatcher()
        agents = [
            _make_agent("a1", capabilities={"code": 0.1}),
            _make_agent("a2", capabilities={"code": 0.9}),
        ]
        task = _make_task("t1", capabilities=["code"])
        rankings = m.get_agent_ranking(task, agents)
        assert len(rankings) == 2
        assert rankings[0][0].agent_id == "a2"  # highest score first
        assert rankings[0][1] >= rankings[1][1]


class TestAgentMatcherCapabilityGap:
    """AgentMatcher.get_capability_gap: max gap for each capability"""

    def test_no_gap_when_agent_has_full_proficiency(self):
        m = AgentMatcher()
        caps = {AgentCapability(name="code"): 1.0}
        agent = AgentProfile(agent_id="a1", capabilities=caps)
        task = _make_task("t1", capabilities=["code"])
        gaps = m.get_capability_gap(task, [agent])
        assert gaps[AgentCapability(name="code")] == 0.0

    def test_partial_gap(self):
        m = AgentMatcher()
        caps = {AgentCapability(name="code"): 0.7}
        agent = AgentProfile(agent_id="a1", capabilities=caps)
        task = _make_task("t1", capabilities=["code"])
        gaps = m.get_capability_gap(task, [agent])
        assert round(gaps[AgentCapability(name="code")], 6) == 0.3

    def test_max_gap_when_no_agent_has_capability(self):
        m = AgentMatcher()
        agent = _make_agent("a1", capabilities={"other": 0.9})
        task = _make_task("t1", capabilities=["code"])
        gaps = m.get_capability_gap(task, [agent])
        assert gaps[AgentCapability(name="code")] == 1.0


class TestAgentMatcherSetReputation:
    """AgentMatcher reputation source setup"""

    def test_set_reputation_source_clears_cache(self):
        m = AgentMatcher()
        m._reputation_cache = {"a1": 0.9}
        m.set_reputation_source(MagicMock())
        assert m._reputation_cache == {}

    def test_set_intervention_weight(self):
        m = AgentMatcher()
        m.set_intervention_weight(0.5)
        assert m._intervention_weight == 0.5
