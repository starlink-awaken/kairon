"""Tests for kairon_lib.incentive_alignment — IncentiveAlignmentEngine."""

import pytest

try:
    from kairon_lib.incentive_alignment import IncentiveAlignmentEngine
except ImportError:
    pytestmark = pytest.mark.skip(reason="test requires archived kairon_lib module")  # type: ignore[name-defined]


class TestIncentiveAlignmentEngine:
    def test_define_goal(self):
        engine = IncentiveAlignmentEngine()
        engine.define_goal("goal1", ["research", "review"], reward_per_action=10.0)
        assert "goal1" in engine._goals
        assert engine._goals["goal1"]["reward_per_action"] == 10.0

    def test_record_aligned_action(self):
        engine = IncentiveAlignmentEngine()
        engine.define_goal("goal1", ["research"], reward_per_action=5.0)
        reward = engine.record_action("agent-1", "research")
        assert reward == 5.0
        score = engine.get_alignment("agent-1")
        assert score.alignment == 1.0
        assert score.total_rewards == 5.0

    def test_record_misaligned_action(self):
        engine = IncentiveAlignmentEngine()
        engine.define_goal("goal1", ["research"], reward_per_action=5.0)
        reward = engine.record_action("agent-1", "chat")
        assert reward == 0.0
        score = engine.get_alignment("agent-1")
        assert score.alignment == 0.0
        assert score.total_rewards == 0.0

    def test_partial_alignment(self):
        engine = IncentiveAlignmentEngine()
        engine.define_goal("goal1", ["research"], reward_per_action=5.0)
        engine.record_action("agent-1", "research")
        engine.record_action("agent-1", "chat")
        engine.record_action("agent-1", "research")
        score = engine.get_alignment("agent-1")
        assert score.alignment == 2.0 / 3.0
        assert score.actions_count == 3
        assert score.total_rewards == 10.0

    def test_get_leaderboard(self):
        engine = IncentiveAlignmentEngine()
        engine.define_goal("goal1", ["good"], reward_per_action=10.0)
        engine.record_action("agent-a", "good")
        engine.record_action("agent-a", "good")
        engine.record_action("agent-b", "bad")
        leaderboard = engine.get_leaderboard(top_n=5)
        assert len(leaderboard) == 2
        assert leaderboard[0].agent_id == "agent-a"
        assert leaderboard[0].alignment == 1.0

    def test_get_misaligned_agents(self):
        engine = IncentiveAlignmentEngine()
        engine.define_goal("goal1", ["good"], reward_per_action=10.0)
        engine.record_action("agent-a", "good")
        engine.record_action("agent-b", "bad")
        engine.record_action("agent-c", "good")
        misaligned = engine.get_misaligned_agents()
        assert misaligned == ["agent-b"]

    def test_get_goal_progress(self):
        engine = IncentiveAlignmentEngine()
        engine.define_goal("goal1", ["research", "review"], reward_per_action=5.0)
        engine.record_action("agent-1", "research")
        engine.record_action("agent-1", "review")
        progress = engine.get_goal_progress("goal1")
        assert progress["goal_id"] == "goal1"
        assert progress["total_aligned_actions"] == 2
        assert progress["total_reward_distributed"] == 10.0

    def test_get_goal_progress_not_found(self):
        engine = IncentiveAlignmentEngine()
        with pytest.raises(KeyError):
            engine.get_goal_progress("nonexistent")

    def test_adjust_rewards(self):
        engine = IncentiveAlignmentEngine()
        engine.define_goal("goal1", ["research"], reward_per_action=5.0)
        engine.adjust_rewards("goal1", 10.0)
        reward = engine.record_action("agent-1", "research")
        assert reward == 10.0

    def test_adjust_rewards_not_found(self):
        engine = IncentiveAlignmentEngine()
        with pytest.raises(KeyError):
            engine.adjust_rewards("nonexistent", 10.0)

    def test_zero_actions_alignment(self):
        engine = IncentiveAlignmentEngine()
        score = engine.get_alignment("unknown-agent")
        assert score.alignment == 0.0
        assert score.actions_count == 0
        assert score.total_rewards == 0.0
