from __future__ import annotations

import logging

_log = logging.getLogger(__name__)
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
# Approval Escalation Matrix ≡ Module
# 内涵 ≝ {Approval, Escalation, Matrix}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ApprovalEscalationMatrix)}
# 功能 ⊢ {Approval_Escalation, Escalation_Matrix, Matrix_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import threading
from dataclasses import dataclass, field
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class EscalationRule:
    risk_level: RiskLevel
    required_committees: list[str] = field(default_factory=list)
    min_approvers: int = 1
    timeout_seconds: int = 3600
    veto_allowed: bool = False


class EscalationMatrix:
    """Risk-level based approval routing and escalation matrix."""

    def __init__(
        self,
        metadata_path: str = "organs/D_Governance/organs/approval_escalation_matrix.py",
    ) -> None:
        self._lock = threading.RLock()
        self._rules: dict[RiskLevel, EscalationRule] = {}
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        self._rules[RiskLevel.LOW] = EscalationRule(
            risk_level=RiskLevel.LOW,
            required_committees=["team-lead"],
            min_approvers=1,
            timeout_seconds=3600,
            veto_allowed=False,
        )
        self._rules[RiskLevel.MEDIUM] = EscalationRule(
            risk_level=RiskLevel.MEDIUM,
            required_committees=["architecture-committee"],
            min_approvers=2,
            timeout_seconds=7200,
            veto_allowed=False,
        )
        self._rules[RiskLevel.HIGH] = EscalationRule(
            risk_level=RiskLevel.HIGH,
            required_committees=["architecture-committee", "security-committee"],
            min_approvers=3,
            timeout_seconds=14400,
            veto_allowed=True,
        )
        self._rules[RiskLevel.CRITICAL] = EscalationRule(
            risk_level=RiskLevel.CRITICAL,
            required_committees=[
                "architecture-committee",
                "security-committee",
                "board",
            ],
            min_approvers=5,
            timeout_seconds=28800,
            veto_allowed=True,
        )

    def register_rule(self, rule: EscalationRule) -> None:
        """Register or override an escalation rule for a risk level."""
        with self._lock:
            _log.info("Registering escalation rule for %s", rule.risk_level.name)
            self._rules[rule.risk_level] = rule

    def assess_risk(self, action_type: str, context: dict) -> RiskLevel:
        """Classify action risk based on action type and context."""
        action_lower = action_type.lower()

        if "delete" in action_lower or "destroy" in action_lower:
            return RiskLevel.CRITICAL
        if context.get("production") is True:
            return RiskLevel.CRITICAL
        if ("modify" in action_lower or "update" in action_lower) and context.get("scope") == "global":
            return RiskLevel.HIGH
        if "modify" in action_lower or "update" in action_lower:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def get_required_approvals(self, risk_level: RiskLevel) -> EscalationRule:
        """Return the escalation rule for the given risk level."""
        with self._lock:
            if risk_level not in self._rules:
                raise ValueError(f"No escalation rule for risk level {risk_level!r}")
            return self._rules[risk_level]

    def check_approval_complete(self, risk_level: RiskLevel, approvals: list[dict]) -> bool:
        """Check whether approvals satisfy the rule for the given risk level."""
        rule = self.get_required_approvals(risk_level)
        approved = [a for a in approvals if a.get("decision") == "approved"]

        if len(approved) < rule.min_approvers:
            return False

        represented = {a.get("committee") for a in approved}
        return all(c in represented for c in rule.required_committees)

    def is_vetoed(self, risk_level: RiskLevel, decisions: list[dict]) -> bool:
        """Check whether any decision is a veto (only if veto is allowed)."""
        rule = self.get_required_approvals(risk_level)
        if not rule.veto_allowed:
            return False
        return any(d.get("decision") == "veto" for d in decisions)
