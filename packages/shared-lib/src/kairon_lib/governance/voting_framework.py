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
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Voting Framework ≡ Module
# 内涵 ≝ {Voting, Framework}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, VotingFramework)}
# 功能 ⊢ {Voting_Framework, Init_Voting, Validate_Framework}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any


class VoteType(Enum):
    SIMPLE_MAJORITY = "simple_majority"
    SUPER_MAJORITY = "super_majority"
    UNANIMOUS = "unanimous"
    WEIGHTED = "weighted"


@dataclass
class Ballot:
    ballot_id: str
    title: str
    vote_type: VoteType
    options: list[str]
    deadline: float | None = None
    min_voters: int = 1
    closed: bool = False


@dataclass
class Vote:
    voter: str
    option: str
    weight: float = 1.0
    cast_at: float = 0.0


class VotingFramework:
    metadata_path = "organs/D-Governance/organs/voting_framework.py"

    def __init__(self) -> None:
        super().__init__()
        self._ballots: dict[str, Ballot] = {}
        self._votes: dict[str, list[Vote]] = {}

    def create_ballot(
        self,
        title: str,
        options: list[str],
        vote_type: VoteType,
        min_voters: int = 1,
        deadline: float | None = None,
    ) -> Ballot:
        if len(options) < 2:
            raise ValueError("Ballot must have at least 2 options")
        ballot_id = f"BALLOT-{uuid.uuid4().hex[:8]}"
        ballot = Ballot(
            ballot_id=ballot_id,
            title=title,
            vote_type=vote_type,
            options=list(options),
            deadline=deadline,
            min_voters=min_voters,
        )
        self._ballots[ballot_id] = ballot
        self._votes[ballot_id] = []
        return ballot

    def cast_vote(self, ballot_id: str, voter: str, option: str, weight: float = 1.0) -> None:
        ballot = self._get_ballot(ballot_id)
        if ballot.closed:
            raise ValueError("Ballot is closed")
        if ballot.deadline is not None and time.time() > ballot.deadline:
            raise ValueError("Ballot deadline has passed")
        if option not in ballot.options:
            raise ValueError(f"Invalid option: {option}")
        existing = [v for v in self._votes[ballot_id] if v.voter == voter]
        if existing:
            raise ValueError(f"Voter {voter} has already voted")
        vote = Vote(voter=voter, option=option, weight=weight, cast_at=time.time())
        self._votes[ballot_id].append(vote)

    def get_results(self, ballot_id: str) -> dict[str, float]:
        ballot = self._get_ballot(ballot_id)
        results: dict[str, float] = dict.fromkeys(ballot.options, 0.0)
        for vote in self._votes[ballot_id]:
            if ballot.vote_type == VoteType.WEIGHTED:
                results[vote.option] += vote.weight
            else:
                results[vote.option] += 1.0
        return results

    def is_decided(self, ballot_id: str) -> bool:
        ballot = self._get_ballot(ballot_id)
        votes = self._votes[ballot_id]
        if len(votes) < ballot.min_voters:
            return False
        results = self.get_results(ballot_id)
        total = sum(results.values())
        if total == 0:
            return False
        if ballot.vote_type == VoteType.UNANIMOUS:
            top = max(results.values())
            return top == total and total >= ballot.min_voters
        if ballot.vote_type == VoteType.SUPER_MAJORITY:
            top = max(results.values())
            return top / total >= 2.0 / 3.0
        # SIMPLE_MAJORITY and WEIGHTED
        top = max(results.values())
        return top > total / 2.0

    def get_winner(self, ballot_id: str) -> str | None:
        if not self.is_decided(ballot_id):
            return None
        results = self.get_results(ballot_id)
        return max(results, key=results.get)

    def close_ballot(self, ballot_id: str) -> dict[str, Any]:
        ballot = self._get_ballot(ballot_id)
        ballot.closed = True
        return {
            "ballot_id": ballot_id,
            "title": ballot.title,
            "results": self.get_results(ballot_id),
            "winner": self.get_winner(ballot_id),
            "total_votes": len(self._votes[ballot_id]),
            "decided": self.is_decided(ballot_id),
        }

    def list_ballots(self, open_only: bool = False) -> list[Ballot]:
        if open_only:
            return [b for b in self._ballots.values() if not b.closed]
        return list(self._ballots.values())

    def _get_ballot(self, ballot_id: str) -> Ballot:
        ballot = self._ballots.get(ballot_id)
        if ballot is None:
            raise KeyError(f"Ballot not found: {ballot_id}")
        return ballot
