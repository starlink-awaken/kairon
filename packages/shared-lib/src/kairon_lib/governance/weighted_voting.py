"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Weighted Voting ≡ Module
# 内涵 ≝ {Weighted, Voting}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, WeightedVoting)}
# 功能 ⊢ {Weighted_Voting, Init_Weighted, Validate_Voting}
# =============================================================================

"""---
Type: WeightedVoting
Layer: L2
Domain: D-Governance
Status: ACTIVE
Updated: "2026-04-02"
Authority: 2
Compiled-From: []
Keywords: [voting, weighted, governance, stake]
---"""
"""加权投票模块 - 基于权重的投票系统"""

from dataclasses import dataclass


@dataclass
class WeightedBallot:
    voter_id: str
    choice: str
    weight: float


class WeightedVoting:
    """加权投票系统"""

    def __init__(self) -> None:
        self._weights: dict[str, float] = {}
        self._ballots: dict[str, list[WeightedBallot]] = {}

    def set_voter_weight(self, voter_id: str, weight: float) -> None:
        """设置投票者权重"""
        self._weights[voter_id] = weight

    def cast_weighted_vote(self, vote_id: str, voter_id: str, choice: str) -> bool:
        """投递加权选票"""
        weight = self._weights.get(voter_id, 1.0)
        if vote_id not in self._ballots:
            self._ballots[vote_id] = []
        self._ballots[vote_id].append(WeightedBallot(voter_id=voter_id, choice=choice, weight=weight))
        return True

    def tally_weighted_results(self, vote_id: str) -> dict[str, float]:
        """统计加权票数"""
        if vote_id not in self._ballots:
            return {}
        results: dict[str, float] = {}
        for ballot in self._ballots[vote_id]:
            results[ballot.choice] = results.get(ballot.choice, 0.0) + ballot.weight
        return results

    def get_total_weight(self, vote_id: str) -> float:
        """获取总权重"""
        if vote_id not in self._ballots:
            return 0.0
        return sum(b.weight for b in self._ballots[vote_id])
