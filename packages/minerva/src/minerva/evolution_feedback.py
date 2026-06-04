"""Evolution Feedback — recording experiences and deriving insights.

Derived from D_Genesis/organs/evolution_feedback_bridge.py (triaged extraction).

Archived D_Genesis capabilities (not extracted — documented here for traceability):
  - FactGraph sync pipeline (EvolutionFeedbackBridge sync_to_fact_graph /
    _do_sync_to_fact_graph with RDF triples) — too coupled to D_Memory's
    FactGraph; minerva uses its own knowledge_store.py for persistence.
  - EvolutionResult → EvolutionFeedback conversion
    (convert_result with type inference from content heuristics) — left in
    D_Genesis as the evolution loop driver is not ported.
  - Genetic algorithm engine (mutation_proposal_engine, gene_stitcher,
    phenotype_engine, archetype_extractor) — over-engineered; archived.
  - Federated evolution (community_dna_contribution, spore_distiller) —
    cross-instance sharing not in scope for minerva.
  - Prototype management (assembler, archetype_store) — deferred.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Experience:
    """A recorded experience entry."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    pattern: str = ""
    outcome: str = ""
    score: float = 0.0
    timestamp: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)


class EvolutionFeedback:
    """Records experiences and derives insights over time.

    This is a lightweight evolution feedback loop that replaces the
    heavier D_Genesis EvolutionFeedbackBridge. Instead of syncing to
    FactGraph triples, it maintains an in-memory experience log and
    computes simple statistical insights.

    Usage:
        ef = EvolutionFeedback()
        ef.record_experience("use batch processing", "reduced latency by 40%", score=0.85)
        insights = ef.get_insights(n=5)
        for i in insights:
            print(i)
    """

    def __init__(self, max_experiences: int = 1000) -> None:
        self._experiences: list[Experience] = []
        self._max_experiences = max_experiences
        self._lock = threading.Lock()

        # Statistics
        self._record_count: int = 0
        self._pruned_count: int = 0

    # ── Public API ──────────────────────────────────────────────────────

    def record_experience(
        self,
        pattern: str,
        outcome: str,
        score: float = 0.0,
        tags: list[str] | None = None,
    ) -> str:
        """Record an experience entry.

        Parameters
        ----------
        pattern: What was done or observed (e.g., "use batch processing").
        outcome: What resulted (e.g., "reduced latency by 40%").
        score: Quality/fitness score [0.0, 1.0].
        tags: Optional categorization tags.

        Returns
        -------
        The experience id.
        """
        exp = Experience(
            pattern=pattern,
            outcome=outcome,
            score=max(0.0, min(1.0, score)),
            tags=list(tags or []),
        )

        with self._lock:
            self._experiences.append(exp)
            self._record_count += 1

            # Prune oldest if over capacity
            if len(self._experiences) > self._max_experiences:
                overflow = len(self._experiences) - self._max_experiences
                self._experiences = self._experiences[overflow:]
                self._pruned_count += overflow
                logger.debug(
                    "[EvolutionFeedback] Pruned %d oldest experiences (total=%d, cap=%d)",
                    overflow,
                    self._record_count,
                    self._max_experiences,
                )

        logger.debug("[EvolutionFeedback] Recorded experience %s", exp.id)
        return exp.id

    def get_insights(self, n: int = 5, min_score: float = 0.5) -> list[str]:
        """Derive insights from recorded experiences.

        Returns the top-N patterns ranked by score, formatted as insight strings.
        Low-scoring experiences are filtered out.

        Parameters
        ----------
        n: Maximum number of insights to return.
        min_score: Minimum score threshold for inclusion.

        Returns
        -------
        List of insight strings, ordered by score descending.
        """
        with self._lock:
            if not self._experiences:
                return ["No experiences recorded yet."]

            # Filter and sort by score descending
            candidates = [e for e in self._experiences if e.score >= min_score]
            candidates.sort(key=lambda e: e.score, reverse=True)

            if not candidates:
                return [f"No insights meet the minimum score threshold ({min_score})."]

            insights: list[str] = []
            for exp in candidates[:n]:
                insight = (
                    f"[score={exp.score:.2f}] When {exp.pattern}, "
                    f"the outcome was: {exp.outcome}"
                )
                if exp.tags:
                    insight += f" (tags: {', '.join(exp.tags)})"
                insights.append(insight)

            return insights

    # ── Statistics ──────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return feedback statistics."""
        with self._lock:
            total = len(self._experiences)
            if total == 0:
                avg_score = 0.0
                high_score_count = 0
            else:
                scores = [e.score for e in self._experiences]
                avg_score = sum(scores) / total
                high_score_count = sum(1 for s in scores if s >= 0.8)

        return {
            "total_experiences": self._record_count,
            "in_memory": total,
            "pruned": self._pruned_count,
            "avg_score": round(avg_score, 4),
            "high_score_count": high_score_count,
        }

    def clear(self) -> int:
        """Clear all experiences. Returns number of cleared entries."""
        with self._lock:
            count = len(self._experiences)
            self._experiences.clear()
            return count
