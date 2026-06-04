"""Tests for rewards — RewardEngine and reward data models."""

from eu_pricing.rewards import Reward, RewardConfig, RewardEngine, RewardType


class TestRewardType:
    """Tests for RewardType enum."""

    def test_values(self):
        assert RewardType.BASE.value == "base"
        assert RewardType.QUALITY.value == "quality"
        assert RewardType.SPEED.value == "speed"
        assert RewardType.BONUS.value == "bonus"

    def test_is_string_enum(self):
        assert isinstance(RewardType.BASE, str)


class TestReward:
    """Tests for Reward dataclass."""

    def test_default_reward_id(self):
        r = Reward(agent_id="a1", task_id="t1", amount=10.0)
        assert len(r.reward_id) == 12
        assert r.agent_id == "a1"
        assert r.task_id == "t1"
        assert r.amount == 10.0

    def test_reward_type_default(self):
        r = Reward(agent_id="a1", task_id="t1", amount=10.0)
        assert r.reward_type == RewardType.BASE

    def test_reward_timestamp_set(self):
        r = Reward(agent_id="a1", task_id="t1", amount=10.0)
        assert r.timestamp > 0


class TestRewardConfig:
    """Tests for RewardConfig dataclass."""

    def test_default_values(self):
        config = RewardConfig()
        assert config.base_reward == 10.0
        assert config.quality_multiplier == 1.5
        assert config.speed_multiplier == 1.2
        assert config.max_bonus == 100.0

    def test_custom_values(self):
        config = RewardConfig(base_reward=20.0, max_bonus=50.0)
        assert config.base_reward == 20.0
        assert config.max_bonus == 50.0


class TestRewardEngine:
    """Tests for RewardEngine reward calculation logic."""

    def setup_method(self):
        self.engine = RewardEngine()

    def test_calculate_default_config(self):
        """calculate should return a Reward with default config."""
        reward = self.engine.calculate("agent-1", "task-1", quality_score=0.8,
                                       completion_time_sec=5.0, expected_time_sec=10.0)
        assert isinstance(reward, Reward)
        assert reward.agent_id == "agent-1"
        assert reward.task_id == "task-1"
        assert reward.amount > 0

    def test_calculate_base_only(self):
        """When quality is 0.5 and time matches exactly, only base reward is given."""
        reward = self.engine.calculate("agent-2", "task-2", quality_score=0.5,
                                       completion_time_sec=10.0, expected_time_sec=10.0)
        # quality_bonus = 10 * (0.5 - 0.5) * 1.5 = 0
        # speed_ratio = 10/10 = 1.0, speed_bonus = 10 * 0 * 1.2 = 0
        # total = 10.0
        assert reward.amount == 10.0

    def test_calculate_quality_bonus(self):
        """High quality score should add quality bonus."""
        reward = self.engine.calculate("agent-3", "task-3", quality_score=1.0,
                                       completion_time_sec=10.0, expected_time_sec=10.0)
        # quality_bonus = 10 * (1.0 - 0.5) * 1.5 = 7.5
        # total = 10 + 7.5 = 17.5
        assert reward.amount == 17.5

    def test_calculate_speed_bonus(self):
        """Completing faster than expected should add speed bonus."""
        reward = self.engine.calculate("agent-4", "task-4", quality_score=0.5,
                                       completion_time_sec=2.0, expected_time_sec=10.0)
        # quality_bonus = 0
        # speed_ratio = 10/2 = 5.0, speed_bonus = 10 * min(5-1, 1) * 1.2 = 10 * 1.0 * 1.2 = 12.0
        # total = min(10 + 0 + 12, 100) = min(22, 100) = 22.0
        assert reward.amount == 22.0

    def test_calculate_capped_at_max_bonus(self):
        """Total reward should be capped at max_bonus."""
        config = RewardConfig(base_reward=50.0, max_bonus=100.0)
        engine = RewardEngine(config=config)
        reward = engine.calculate("agent-5", "task-5", quality_score=1.0,
                                  completion_time_sec=0.1, expected_time_sec=10.0)
        assert reward.amount <= 100.0

    def test_calculate_minimum_zero(self):
        """Total reward should not go below 0."""
        config = RewardConfig(base_reward=0.0, max_bonus=100.0)
        engine = RewardEngine(config=config)
        reward = engine.calculate("agent-6", "task-6", quality_score=0.0,
                                  completion_time_sec=100.0, expected_time_sec=10.0)
        assert reward.amount >= 0.0

    def test_calculate_with_custom_config(self):
        """Custom RewardConfig should be used correctly."""
        config = RewardConfig(base_reward=20.0, quality_multiplier=2.0,
                              speed_multiplier=1.0, max_bonus=50.0)
        engine = RewardEngine(config=config)
        reward = engine.calculate("agent-7", "task-7", quality_score=0.8,
                                  completion_time_sec=5.0, expected_time_sec=10.0)
        # quality_bonus = 20 * (0.8 - 0.5) * 2.0 = 12.0
        # speed_ratio = 10/5 = 2.0, speed_bonus = 20 * min(2-1, 1) * 1.0 = 20 * 1.0 = 20.0
        # total = min(20 + 12 + 20, 50) = min(52, 50) = 50.0
        assert reward.amount == 50.0

    def test_calculate_adds_to_history(self):
        """calculate should store rewards in history."""
        self.engine.calculate("agent-8", "task-8a", quality_score=0.7,
                              completion_time_sec=5.0, expected_time_sec=10.0)
        self.engine.calculate("agent-8", "task-8b", quality_score=0.9,
                              completion_time_sec=3.0, expected_time_sec=10.0)
        history = self.engine.get_history("agent-8")
        assert len(history) == 2

    def test_get_pending_no_rewards(self):
        """get_pending should return 0 for agents with no rewards."""
        assert self.engine.get_pending("agent-none") == 0.0

    def test_get_pending_after_calculation(self):
        """get_pending should accumulate after calculations."""
        self.engine.calculate("agent-9", "task-9", quality_score=0.5,
                              completion_time_sec=10.0, expected_time_sec=10.0)
        # base = 10.0
        assert self.engine.get_pending("agent-9") == 10.0

    def test_payout_returns_and_clears_pending(self):
        """payout should return the pending amount and clear it."""
        self.engine.calculate("agent-10", "task-10", quality_score=0.5,
                              completion_time_sec=10.0, expected_time_sec=10.0)
        amount = self.engine.payout("agent-10")
        assert amount == 10.0
        assert self.engine.get_pending("agent-10") == 0.0

    def test_payout_no_pending(self):
        """payout on an agent with no pending should return 0."""
        assert self.engine.payout("agent-none") == 0.0

    def test_get_history_empty(self):
        """get_history for an unknown agent should return empty list."""
        assert self.engine.get_history("unknown") == []

    def test_get_history_limit(self):
        """get_history should respect the limit parameter."""
        for i in range(10):
            self.engine.calculate("agent-11", f"task-{i}", quality_score=0.5,
                                  completion_time_sec=10.0, expected_time_sec=10.0)
        assert len(self.engine.get_history("agent-11", limit=3)) == 3

    def test_get_stats_no_history(self):
        """get_stats for an agent with no history should return zeros."""
        stats = self.engine.get_stats("agent-none")
        assert stats == {"total": 0, "count": 0, "avg": 0.0, "max": 0.0}

    def test_get_stats_with_history(self):
        """get_stats should compute correct aggregate statistics."""
        self.engine.calculate("agent-12", "task-12a", quality_score=0.5,
                              completion_time_sec=10.0, expected_time_sec=10.0)
        self.engine.calculate("agent-12", "task-12b", quality_score=0.5,
                              completion_time_sec=10.0, expected_time_sec=10.0)
        stats = self.engine.get_stats("agent-12")
        # Each call yields base=10.0
        assert stats["total"] == 20.0
        assert stats["count"] == 2
        assert stats["avg"] == 10.0
        assert stats["max"] == 10.0
