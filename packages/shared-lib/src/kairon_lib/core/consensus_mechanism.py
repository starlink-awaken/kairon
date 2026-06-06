from __future__ import annotations

"""
---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Updated: 2026-03-17
Authority: 4
Keywords: [consensus, raft, voting, quorum, decision, threshold, sqlite]
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# ConsensusMechanism ≡ Organ
# 内涵 ≝ {vote_id, proposal, voter_id, vote_weight, decision}
# 外延 ≝ {v | v ∈ D-Governance ∧ consensus_vote(v)}
# 功能 ⊢ {RequestVote, CastVote, CalculateThreshold, CreateProposal,
#          GetProposal, GetVotes, TallyVotes, CloseProposal}
# =============================================================================

import logging
import sqlite3
import threading
import uuid

# Local governance types (adapted from Z-Core law layer via facade pattern)
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any


class DecisionStatus(Enum):
    """Possible outcomes of a governance decision."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


@dataclass
class DecisionResult:
    """The outcome of a governance decision."""

    request_id: str
    status: DecisionStatus
    reason: str = ""
    decided_by: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


from kairon_utils.sqlite_utils import managed_connection

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VoteType enum
# ---------------------------------------------------------------------------


class VoteType(StrEnum):
    """Type of vote in consensus."""

    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


# ---------------------------------------------------------------------------
# ProposalStatus enum
# ---------------------------------------------------------------------------


class ProposalStatus(StrEnum):
    """Status of a consensus proposal."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# ConsensusProposal dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConsensusProposal:
    """Represents a proposal requiring consensus."""

    id: str
    title: str
    description: str
    proposer_id: str
    quorum_threshold: float  # 0.0-1.0, minimum participation
    approval_threshold: float  # 0.0-1.0, minimum approval ratio
    status: ProposalStatus
    created_at: str
    closes_at: str
    closed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "proposer_id": self.proposer_id,
            "quorum_threshold": self.quorum_threshold,
            "approval_threshold": self.approval_threshold,
            "status": self.status.value,
            "created_at": self.created_at,
            "closes_at": self.closes_at,
            "closed_at": self.closed_at,
        }


# ---------------------------------------------------------------------------
# ConsensusVote dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConsensusVote:
    """Represents a vote on a proposal."""

    id: str
    proposal_id: str
    voter_id: str
    vote_type: VoteType
    weight: float  # Voter weight, typically 1.0
    voted_at: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_id": self.proposal_id,
            "voter_id": self.voter_id,
            "vote_type": self.vote_type.value,
            "weight": self.weight,
            "voted_at": self.voted_at,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# VoteTally dataclass
# ---------------------------------------------------------------------------


@dataclass
class VoteTally:
    """Result of vote counting."""

    proposal_id: str
    total_votes: int
    total_weight: float
    approve_weight: float
    reject_weight: float
    abstain_weight: float
    quorum_reached: bool
    approval_reached: bool
    result: ProposalStatus
    tallied_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "total_votes": self.total_votes,
            "total_weight": self.total_weight,
            "approve_weight": self.approve_weight,
            "reject_weight": self.reject_weight,
            "abstain_weight": self.abstain_weight,
            "quorum_reached": self.quorum_reached,
            "approval_reached": self.approval_reached,
            "result": self.result.value,
            "tallied_at": self.tallied_at,
        }


# ---------------------------------------------------------------------------
# ConsensusMechanism
# ---------------------------------------------------------------------------


class ConsensusMechanism:
    """Voting and consensus mechanism based on Raft-inspired protocol.

    Implements :class:`IConsensusMechanism` from Z-Core/L2-Law.

    Supports weighted voting, quorum requirements, and configurable approval thresholds.
    Votes are persisted to SQLite for auditability.

    SQLite at ``data/db/organs/governance/consensus_mechanism.db``.
    Thread-safe; uses a per-instance Lock.

    BOS-URI endpoints
    -----------------
    ``bos://governance/consensus/request``  — request a vote
    ``bos://governance/consensus/cast``      — cast a vote
    ``bos://governance/consensus/tally``     — tally votes
    """

    _DEFAULT_DB: str = "data/db/organs/governance/consensus_mechanism.db"
    _lock: threading.Lock

    # Default thresholds
    _DEFAULT_QUORUM: float = 0.5  # 50% participation
    _DEFAULT_APPROVAL: float = 0.67  # 67% approval (supermajority)

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        _log.debug("[ConsensusMechanism] db=%s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> Any:
        """Get database connection context manager."""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return managed_connection(conn)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS consensus_proposals (
                    id                  TEXT PRIMARY KEY,
                    title               TEXT NOT NULL,
                    description         TEXT NOT NULL,
                    proposer_id         TEXT NOT NULL,
                    quorum_threshold    REAL NOT NULL DEFAULT 0.5,
                    approval_threshold  REAL NOT NULL DEFAULT 0.67,
                    status              TEXT NOT NULL DEFAULT 'pending',
                    created_at          TEXT NOT NULL,
                    closes_at           TEXT NOT NULL,
                    closed_at           TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_proposal_status ON consensus_proposals(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_proposal_closes ON consensus_proposals(closes_at)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS consensus_votes (
                    id            TEXT PRIMARY KEY,
                    proposal_id   TEXT NOT NULL,
                    voter_id      TEXT NOT NULL,
                    vote_type     TEXT NOT NULL,
                    weight        REAL NOT NULL DEFAULT 1.0,
                    voted_at      TEXT NOT NULL,
                    reason        TEXT,
                    UNIQUE(proposal_id, voter_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vote_proposal ON consensus_votes(proposal_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vote_voter ON consensus_votes(voter_id)")
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _row_to_proposal(self, row: sqlite3.Row) -> ConsensusProposal:
        return ConsensusProposal(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            proposer_id=row["proposer_id"],
            quorum_threshold=row["quorum_threshold"],
            approval_threshold=row["approval_threshold"],
            status=ProposalStatus(row["status"]),
            created_at=row["created_at"],
            closes_at=row["closes_at"],
            closed_at=row["closed_at"],
        )

    def _row_to_vote(self, row: sqlite3.Row) -> ConsensusVote:
        return ConsensusVote(
            id=row["id"],
            proposal_id=row["proposal_id"],
            voter_id=row["voter_id"],
            vote_type=VoteType(row["vote_type"]),
            weight=row["weight"],
            voted_at=row["voted_at"],
            reason=row["reason"],
        )

    # ------------------------------------------------------------------
    # Public API: Proposal Management
    # ------------------------------------------------------------------

    def create_proposal(
        self,
        title: str,
        description: str,
        proposer_id: str,
        quorum_threshold: float | None = None,
        approval_threshold: float | None = None,
        duration_hours: float = 24.0,
    ) -> ConsensusProposal:
        """Create a new proposal requiring consensus."""
        proposal_id = str(uuid.uuid4())
        now = self._now()

        from datetime import timedelta

        closes_at = (datetime.now(UTC) + timedelta(hours=duration_hours)).isoformat()

        proposal = ConsensusProposal(
            id=proposal_id,
            title=title,
            description=description,
            proposer_id=proposer_id,
            quorum_threshold=quorum_threshold or self._DEFAULT_QUORUM,
            approval_threshold=approval_threshold or self._DEFAULT_APPROVAL,
            status=ProposalStatus.PENDING,
            created_at=now,
            closes_at=closes_at,
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO consensus_proposals
                    (id, title, description, proposer_id, quorum_threshold, approval_threshold, status, created_at, closes_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.id,
                    proposal.title,
                    proposal.description,
                    proposal.proposer_id,
                    proposal.quorum_threshold,
                    proposal.approval_threshold,
                    proposal.status.value,
                    proposal.created_at,
                    proposal.closes_at,
                ),
            )
            conn.commit()

        _log.debug("[ConsensusMechanism] created proposal %s", proposal_id)
        return proposal

    def get_proposal(self, proposal_id: str) -> ConsensusProposal | None:
        """Retrieve a proposal by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM consensus_proposals WHERE id = ?", (proposal_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_proposal(row)

    def close_proposal(self, proposal_id: str) -> ConsensusProposal | None:
        """Close a proposal and calculate final result."""
        proposal = self.get_proposal(proposal_id)
        if proposal is None or proposal.status != ProposalStatus.PENDING:
            return None

        tally = self.tally_votes(proposal_id)

        with self._lock, self._connect() as conn:
            proposal.status = tally.result
            proposal.closed_at = self._now()

            conn.execute(
                "UPDATE consensus_proposals SET status = ?, closed_at = ? WHERE id = ?",
                (proposal.status.value, proposal.closed_at, proposal_id),
            )
            conn.commit()

        _log.info(
            "[ConsensusMechanism] closed proposal %s with result %s",
            proposal_id,
            proposal.status.value,
        )
        return proposal

    # ------------------------------------------------------------------
    # Public API: Voting
    # ------------------------------------------------------------------

    def request_vote(self, proposal_id: str, voter_id: str) -> bool:
        """Request a vote from a voter (for notification purposes)."""
        proposal = self.get_proposal(proposal_id)
        if proposal is None or proposal.status != ProposalStatus.PENDING:
            return False

        # Check if already voted
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM consensus_votes WHERE proposal_id = ? AND voter_id = ?",
                (proposal_id, voter_id),
            ).fetchone()

        return existing is None

    def cast_vote(
        self,
        proposal_id: str,
        voter_id: str,
        vote_type: VoteType,
        weight: float = 1.0,
        reason: str | None = None,
    ) -> ConsensusVote | None:
        """Cast a vote on a proposal.

        Returns None if proposal is not found or not accepting votes.
        Raises an error if the voter has already voted.
        """
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            return None

        if proposal.status != ProposalStatus.PENDING:
            _log.warning(
                "[ConsensusMechanism] proposal %s is not accepting votes (status=%s)",
                proposal_id,
                proposal.status.value,
            )
            return None

        # Check if closed
        if datetime.fromisoformat(proposal.closes_at) < datetime.now(UTC):
            _log.warning("[ConsensusMechanism] proposal %s has closed", proposal_id)
            return None

        vote_id = str(uuid.uuid4())
        now = self._now()

        vote = ConsensusVote(
            id=vote_id,
            proposal_id=proposal_id,
            voter_id=voter_id,
            vote_type=vote_type,
            weight=weight,
            voted_at=now,
            reason=reason,
        )

        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO consensus_votes
                        (id, proposal_id, voter_id, vote_type, weight, voted_at, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        vote.id,
                        vote.proposal_id,
                        vote.voter_id,
                        vote.vote_type.value,
                        vote.weight,
                        vote.voted_at,
                        vote.reason,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                _log.warning(
                    "[ConsensusMechanism] voter %s already voted on proposal %s",
                    voter_id,
                    proposal_id,
                )
                return None

        _log.debug(
            "[ConsensusMechanism] %s voted %s on proposal %s (weight=%.2f)",
            voter_id,
            vote_type.value,
            proposal_id,
            weight,
        )
        return vote

    def get_votes(self, proposal_id: str) -> list[ConsensusVote]:
        """Get all votes for a proposal."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM consensus_votes WHERE proposal_id = ? ORDER BY voted_at ASC",
                (proposal_id,),
            ).fetchall()

        return [self._row_to_vote(r) for r in rows]

    # ------------------------------------------------------------------
    # Public API: Threshold Calculation
    # ------------------------------------------------------------------

    def calculate_threshold(self, total_weight: float, threshold_ratio: float) -> float:
        """Calculate the absolute threshold from a ratio.

        Args:
            total_weight: Sum of all voter weights
            threshold_ratio: Threshold as a ratio (0.0-1.0)

        Returns:
            Absolute threshold value
        """
        return total_weight * threshold_ratio

    def tally_votes(self, proposal_id: str) -> VoteTally:
        """Count votes and determine if proposal passes.

        Checks both quorum (participation) and approval (acceptance) thresholds.
        """
        votes = self.get_votes(proposal_id)
        proposal = self.get_proposal(proposal_id)

        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        total_weight = 0.0
        approve_weight = 0.0
        reject_weight = 0.0
        abstain_weight = 0.0

        for vote in votes:
            total_weight += vote.weight
            if vote.vote_type == VoteType.APPROVE:
                approve_weight += vote.weight
            elif vote.vote_type == VoteType.REJECT:
                reject_weight += vote.weight
            elif vote.vote_type == VoteType.ABSTAIN:
                abstain_weight += vote.weight

        # Calculate thresholds
        quorum_threshold = self.calculate_threshold(total_weight, proposal.quorum_threshold)
        approval_threshold = self.calculate_threshold(total_weight, proposal.approval_threshold)

        # Determine result
        quorum_reached = total_weight >= quorum_threshold
        approval_reached = approve_weight >= approval_threshold

        result = ProposalStatus.PENDING
        if not quorum_reached:
            result = ProposalStatus.EXPIRED
        elif approval_reached:
            result = ProposalStatus.APPROVED
        elif reject_weight > approve_weight:
            result = ProposalStatus.REJECTED

        tally = VoteTally(
            proposal_id=proposal_id,
            total_votes=len(votes),
            total_weight=total_weight,
            approve_weight=approve_weight,
            reject_weight=reject_weight,
            abstain_weight=abstain_weight,
            quorum_reached=quorum_reached,
            approval_reached=approval_reached,
            result=result,
            tallied_at=self._now(),
        )

        _log.debug(
            "[ConsensusMechanism] tallied proposal %s: %d votes, result=%s",
            proposal_id,
            len(votes),
            result.value,
        )
        return tally

    # ------------------------------------------------------------------
    # IConsensusMechanism adapter methods
    # ------------------------------------------------------------------

    _RESULT_MAP: dict[ProposalStatus, DecisionStatus] = {
        ProposalStatus.PENDING: DecisionStatus.PENDING,
        ProposalStatus.APPROVED: DecisionStatus.APPROVED,
        ProposalStatus.REJECTED: DecisionStatus.REJECTED,
        ProposalStatus.EXPIRED: DecisionStatus.REJECTED,
        ProposalStatus.CANCELLED: DecisionStatus.REJECTED,
    }

    def submit_vote(
        self,
        proposal_id: str,
        voter: str,
        vote: bool,
        reason: str = "",
    ) -> None:
        """Record a vote on a proposal.

        Satisfies :meth:`IConsensusMechanism.submit_vote`.
        """
        vote_type = VoteType.APPROVE if vote else VoteType.REJECT
        self.cast_vote(
            proposal_id=proposal_id,
            voter_id=voter,
            vote_type=vote_type,
            reason=reason or None,
        )

    def tally(self, proposal_id: str) -> DecisionResult:
        """Tally votes for a proposal and return the decision.

        Satisfies :meth:`IConsensusMechanism.tally`.
        """
        vt = self.tally_votes(proposal_id)
        return DecisionResult(
            request_id=vt.proposal_id,
            status=self._RESULT_MAP.get(vt.result, DecisionStatus.PENDING),
            reason=f"approve={vt.approve_weight} reject={vt.reject_weight} quorum={vt.quorum_reached}",
            decided_by="consensus",
            metadata=vt.to_dict(),
        )

    def get_quorum_threshold(self) -> float:
        """Return the minimum participation ratio required for quorum.

        Satisfies :meth:`IConsensusMechanism.get_quorum_threshold`.
        """
        return self._DEFAULT_QUORUM
