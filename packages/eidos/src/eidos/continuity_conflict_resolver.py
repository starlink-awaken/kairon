from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Devil'
Authority: organs/D-Continuity/AGENTS.md
Layer: L3
Constraint: '[!!] DETERMINISTIC_CONFLICT_RESOLUTION'
Summary: 'Deterministic conflict resolution engine — rule-based fallback for @Devil review when LLM is unavailable.'
Tags:
- conflict-resolution
- deterministic
- devil-review
- fallback
---
"""


import ast
import logging
import math
import time
from typing import Any, Protocol

_log = logging.getLogger(__name__)

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# DeterministicConflictResolver ≡ Module
# 内涵 ≝ {Deterministic, Conflict, Resolution, Scoring}
# 外延 ≝ {e | e ∈ D-Continuity ∧ implements(e, DeterministicConflictResolver)}
# 功能 ⊢ {Role_Authority, Code_Quality, File_Criticality, Composite_Score,
#          Deterministic_Review, Resolve_Conflict, Review_With_Fallback}
# =============================================================================

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Role authority weights — higher = more authority for review decisions.
ROLE_AUTHORITY: dict[str, float] = {
    "@Devil": 5.0,  # QA / security — highest for review decisions
    "@Board": 4.5,  # Governance
    "@Sage": 4.0,  # Architecture / wisdom
    "@Keeper": 3.0,  # Memory / persistence guardian
    "@Builder": 2.0,  # Implementation
}

_DEFAULT_ROLE_AUTHORITY = 1.0

#: Composite score weights (must sum to 1.0).
W_ROLE = 0.40
W_QUALITY = 0.25
W_CRITICALITY = 0.20
W_RECENCY = 0.15

#: Recency decay half-life in seconds (1 hour).
_RECENCY_HALF_LIFE = 3600.0

#: Escalation threshold — if top-two scores are within this ratio, escalate.
_ESCALATION_THRESHOLD_NORMAL = 0.10  # 10 % relative gap
_ESCALATION_THRESHOLD_CRITICAL = 0.20  # 20 % for nucleus / rules files


class _LLMProvider(Protocol):
    def generate(self, prompt: str) -> None: ...


class DeterministicConflictResolver:
    """Rule-based conflict resolution engine.

    Provides deterministic conflict resolution when the LLM is unavailable,
    using priority scoring across four dimensions:

    1. **Role authority** — persona archetype weight
    2. **Code quality** — heuristic AST analysis (docstrings, annotations, error handling)
    3. **File criticality** — path-based classification (nucleus > rules > organs > tests)
    4. **Recency** — exponential-decay bonus for more recent changes

    The engine also provides a ``review_with_fallback`` method that attempts
    an LLM review first and gracefully degrades to deterministic rules.
    """

    # ------------------------------------------------------------------
    # 1. Individual scoring dimensions
    # ------------------------------------------------------------------

    @staticmethod
    def role_authority_score(role: str) -> float:
        """Return the authority weight for a given persona role.

        Args:
            role: Persona name, e.g. ``"@Devil"``.

        Returns:
            Authority weight (>= 1.0).
        """
        return ROLE_AUTHORITY.get(role, _DEFAULT_ROLE_AUTHORITY)

    @staticmethod
    def code_quality_score(code: str) -> float:
        """Heuristic quality score for Python source code.

        Scores are computed from static analysis of the AST:
        * +2.0 per function/class/async-function definition
        * +3.0 per docstring
        * +1.5 per type annotation (arg or return)
        * +2.0 per try/except block (error handling)

        Non-parseable input returns 0.0.
        """
        if not code or not code.strip():
            return 0.0

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return 0.0

        score = 0.0
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                score += 2.0
                if ast.get_docstring(node):
                    score += 3.0
                # Count type annotations on arguments
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for arg in node.args.args:
                        if arg.annotation is not None:
                            score += 1.5
                    if node.returns is not None:
                        score += 1.5
            elif isinstance(node, ast.Try):
                score += 2.0
        return score

    @staticmethod
    def file_criticality_score(file_path: str) -> float:
        """Classify file criticality based on its path.

        Returns a score in [1.0, 5.0]:
        * 5.0 — nucleus core (L0 Genome, Z-Spore DNA)
        * 4.0 — nucleus (other)
        * 3.0 — organ rules / authority files
        * 2.0 — organ implementation code
        * 1.0 — tests, docs, configs
        """
        p = file_path.replace("-", "_").lower()

        if "nucleus/" in p or "nucleus\\" in p:
            if "l0_genome" in p or "z_spore/dna" in p or "z_core/l0" in p:
                return 5.0
            return 4.0
        if "organs/" in p and "/rules/" in p:
            return 3.0
        if "organs/" in p:
            return 2.0
        # tests, docs, configs, scripts, etc.
        return 1.0

    @staticmethod
    def recency_score(timestamp: float, *, reference: float | None = None) -> float:
        """Exponential-decay recency bonus in [0, 1].

        More recent timestamps score closer to 1.0.

        Args:
            timestamp: Unix epoch of the change.
            reference: Reference "now" timestamp (default: ``time.time()``).
        """
        ref = reference if reference is not None else time.time()
        age = max(ref - timestamp, 0.0)
        # Exponential decay with half-life
        return math.exp(-0.693 * age / _RECENCY_HALF_LIFE)

    # ------------------------------------------------------------------
    # 2. Composite score
    # ------------------------------------------------------------------

    def composite_score(
        self,
        role: str,
        code_content: str,
        file_path: str,
        timestamp: float,
    ) -> float:
        """Weighted composite score across all dimensions.

        The weights are defined by module-level constants ``W_ROLE``,
        ``W_QUALITY``, ``W_CRITICALITY``, ``W_RECENCY``.
        """
        return (
            W_ROLE * self.role_authority_score(role)
            + W_QUALITY * self.code_quality_score(code_content)
            + W_CRITICALITY * self.file_criticality_score(file_path)
            + W_RECENCY * self.recency_score(timestamp)
        )

    # ------------------------------------------------------------------
    # 3. Deterministic review (replaces LLM @Devil review)
    # ------------------------------------------------------------------

    @staticmethod
    def deterministic_review(
        vision_id: str,
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Perform a deterministic @Devil review of a vision's task list.

        Checks:
        * Task completion ratio
        * Presence of test / review tasks
        * Missing critical task types

        Returns:
            Dict with ``assessment``, ``score`` (0.0–1.0), and ``issues``.
        """
        issues: list[str] = []

        if not tasks:
            return {
                "assessment": (f"[@Devil-Deterministic] Vision {vision_id}: No tasks found — unable to assess."),
                "score": 0.0,
                "issues": ["No tasks associated with this vision."],
            }

        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("status") == "COMPLETED")
        completion_ratio = completed / total

        # Flag incomplete tasks
        for t in tasks:
            if t.get("status") != "COMPLETED":
                issues.append(
                    f"Task '{t.get('summary', t.get('id', '?'))}' is incomplete (status: {t.get('status', 'UNKNOWN')})."
                )

        # Check for test coverage tasks
        has_test_task = any("test" in t.get("summary", "").lower() for t in tasks)
        if not has_test_task:
            issues.append("No test-related task found — testing gap risk.")
            completion_ratio *= 0.9  # penalize slightly

        # Check for review tasks
        has_review = any(
            "review" in t.get("summary", "").lower() or "polish" in t.get("summary", "").lower() for t in tasks
        )
        if not has_review:
            issues.append("No review/polish task found.")
            completion_ratio *= 0.95

        score = min(completion_ratio, 1.0)

        if score >= 0.9 and not issues:
            assessment = (
                f"[@Devil-Deterministic] Vision {vision_id}: All {total} tasks completed. Implementation looks aligned."
            )
        elif score >= 0.7:
            assessment = (
                f"[@Devil-Deterministic] Vision {vision_id}: "
                f"{completed}/{total} tasks completed (score {score:.0%}). "
                f"Minor gaps detected."
            )
        else:
            assessment = (
                f"[@Devil-Deterministic] Vision {vision_id}: "
                f"{completed}/{total} tasks completed (score {score:.0%}). "
                f"Significant issues require attention."
            )

        return {
            "assessment": assessment,
            "score": score,
            "issues": issues,
        }

    # ------------------------------------------------------------------
    # 4. LLM → deterministic fallback chain
    # ------------------------------------------------------------------

    def review_with_fallback(
        self,
        vision_id: str,
        tasks: list[dict[str, Any]],
        llm_provider: _LLMProvider | None = None,
    ) -> dict[str, Any]:
        """Attempt LLM-based review, fall back to deterministic rules.

        Args:
            vision_id: Vision identifier.
            tasks: List of task dicts (``id``, ``summary``, ``status``).
            llm_provider: Optional LLM provider with a ``.generate()`` method.

        Returns:
            Dict with ``method`` (``"llm"`` or ``"deterministic"``),
            ``assessment``, ``score``, and ``issues``.
        """
        if llm_provider is not None:
            try:
                prompt = (
                    f"[PERSONA: @Devil - The Critic]\n"
                    f"Analyze the implementation of Vision {vision_id}.\n"
                    f"Tasks completed: {[t.get('summary', '?') for t in tasks]}\n"
                    f"Provide a ruthlessly honest 1-sentence assessment."
                )
                response = llm_provider.generate(prompt)
                assessment_text = getattr(response, "text", str(response))
                _log.info("😈 [@Devil LLM Assessment]: %s", assessment_text)
                return {
                    "method": "llm",
                    "assessment": assessment_text,
                    "score": 1.0,  # LLM doesn't produce a numeric score
                    "issues": [],
                }
            except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
                _log.warning("⚠️ [@Devil] LLM review failed, falling back to deterministic rules.")

        # Deterministic fallback
        result = self.deterministic_review(vision_id, tasks)
        result["method"] = "deterministic"
        _log.info(
            "😈 [@Devil-Deterministic Assessment]: %s (score=%.2f)",
            result["assessment"],
            result["score"],
        )
        return result

    # ------------------------------------------------------------------
    # 5. Multi-agent conflict resolution
    # ------------------------------------------------------------------

    def resolve_conflict(
        self,
        file_path: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Resolve a multi-agent conflict using composite scoring.

        Each candidate dict should contain:
        * ``agent_id`` — unique identifier
        * ``role`` — persona (e.g. ``"@Builder"``)
        * ``content`` — source code
        * ``timestamp`` — unix epoch

        When the top-two scores are within the escalation threshold the
        resolver returns ``strategy="ESCALATE"`` instead of choosing a winner.
        The threshold is tighter for critical files (nucleus, rules).

        Returns:
            Dict with ``winner``, ``strategy``, ``scores``.
        """
        if not candidates:
            return {
                "winner": None,
                "strategy": "ESCALATE",
                "scores": {},
                "reason": "No candidates provided.",
            }

        scores: dict[str, float] = {}
        for c in candidates:
            scores[c["agent_id"]] = self.composite_score(
                role=c.get("role", ""),
                code_content=c.get("content", ""),
                file_path=file_path,
                timestamp=c.get("timestamp", time.time()),
            )

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

        # Single candidate — auto-accept
        if len(ranked) == 1:
            return {
                "winner": ranked[0][0],
                "strategy": "ACCEPT_HIGHEST",
                "scores": scores,
                "reason": "Single candidate — auto-accepted.",
            }

        top_score = ranked[0][1]
        runner_up = ranked[1][1]

        # Determine escalation threshold based on file criticality
        criticality = self.file_criticality_score(file_path)
        if criticality >= 4.0:
            threshold = _ESCALATION_THRESHOLD_CRITICAL
        else:
            threshold = _ESCALATION_THRESHOLD_NORMAL

        # Check relative gap
        gap = (top_score - runner_up) / max(top_score, 1e-9)
        if gap < threshold:
            return {
                "winner": None,
                "strategy": "ESCALATE",
                "scores": scores,
                "reason": (
                    f"Score gap ({gap:.1%}) below threshold ({threshold:.0%}) "
                    f"for file criticality {criticality:.0f}. Manual review required."
                ),
            }

        return {
            "winner": ranked[0][0],
            "strategy": "ACCEPT_HIGHEST",
            "scores": scores,
            "reason": (f"Clear winner with {gap:.1%} score gap (threshold {threshold:.0%})."),
        }
