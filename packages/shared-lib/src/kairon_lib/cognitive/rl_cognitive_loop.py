from __future__ import annotations

"""
---
Type: Organ
Status: Active
Layer: D-Governance
Owner: '@Prime'
Constraint: '[!!] REINFORCEMENT_LEARNING'
Summary: RLCognitiveLoop — 强化学习增强的认知循环，自动优化决策策略
Tags:
- reinforcement-learning
- rl
- cognitive
- optimization
- learning
---
Extracted from SharedBrain D_Governance → kairon_lib.
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Rl Cognitive Loop ≡ Module
# 内涵 ≝ {Rl, Cognitive, Loop}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, RlCognitiveLoop)}
# 功能 ⊢ {Rl_Cognitive, Cognitive_Loop, Loop_Init}
# =============================================================================


import logging
import random
from collections import defaultdict
from dataclasses import dataclass

_log = logging.getLogger(__name__)


@dataclass
class RLState:
    """强化学习状态"""

    problem_type: str
    system_load: str  # "low", "medium", "high"
    urgency: str  # "low", "medium", "high"
    previous_decision: str | None = None


@dataclass
class RLAction:
    """强化学习动作"""

    thinking_mode: str
    deliberation_depth: int  # 1-5
    consensus_threshold: float  # 0.5-1.0


@dataclass
class RLExperience:
    """学习经验"""

    state: RLState
    action: RLAction
    reward: float
    next_state: RLState
    timestamp: float


class RLCognitiveLoop:
    """强化学习认知循环

    核心能力:
    - Q-learning学习最优决策策略
    - 根据系统状态自适应调整
    - 从历史决策中学习优化
    - 自动平衡效率与质量
    """

    # 学习参数
    ALPHA = 0.1  # 学习率
    GAMMA = 0.9  # 折扣因子
    EPSILON = 0.1  # 探索率

    def __init__(self) -> None:
        # Q表: (state_key, action_key) -> value
        self._q_table: dict[tuple[str, str], float] = defaultdict(float)

        # 经验回放缓冲
        self._experience_buffer: list[RLExperience] = []
        self._max_buffer_size = 1000

        # 决策统计
        self._decision_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_reward": 0.0})

    def _state_to_key(self, state: RLState) -> str:
        """状态编码"""
        return f"{state.problem_type}:{state.system_load}:{state.urgency}:{state.previous_decision or 'none'}"

    def _action_to_key(self, action: RLAction) -> str:
        """动作编码"""
        return f"{action.thinking_mode}:{action.deliberation_depth}:{action.consensus_threshold:.1f}"

    def select_action(self, state: RLState) -> RLAction:
        """选择动作 (ε-贪心策略)"""
        state_key = self._state_to_key(state)

        # ε概率随机探索
        if random.random() < self.EPSILON:  # noqa: S311
            return self._random_action()

        # 否则选择Q值最高的动作
        best_action = None
        best_q_value = float("-inf")

        for action in self._possible_actions():
            action_key = self._action_to_key(action)
            q_value = self._q_table[(state_key, action_key)]

            if q_value > best_q_value:
                best_q_value = q_value
                best_action = action

        return best_action or self._random_action()

    def _random_action(self) -> RLAction:
        """随机动作"""
        modes = ["council", "first_principles", "red_team", "creative", "science"]
        return RLAction(
            thinking_mode=random.choice(modes),  # noqa: S311
            deliberation_depth=random.randint(1, 5),  # noqa: S311
            consensus_threshold=random.choice([0.5, 0.6, 0.7, 0.8, 0.9, 1.0]),  # noqa: S311
        )

    def _possible_actions(self) -> list[RLAction]:
        """所有可能的动作"""
        actions = []
        modes = ["council", "first_principles", "red_team", "creative", "science"]

        for mode in modes:
            for depth in [2, 3, 4]:
                for threshold in [0.6, 0.7, 0.8, 0.9]:
                    actions.append(RLAction(mode, depth, threshold))

        return actions

    def learn(self, experience: RLExperience) -> None:
        """从经验中学习"""
        # 存储经验
        self._experience_buffer.append(experience)
        if len(self._experience_buffer) > self._max_buffer_size:
            self._experience_buffer.pop(0)

        # Q-learning更新
        state_key = self._state_to_key(experience.state)
        action_key = self._action_to_key(experience.action)
        next_state_key = self._state_to_key(experience.next_state)

        # 计算TD目标
        current_q = self._q_table[(state_key, action_key)]

        # 获取下一个状态的最大Q值
        max_next_q = max(
            (self._q_table[(next_state_key, self._action_to_key(a))] for a in self._possible_actions()),
            default=0.0,
        )

        # Q值更新
        td_target = experience.reward + self.GAMMA * max_next_q
        self._q_table[(state_key, action_key)] = current_q + self.ALPHA * (td_target - current_q)

        # 更新统计
        action_str = f"{experience.action.thinking_mode}_d{experience.action.deliberation_depth}"
        self._decision_stats[action_str]["count"] += 1
        self._decision_stats[action_str]["total_reward"] += experience.reward

        _log.debug(f"RL Learn: {state_key} -> {action_key}, reward={experience.reward:.2f}")

    def calculate_reward(
        self,
        decision_time: float,  # 决策耗时(秒)
        consensus_reached: bool,
        decision_quality: float,  # 0-1
        system_health_delta: float,  # 决策后系统健康变化
    ) -> float:
        """计算奖励"""
        # 时间效率奖励 (越快越好)
        time_reward = max(0, 10 - decision_time) / 10

        # 共识奖励
        consensus_reward = 1.0 if consensus_reached else -0.5

        # 质量奖励
        quality_reward = decision_quality * 2

        # 系统健康奖励
        health_reward = system_health_delta * 3

        # 综合奖励
        total_reward = time_reward + consensus_reward + quality_reward + health_reward

        return max(-5.0, min(5.0, total_reward))

    def get_policy_stats(self) -> dict:
        """获取策略统计"""
        if not self._decision_stats:
            return {"status": "no_data"}

        best_action = max(self._decision_stats.items(), key=lambda x: x[1]["total_reward"] / max(x[1]["count"], 1))

        return {
            "total_decisions": sum(s["count"] for s in self._decision_stats.values()),
            "q_table_size": len(self._q_table),
            "experience_buffer_size": len(self._experience_buffer),
            "best_action": best_action[0],
            "best_action_avg_reward": best_action[1]["total_reward"] / best_action[1]["count"],
        }
