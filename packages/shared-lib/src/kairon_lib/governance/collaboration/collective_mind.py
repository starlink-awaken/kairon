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
# Collective Mind ≡ Module
# 内涵 ≝ {Collective, Mind}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CollectiveMind)}
# 功能 ⊢ {Collective_Mind, Init_Collective, Validate_Mind}
# =============================================================================

"""
---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Authority: EC-7/PB-3
Keywords: [collective, deliberation, federated, emergent, intelligence, multi-twin]
BOS-URI: [bos://hive/deliberate, bos://hive/federate, bos://hive/insights]
---

# P8.3 Collective Mind
## multi_twin_deliberation — MultiTwinDeliberation
## federated_learning — FederatedLearning
## emergent_intelligence — EmergentIntelligence

Collective Intelligence (集智) framework for B-OS:
- Multi-twin deliberation with configurable consensus algorithms
- Privacy-preserving federated learning with differential privacy
- Emergent intelligence detection and collective wisdom evaluation
"""


import logging
import math
import random
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

_log = logging.getLogger(__name__)


# =============================================================================
# Consensus & Voting Enums
# =============================================================================


class ConsensusMode(StrEnum):
    """Consensus algorithm variants."""

    UNANIMOUS = "unanimous"  # All must agree
    MAJORITY = "majority"  # >50% yes
    SUPERMAJORITY = "supermajority"  # >66% yes
    WEIGHTED = "weighted"  # Weight-based aggregation


class VoteType(StrEnum):
    """Vote direction."""

    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"


class SessionStatus(StrEnum):
    """Deliberation session lifecycle."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    FAILED = "failed"


# =============================================================================
# P8.3.1 — MultiTwinDeliberation
# =============================================================================


@dataclass
class Proposal:
    proposal_id: str
    twin_id: str
    content: str
    submitted_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class Vote:
    twin_id: str
    proposal_id: str
    vote_type: VoteType
    weight: float = 1.0
    voted_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DeliberationSession:
    session_id: str
    topic: str
    participants: list[str]
    proposals: list[Proposal] = field(default_factory=list)
    votes: list[Vote] = field(default_factory=list)
    status: SessionStatus = SessionStatus.ACTIVE
    consensus_mode: ConsensusMode = ConsensusMode.MAJORITY
    anonymous: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DeliberationOutcome:
    outcome_id: str
    session_id: str
    decision: str
    consensus_level: float
    minority_position: str = ""


class MultiTwinDeliberation:
    """
    Multi-twin deliberation network.

    Supports named and anonymous voting across multiple consensus modes.
    BOS-URI: bos://hive/deliberate
    """

    def __init__(self, metadata_path: str = "organs/D-Governance/organs/collective_mind.py") -> None:
        super().__init__(metadata_path=metadata_path)
        self._lock = threading.RLock()
        self._sessions: dict[str, DeliberationSession] = {}
        _log.info("[Deliberation] MultiTwinDeliberation initialised")

    # ── Session lifecycle ─────────────────────────────────────────────────────

    def create_session(
        self,
        topic: str,
        participant_twin_ids: list[str],
        consensus_mode: ConsensusMode = ConsensusMode.MAJORITY,
        anonymous: bool = False,
    ) -> DeliberationSession:
        """Create a new deliberation session."""
        session = DeliberationSession(
            session_id=str(uuid.uuid4()),
            topic=topic,
            participants=list(participant_twin_ids),
            consensus_mode=consensus_mode,
            anonymous=anonymous,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        _log.info("[Deliberation] Created session %s — topic: %s", session.session_id, topic)
        return session

    def get_session(self, session_id: str) -> DeliberationSession | None:
        """Return a session by id, or None."""
        with self._lock:
            return self._sessions.get(session_id)

    def get_active_sessions(self) -> list[DeliberationSession]:
        """Return all active (non-resolved) sessions."""
        with self._lock:
            return [s for s in self._sessions.values() if s.status == SessionStatus.ACTIVE]

    # ── Proposal & voting ─────────────────────────────────────────────────────

    def submit_proposal(self, session_id: str, twin_id: str, content: str) -> bool:
        """Submit a proposal to a session. Returns False unless the twin is a participant."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or session.status != SessionStatus.ACTIVE:
                return False
            if twin_id not in session.participants:
                return False
            proposal = Proposal(
                proposal_id=str(uuid.uuid4()),
                twin_id=twin_id,
                content=content,
            )
            session.proposals.append(proposal)
            return True

    def vote(
        self,
        session_id: str,
        twin_id: str,
        proposal_id: str,
        vote_type: VoteType,
        weight: float = 1.0,
    ) -> bool:
        """Record a vote. Returns False if the session, participant, or proposal is invalid."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or session.status != SessionStatus.ACTIVE:
                return False
            if twin_id not in session.participants:
                return False
            if proposal_id not in {proposal.proposal_id for proposal in session.proposals}:
                return False
            vote = Vote(
                twin_id=twin_id,
                proposal_id=proposal_id,
                vote_type=vote_type,
                weight=weight,
            )
            session.votes.append(vote)
            return True

    # ── Resolution ─────────────────────────────────────────────────────────────

    def resolve_session(self, session_id: str) -> DeliberationOutcome | None:
        """
        Resolve a session using the configured consensus mode.

        UNANIMOUS  — all non-abstain votes must be YES
        MAJORITY   — YES votes > 50% of eligible participants
        SUPERMAJORITY — YES votes > 66%
        WEIGHTED   — sum(weight*YES) > 50% of total weight
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None

            session.status = SessionStatus.RESOLVED

            yes_votes = [v for v in session.votes if v.vote_type == VoteType.YES]
            no_votes = [v for v in session.votes if v.vote_type == VoteType.NO]
            abstain = [v for v in session.votes if v.vote_type == VoteType.ABSTAIN]

            yes_w = sum(v.weight for v in yes_votes)
            no_w = sum(v.weight for v in no_votes)
            total_w = yes_w + no_w + sum(v.weight for v in abstain) or 1.0

            if session.consensus_mode == ConsensusMode.UNANIMOUS:
                passed = len(no_votes) == 0 and len(yes_votes) > 0
                consensus = yes_w / total_w

            elif session.consensus_mode == ConsensusMode.MAJORITY:
                eligible_participants = len(session.participants) or 1
                consensus = len(yes_votes) / eligible_participants
                passed = consensus > 0.5

            elif session.consensus_mode == ConsensusMode.SUPERMAJORITY:
                eligible_participants = len(session.participants) or 1
                consensus = len(yes_votes) / eligible_participants
                passed = consensus > 2 / 3

            else:  # WEIGHTED
                consensus = yes_w / total_w
                passed = consensus > 0.5

            decision = "Passed" if passed else "Rejected"
            minority = ""
            if not passed and no_votes:
                # Map proposal_id → content via proposals list
                pid_to_content = {p.proposal_id: p.content for p in session.proposals}
                minority = "; ".join(f"{v.twin_id}: {pid_to_content.get(v.proposal_id, '')}" for v in no_votes[:3])

            outcome = DeliberationOutcome(
                outcome_id=str(uuid.uuid4()),
                session_id=session_id,
                decision=decision,
                consensus_level=round(consensus, 4),
                minority_position=minority,
            )
            _log.info(
                "[Deliberation] Resolved %s — %s (consensus=%.2f)",
                session_id,
                decision,
                consensus,
            )
            return outcome


# =============================================================================
# P8.3.2 — FederatedLearning
# =============================================================================


@dataclass
class FederatedRound:
    round_id: str
    participants: list[str]
    gradients: dict[str, list[float]] = field(default_factory=dict)
    aggregated_at: str | None = None
    loss: float = 0.0


class FederatedLearning:
    """
    Federated learning with FedAvg aggregation and Gaussian-noise differential privacy.

    BOS-URI: bos://hive/federate
    """

    NOISE_FACTOR: float = 0.1  # Gaussian noise std scale
    GRADIENT_DIM: int = 10  # Simulated gradient vector length

    def __init__(self, metadata_path: str = "organs/D-Governance/organs/collective_mind.py") -> None:
        super().__init__(metadata_path=metadata_path)
        self._lock = threading.RLock()
        self._rounds: dict[str, FederatedRound] = {}
        _log.info("[Federated] FederatedLearning initialised")

    @classmethod
    def _validate_gradient_dimension(
        cls,
        gradient: list[float],
        *,
        label: str = "Gradient",
    ) -> None:
        actual_dim = len(gradient)
        if actual_dim != cls.GRADIENT_DIM:
            raise ValueError(f"{label} dimension {actual_dim} does not match expected {cls.GRADIENT_DIM}")

    # ── Round lifecycle ────────────────────────────────────────────────────────

    def init_round(self, participant_twin_ids: list[str]) -> FederatedRound:
        """Open a new federated round."""
        rnd = FederatedRound(
            round_id=str(uuid.uuid4()),
            participants=list(participant_twin_ids),
        )
        with self._lock:
            self._rounds[rnd.round_id] = rnd
        _log.info(
            "[Federated] Init round %s with %d participants",
            rnd.round_id,
            len(participant_twin_ids),
        )
        return rnd

    def get_round_status(self, round_id: str) -> dict[str, Any]:
        """Return round status snapshot."""
        with self._lock:
            rnd = self._rounds.get(round_id)
            if not rnd:
                return {}
            return {
                "round_id": round_id,
                "participants": len(rnd.participants),
                "gradients_received": len(rnd.gradients),
                "aggregated": rnd.aggregated_at is not None,
                "loss": rnd.loss,
            }

    # ── Gradient submission ───────────────────────────────────────────────────

    def submit_gradient(self, round_id: str, twin_id: str, gradient: list[float] | None = None) -> bool:
        """
        Submit a (noisy) gradient for a round.

        If gradient is None, a simulated gradient is used.
        Gaussian noise is added for differential privacy.
        """
        with self._lock:
            rnd = self._rounds.get(round_id)
            if not rnd or twin_id not in rnd.participants:
                return False

            grad = gradient
            if grad is None:
                # Simulated gradient — uniform [-0.1, 0.1]
                grad = [random.uniform(-0.1, 0.1) for _ in range(self.GRADIENT_DIM)]  # noqa: S311
            else:
                self._validate_gradient_dimension(grad)

            # Apply Gaussian noise for differential privacy
            rng = random.Random(hash(twin_id) % (2**32))  # noqa: S311
            noisy = [g + rng.gauss(0.0, self.NOISE_FACTOR) for g in grad]
            rnd.gradients[twin_id] = noisy
            return True

    # ── Aggregation (FedAvg) ──────────────────────────────────────────────────

    def aggregate_gradients(self, round_id: str) -> dict[str, Any]:
        """
        FedAvg aggregation — element-wise mean of received gradients.

        Returns {"aggregated": [...], "num_participants": N}.
        """
        with self._lock:
            rnd = self._rounds.get(round_id)
            if not rnd or not rnd.gradients:
                return {}

            grads = list(rnd.gradients.values())
            n = len(grads)
            dim = len(grads[0])
            for gradient in grads:
                self._validate_gradient_dimension(gradient)
            result = [sum(g[i] for g in grads) / n for i in range(dim)]

            rnd.aggregated_at = datetime.now(UTC).isoformat()

            _log.info(
                "[Federated] Aggregated round %s — %d participants, dim=%d",
                round_id,
                n,
                dim,
            )
            return {"aggregated": result, "num_participants": n}

    def apply_aggregation(self, round_id: str, global_model: list[float]) -> dict[str, Any]:
        """
        Apply aggregated gradient update to global model (FedAvg step).

        Returns updated model weights.
        """
        agg = self.aggregate_gradients(round_id)
        if not agg:
            return {"weights": global_model, "applied": False}

        delta = agg["aggregated"]
        if len(global_model) != len(delta):
            raise ValueError(
                f"Global model dimension {len(global_model)} does not match aggregated gradient dimension {len(delta)}"
            )
        updated = [w + d for w, d in zip(global_model, delta, strict=True)]

        # Update stored round loss (simulated)
        with self._lock:
            rnd = self._rounds.get(round_id)
            if rnd:
                rnd.loss = random.uniform(0.01, 0.5)  # noqa: S311

        _log.info("[Federated] Applied FedAvg update to round %s", round_id)
        return {"weights": updated, "applied": True, "loss": rnd.loss if rnd else 0.0}


# =============================================================================
# P8.3.3 — EmergentIntelligence
# =============================================================================


@dataclass
class EmergentInsight:
    insight_id: str
    description: str
    supporting_evidence: list[str]
    confidence: float
    emerged_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class EmergentIntelligence:
    """
    Detects emergent insights from pattern clusters, evaluates collective wisdom,
    and generates recommendations.

    BOS-URI: bos://hive/insights
    """

    INSIGHT_THRESHOLD: float = 0.7

    def __init__(self, metadata_path: str = "organs/D-Governance/organs/collective_mind.py") -> None:
        super().__init__(metadata_path=metadata_path)
        self._lock = threading.RLock()
        self._insights: list[EmergentInsight] = []
        _log.info("[Emergent] EmergentIntelligence initialised")

    # ── Insight detection ─────────────────────────────────────────────────────

    def detect_insights(self, pattern_cluster: list[dict]) -> list[EmergentInsight]:
        """
        Detect emergent insights from a cluster of patterns.

        A pattern dict should contain: name, confidence (0-1), evidence (list[str]).
        Only patterns exceeding INSIGHT_THRESHOLD are promoted to insights.
        """
        emerging: list[EmergentInsight] = []
        with self._lock:
            for pattern in pattern_cluster:
                confidence = float(pattern.get("confidence", 0.0))
                if confidence >= self.INSIGHT_THRESHOLD:
                    insight = EmergentInsight(
                        insight_id=str(uuid.uuid4()),
                        description=f"Emerging pattern: {pattern.get('name', 'unknown')}",
                        supporting_evidence=list(pattern.get("evidence", [])),
                        confidence=confidence,
                    )
                    self._insights.append(insight)
                    emerging.append(insight)
                    _log.info(
                        "[Emergent] Insight detected: %s (conf=%.2f)",
                        insight.description,
                        confidence,
                    )
        return emerging

    def get_all_insights(self) -> list[EmergentInsight]:
        """Return all stored insights."""
        with self._lock:
            return list(self._insights)

    # ── Collective wisdom ─────────────────────────────────────────────────────

    def evaluate_collective_wisdom(self, deliberation_id: str) -> float:
        """
        Evaluate collective intelligence score for a deliberation.

        Uses a confidence-weighted average of participating twin contributions.
        Returns a score in [0, 1].
        """
        with self._lock:
            return self._compute_collective_intelligence(
                {deliberation_id: 0.75}  # Placeholder: per-deliberation scores
            )

    @staticmethod
    def _compute_collective_intelligence(scores: dict[str, float]) -> float:
        """
        Compute overall collective intelligence from individual twin scores.

        Uses the mean-of-means heuristic from Wisdom of Crowds theory.
        """
        if not scores:
            return 0.0
        values = list(scores.values())
        mean = sum(values) / len(values)
        # Discount for variance (diverse reliable inputs > homogeneous ones)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        diversity_bonus = min(math.sqrt(variance), 0.1)
        return min(max(mean + diversity_bonus, 0.0), 1.0)

    # ── Recommendation generation ─────────────────────────────────────────────

    def generate_recommendation(self, insights: list[EmergentInsight]) -> str:
        """
        Generate a natural-language recommendation from a set of insights.

        Selects the highest-confidence insight as primary and synthesises
        a recommendation string.
        """
        if not insights:
            return "Insufficient evidence for recommendation. Await more data."

        top = max(insights, key=lambda i: i.confidence)
        supporting = [i.description for i in insights if i.confidence >= self.INSIGHT_THRESHOLD]

        recommendation = (
            f"Recommended action based on {len(supporting)} high-confidence insights. "
            f"Primary signal: {top.description} "
            f"(confidence={top.confidence:.0%}). "
            f"Supporting evidence: {'; '.join(supporting[:3])}"
        )
        _log.info("[Emergent] Recommendation generated — top conf=%.2f", top.confidence)
        return recommendation
