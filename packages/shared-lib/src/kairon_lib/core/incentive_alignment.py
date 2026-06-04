from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Incentive Alignment ≡ Module
# 内涵 ≝ {Incentive, Alignment}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, IncentiveAlignment)}
# 功能 ⊢ {Incentive_Alignment, Init_Incentive, Validate_Alignment}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Incentive:
    incentive_id: str
    agent_id: str
    action: str
    reward: float
    timestamp: float


@dataclass
class AlignmentScore:
    agent_id: str
    alignment: float
    total_rewards: float
    actions_count: int


class IncentiveAlignmentEngine:
    """Tracks agent incentive alignment against defined goals."""

    def __init__(self) -> None:
        self._goals: dict[str, dict] = {}  # goal_id -> {desired_actions, reward}
        self._incentives: list[Incentive] = []
        self._agent_aligned: dict[str, int] = defaultdict(int)
        self._agent_total: dict[str, int] = defaultdict(int)
        self._agent_rewards: dict[str, float] = defaultdict(float)
        self._goal_action_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._incentive_counter: int = 0

    def define_goal(self, goal_id: str, desired_actions: list[str], reward_per_action: float) -> None:
        self._goals[goal_id] = {
            "desired_actions": set(desired_actions),
            "reward_per_action": reward_per_action,
        }

    def record_action(self, agent_id: str, action: str) -> float:
        self._agent_total[agent_id] += 1
        reward = 0.0
        for goal_id, goal in self._goals.items():
            if action in goal["desired_actions"]:
                reward = goal["reward_per_action"]
                self._agent_aligned[agent_id] += 1
                self._goal_action_counts[goal_id][action] += 1
                break

        self._agent_rewards[agent_id] += reward
        self._incentive_counter += 1
        self._incentives.append(
            Incentive(
                incentive_id=f"inc-{self._incentive_counter}",
                agent_id=agent_id,
                action=action,
                reward=reward,
                timestamp=time.time(),
            )
        )
        return reward

    def get_alignment(self, agent_id: str) -> AlignmentScore:
        total = self._agent_total[agent_id]
        aligned = self._agent_aligned[agent_id]
        return AlignmentScore(
            agent_id=agent_id,
            alignment=aligned / total if total > 0 else 0.0,
            total_rewards=self._agent_rewards[agent_id],
            actions_count=total,
        )

    def get_leaderboard(self, top_n: int = 10) -> list[AlignmentScore]:
        agents = set(self._agent_total.keys())
        scores = [self.get_alignment(a) for a in agents]
        scores.sort(key=lambda s: s.alignment, reverse=True)
        return scores[:top_n]

    def get_misaligned_agents(self) -> list[str]:
        result: list[str] = []
        for agent_id in self._agent_total:
            score = self.get_alignment(agent_id)
            if score.alignment < 0.5:
                result.append(agent_id)
        return sorted(result)

    def get_goal_progress(self, goal_id: str) -> dict:
        goal = self._goals.get(goal_id)
        if goal is None:
            raise KeyError(f"Goal {goal_id} not found")
        action_counts = self._goal_action_counts.get(goal_id, {})
        total_actions = sum(action_counts.values())
        return {
            "goal_id": goal_id,
            "desired_actions": sorted(goal["desired_actions"]),
            "action_counts": dict(action_counts),
            "total_aligned_actions": total_actions,
            "total_reward_distributed": total_actions * goal["reward_per_action"],
        }

    def adjust_rewards(self, goal_id: str, new_reward: float) -> None:
        goal = self._goals.get(goal_id)
        if goal is None:
            raise KeyError(f"Goal {goal_id} not found")
        goal["reward_per_action"] = new_reward
