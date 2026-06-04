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
# Risk Classifier ≡ Module
# 内涵 ≝ {Risk, Classifier}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, RiskClassifier)}
# 功能 ⊢ {Risk_Classifier, Init_Risk, Validate_Classifier}
# =============================================================================

"""Risk classification engine for D-Governance.

---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Authority: EC-7/PB-3
Keywords: [risk, classification, scoring, governance, security]
---

Automatically classifies the risk level of an action based on resource type,
operation type, data sensitivity, scope, and reversibility. Used by
ApprovalQueue and GovernanceEngine to determine whether human review is
required before execution.

Usage::

    classifier = RiskClassifier()
    result = classifier.classify(
        action={"type": "delete_data", "target": "users", "resource": "database"},
        context={"user_role": "admin", "data_sensitivity": "high"}
    )
    print(result.level)  # RiskLevel.CRITICAL
"""

import logging
from dataclasses import dataclass
from typing import Any

from kairon_lib.governance.approval_queue import RiskLevel  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk factor definitions
# ---------------------------------------------------------------------------

# Weight assigned to each risk dimension (must sum to 1.0)
_FACTOR_WEIGHTS: dict[str, float] = {
    "resource_type": 0.20,
    "operation_type": 0.30,
    "data_sensitivity": 0.25,
    "scope": 0.15,
    "reversibility": 0.10,
}

# Scores for resource types
_RESOURCE_SCORES: dict[str, float] = {
    "kernel": 1.0,
    "memory": 0.8,
    "filesystem": 0.7,
    "network": 0.7,
    "database": 0.8,
    "config": 0.6,
    "code": 0.5,
    "user": 0.9,
    "financial": 1.0,
    "api": 0.4,
    "default": 0.5,
}

# Scores for operation types
_OPERATION_SCORES: dict[str, float] = {
    "delete": 1.0,
    "write": 0.7,
    "execute": 0.9,
    "read": 0.2,
    "update": 0.5,
    "create": 0.4,
    "grant": 0.8,
    "revoke": 0.8,
    "transmit": 0.6,
    "deploy": 0.8,
    "default": 0.4,
}

# Scores for data sensitivity
_SENSITIVITY_SCORES: dict[str, float] = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.5,
    "low": 0.2,
    "public": 0.0,
    "default": 0.4,
}

# Scores for scope (number of affected entities)
_SCOPE_SCORES: dict[str, float] = {
    "global": 1.0,
    "system": 0.9,
    "multiple_users": 0.7,
    "single_user": 0.4,
    "self_only": 0.1,
    "default": 0.4,
}

# Scores for reversibility
_REVERSIBILITY_SCORES: dict[str, float] = {
    "irreversible": 1.0,
    "difficult": 0.7,
    "moderate": 0.4,
    "easy": 0.1,
    "instant": 0.0,
    "default": 0.4,
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RiskFactor:
    """A single risk factor contributing to the overall score.

    Attributes
    ----------
    factor_name:
        Name of the factor (e.g. "resource_type", "operation_type").
    weight:
        Relative weight of this factor (0.0–1.0).
    score:
        Raw risk score for this factor (0.0–1.0).
    """

    factor_name: str
    weight: float
    score: float

    @property
    def weighted_score(self) -> float:
        """Return the contribution of this factor to the total score."""
        return self.weight * self.score


@dataclass
class ClassificationResult:
    """Result of a risk classification.

    Attributes
    ----------
    level:
        The classified risk level.
    score:
        The raw risk score (0.0–1.0).
    factors:
        List of individual risk factors evaluated.
    reasoning:
        Human-readable explanation of the classification.
    """

    level: RiskLevel
    score: float
    factors: list[RiskFactor]
    reasoning: str


# ---------------------------------------------------------------------------
# RiskClassifier
# ---------------------------------------------------------------------------


class RiskClassifier:
    """Automatic risk classifier for governance operations.

    Evaluates five risk dimensions and returns a RiskLevel (LOW / MEDIUM /
    HIGH / CRITICAL) with full provenance (factor scores and reasoning).

    BOS-URI endpoints
    -----------------
    ``bos://governance/risk/classify``  — classify an action
    ``bos://governance/risk/score``      — return raw risk score only
    """

    def __init__(
        self,
        metadata_path: str = "organs/D-Governance/organs/risk_classifier.py",
    ) -> None:
        self.status = "active"
        self.status = "ACTIVE"
        _log.info("RiskClassifier initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(
        self,
        action: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        """Classify the risk level of an action.

        Parameters
        ----------
        action:
            Action descriptor. Expected keys::

                - type (str): operation type (e.g. "delete", "write", "execute")
                - target (str): target entity name (optional)
                - resource (str): resource category (optional)

        context:
            Additional context. Expected keys::

                - data_sensitivity (str): critical / high / medium / low / public
                - scope (str): global / system / multiple_users / single_user / self_only
                - reversibility (str): irreversible / difficult / moderate / easy / instant
                - user_role (str): role of the requesting user

        Returns
        -------
        ClassificationResult
            The classification including level, raw score, factor breakdown,
            and a human-readable reasoning string.
        """
        if context is None:
            context = {}

        score = self._calculate_score(action, context)
        level = self._determine_level(score)
        factors = self._build_factors(action, context)
        reasoning = self._build_reasoning(action, context, level, score)

        _log.info(
            "[RiskClassifier] classified action=%s level=%s score=%.3f",
            action.get("type", "unknown"),
            level.value,
            score,
        )

        return ClassificationResult(
            level=level,
            score=round(score, 4),
            factors=factors,
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    # Internal scoring
    # ------------------------------------------------------------------

    def _calculate_score(
        self,
        action: dict[str, Any],
        context: dict[str, Any],
    ) -> float:
        """Compute the weighted risk score (0.0–1.0)."""
        weights = _FACTOR_WEIGHTS

        resource_score = self._score_resource(action)
        op_score = self._score_operation(action)
        sensitivity_score = self._score_sensitivity(context)
        scope_score = self._score_scope(context)
        reversibility_score = self._score_reversibility(context)

        weighted = (
            weights["resource_type"] * resource_score
            + weights["operation_type"] * op_score
            + weights["data_sensitivity"] * sensitivity_score
            + weights["scope"] * scope_score
            + weights["reversibility"] * reversibility_score
        )

        return max(0.0, min(1.0, weighted))

    def _determine_level(self, score: float) -> RiskLevel:
        """Map a raw score to a RiskLevel."""
        if score >= 0.75:
            return RiskLevel.CRITICAL
        if score >= 0.50:
            return RiskLevel.HIGH
        if score >= 0.25:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _build_factors(
        self,
        action: dict[str, Any],
        context: dict[str, Any],
    ) -> list[RiskFactor]:
        """Return all five RiskFactor instances for the given inputs."""
        return [
            RiskFactor(
                factor_name="resource_type",
                weight=_FACTOR_WEIGHTS["resource_type"],
                score=self._score_resource(action),
            ),
            RiskFactor(
                factor_name="operation_type",
                weight=_FACTOR_WEIGHTS["operation_type"],
                score=self._score_operation(action),
            ),
            RiskFactor(
                factor_name="data_sensitivity",
                weight=_FACTOR_WEIGHTS["data_sensitivity"],
                score=self._score_sensitivity(context),
            ),
            RiskFactor(
                factor_name="scope",
                weight=_FACTOR_WEIGHTS["scope"],
                score=self._score_scope(context),
            ),
            RiskFactor(
                factor_name="reversibility",
                weight=_FACTOR_WEIGHTS["reversibility"],
                score=self._score_reversibility(context),
            ),
        ]

    def _build_reasoning(
        self,
        action: dict[str, Any],
        context: dict[str, Any],
        level: RiskLevel,
        score: float,
    ) -> str:
        """Generate a human-readable reasoning string."""
        op_type = action.get("type", "unknown")
        resource = action.get("resource", "default")
        sensitivity = context.get("data_sensitivity", "medium")
        scope = context.get("scope", "self_only")
        reversibility = context.get("reversibility", "moderate")

        return (
            f"Action '{op_type}' on resource '{resource}' with "
            f"sensitivity={sensitivity}, scope={scope}, reversibility={reversibility} "
            f"yields raw_score={score:.3f} -> {level.value.upper()}. "
            f"Highest-weighted dimension: operation_type (weight=0.30)."
        )

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------

    def _score_resource(self, action: dict[str, Any]) -> float:
        """Score the resource type dimension."""
        resource = str(action.get("resource", "")).lower()
        return _RESOURCE_SCORES.get(resource, _RESOURCE_SCORES["default"])

    def _score_operation(self, action: dict[str, Any]) -> float:
        """Score the operation type dimension."""
        op_type = str(action.get("type", "")).lower()
        return _OPERATION_SCORES.get(op_type, _OPERATION_SCORES["default"])

    def _score_sensitivity(self, context: dict[str, Any]) -> float:
        """Score the data sensitivity dimension."""
        sensitivity = str(context.get("data_sensitivity", "medium")).lower()
        return _SENSITIVITY_SCORES.get(sensitivity, _SENSITIVITY_SCORES["default"])

    def _score_scope(self, context: dict[str, Any]) -> float:
        """Score the scope dimension."""
        scope = str(context.get("scope", "self_only")).lower()
        return _SCOPE_SCORES.get(scope, _SCOPE_SCORES["default"])

    def _score_reversibility(self, context: dict[str, Any]) -> float:
        """Score the reversibility dimension."""
        reversibility = str(context.get("reversibility", "moderate")).lower()
        return _REVERSIBILITY_SCORES.get(reversibility, _REVERSIBILITY_SCORES["default"])
