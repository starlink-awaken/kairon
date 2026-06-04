"""Reward Engine — calculate and distribute rewards based on task completion quality."""

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class RewardType(StrEnum):
    BASE = "base"
    QUALITY = "quality"
    SPEED = "speed"
    BONUS = "bonus"


@dataclass
class Reward:
    reward_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""
    task_id: str = ""
    reward_type: RewardType = RewardType.BASE
    amount: float = 0.0
    reason: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class RewardConfig:
    base_reward: float = 10.0
    quality_multiplier: float = 1.5
    speed_multiplier: float = 1.2
    max_bonus: float = 100.0


class RewardEngine:
    """Calculate and distribute rewards based on task completion."""

    def __init__(self, config: RewardConfig | None = None):
        self.config = config or RewardConfig()
        self._history: dict[str, list[Reward]] = {}
        self._pending: dict[str, float] = {}

    def calculate(self, agent_id: str, task_id: str, quality_score: float,
                  completion_time_sec: float, expected_time_sec: float) -> Reward:
        base = self.config.base_reward
        quality_bonus = base * (quality_score - 0.5) * self.config.quality_multiplier
        speed_ratio = expected_time_sec / max(completion_time_sec, 0.1)
        speed_bonus = base * min(speed_ratio - 1.0, 1.0) * self.config.speed_multiplier
        total = max(0.0, min(base + quality_bonus + speed_bonus, self.config.max_bonus))
        reward = Reward(agent_id=agent_id, task_id=task_id,
                        reward_type=RewardType.BASE if abs(total - base) < 1 else RewardType.QUALITY,
                        amount=round(total, 2))
        self._history.setdefault(agent_id, []).append(reward)
        self._pending[agent_id] = self._pending.get(agent_id, 0) + total
        return reward

    def get_pending(self, agent_id: str) -> float:
        return self._pending.get(agent_id, 0.0)

    def payout(self, agent_id: str) -> float:
        return self._pending.pop(agent_id, 0.0)

    def get_history(self, agent_id: str, limit: int = 50) -> list[Reward]:
        return self._history.get(agent_id, [])[-limit:]

    def get_stats(self, agent_id: str) -> dict:
        rewards = self._history.get(agent_id, [])
        if not rewards:
            return {"total": 0, "count": 0, "avg": 0.0, "max": 0.0}
        amounts = [r.amount for r in rewards]
        return {"total": sum(amounts), "count": len(amounts), "avg": sum(amounts) / len(amounts), "max": max(amounts)}
