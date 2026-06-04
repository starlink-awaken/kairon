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
# Policy Registry ≡ Module
# 内涵 ≝ {Policy, Registry}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, PolicyRegistry)}
# 功能 ⊢ {Policy_Registry, Init_Policy, Validate_Registry}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---
"""Runtime policy management for D-Governance.

Registers, evaluates, and enforces governance policies at runtime.
Supports versioning, suspension, retirement, and rule-based access control.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Policy:
    policy_id: str
    name: str
    description: str
    rules: list[dict]
    version: str = "1.0.0"
    status: str = "active"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass
class PolicyEvalResult:
    allowed: bool
    policy_id: str
    reason: str
    conditions: list[str] = field(default_factory=list)


_RISK_LEVEL_POLICY_MAP: dict[str, tuple[str, list[dict[str, Any]]]] = {
    "low": ("risk-low-policy", []),
    "medium": ("risk-medium-policy", [{"type": "require_context", "key": "evaluation_id"}]),
    "high": ("risk-high-policy", [{"type": "require_context", "key": "approval_token"}]),
    "critical": (
        "risk-critical-policy",
        [
            {"type": "require_context", "key": "approval_token"},
            {"type": "require_context", "key": "break_glass_reason"},
        ],
    ),
}


def _bump_minor(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3:
        return "1.1.0"
    major, minor, patch = parts
    return f"{major}.{int(minor) + 1}.{patch}"


class PolicyRegistry:
    """Thread-safe registry for governance policies.

    Implements :class:`IPolicyEngine` from Z-Core/L2-Law.
    """

    def __init__(
        self,
        metadata_path: str = "organs/D_Governance/organs/policy_registry.py",
    ) -> None:
        self._policies: dict[str, Policy] = {}
        self._history: dict[str, list[dict]] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register_policy(  # type: ignore[override]
        self,
        policy_or_id: Policy | str,
        rules: dict[str, Any] | None = None,
    ) -> bool:
        """Register a policy.

        Accepts either a :class:`Policy` object (original API) or a
        ``(policy_id, rules)`` pair as required by :class:`IPolicyEngine`.
        Returns ``True`` on success.
        """
        if isinstance(policy_or_id, str):
            policy = Policy(
                policy_id=policy_or_id,
                name=policy_or_id,
                description="",
                rules=[rules] if isinstance(rules, dict) else (rules or []),
            )
        else:
            policy = policy_or_id

        with self._lock:
            now = _now_iso()
            if policy.policy_id in self._policies:
                old = self._policies[policy.policy_id]
                policy.version = _bump_minor(old.version)
                policy.updated_at = now
                self._history.setdefault(policy.policy_id, []).append(
                    {"version": policy.version, "action": "updated", "timestamp": now},
                )
            else:
                policy.updated_at = now
                self._history.setdefault(policy.policy_id, []).append(
                    {"version": policy.version, "action": "registered", "timestamp": now},
                )
            self._policies[policy.policy_id] = policy
        return True

    def get_policy(self, policy_id: str) -> Policy | None:
        with self._lock:
            return self._policies.get(policy_id)

    def list_active_policies(self) -> list[Policy]:
        with self._lock:
            return [p for p in self._policies.values() if p.status == "active"]

    def suspend_policy(self, policy_id: str) -> bool:
        with self._lock:
            policy = self._policies.get(policy_id)
            if policy is None or policy.status in ("suspended", "retired"):
                return False
            policy.status = "suspended"
            policy.updated_at = _now_iso()
            self._history.setdefault(policy_id, []).append(
                {"version": policy.version, "action": "suspended", "timestamp": policy.updated_at},
            )
            return True

    def retire_policy(self, policy_id: str) -> bool:
        with self._lock:
            policy = self._policies.get(policy_id)
            if policy is None or policy.status == "retired":
                return False
            policy.status = "retired"
            policy.updated_at = _now_iso()
            self._history.setdefault(policy_id, []).append(
                {"version": policy.version, "action": "retired", "timestamp": policy.updated_at},
            )
            return True

    # ------------------------------------------------------------------
    # Evaluation & enforcement
    # ------------------------------------------------------------------

    def can_execute(
        self,
        policy_id: str,
        actor: str,
        action: str,
        context: dict | None = None,
    ) -> PolicyEvalResult:
        context = context or {}
        with self._lock:
            policy = self._policies.get(policy_id)

        if policy is None:
            return PolicyEvalResult(
                allowed=False,
                policy_id=policy_id,
                reason="policy not found",
            )
        if policy.status != "active":
            return PolicyEvalResult(
                allowed=False,
                policy_id=policy_id,
                reason=f"policy is {policy.status}",
            )

        conditions: list[str] = []
        for rule in policy.rules:
            rtype = rule.get("type", "")
            if rtype == "deny_actor" and rule.get("actor") == actor:
                return PolicyEvalResult(
                    allowed=False,
                    policy_id=policy_id,
                    reason=f"actor '{actor}' denied by rule",
                )
            if rtype == "require_context":
                key = rule.get("key", "")
                if key and key not in context:
                    return PolicyEvalResult(
                        allowed=False,
                        policy_id=policy_id,
                        reason=f"missing required context key '{key}'",
                        conditions=[f"requires context key '{key}'"],
                    )
                if key:
                    conditions.append(f"context key '{key}' present")

        return PolicyEvalResult(
            allowed=True,
            policy_id=policy_id,
            reason="allowed",
            conditions=conditions,
        )

    def enforce(
        self,
        policy_id: str,
        actor: str,
        action: str,
        context: dict | None = None,
    ) -> PolicyEvalResult:
        result = self.can_execute(policy_id, actor, action, context)
        logger.info(
            "enforce policy=%s actor=%s action=%s allowed=%s reason=%s",
            policy_id,
            actor,
            action,
            result.allowed,
            result.reason,
        )
        return result

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_policy_history(self, policy_id: str) -> list[dict]:
        with self._lock:
            return list(self._history.get(policy_id, []))

    # ------------------------------------------------------------------
    # IPolicyEngine adapter methods
    # ------------------------------------------------------------------

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate *context* against all active policies.

        Returns ``True`` only if every active policy allows the context.
        Satisfies :meth:`IPolicyEngine.evaluate`.
        """
        policy_id = context.get("policy_id", "")
        actor = context.get("actor", "")
        action = context.get("action", "")
        if policy_id:
            return self.can_execute(policy_id, actor, action, context).allowed
        for p in self.list_active_policies():
            if not self.can_execute(p.policy_id, actor, action, context).allowed:
                return False
        return True

    def list_policies(self) -> list[str]:
        """Return IDs of all registered policies.

        Satisfies :meth:`IPolicyEngine.list_policies`.
        """
        with self._lock:
            return list(self._policies.keys())

    # ------------------------------------------------------------------
    # Phase5 governance templates
    # ------------------------------------------------------------------

    def register_risk_level_templates(self) -> dict[str, str]:
        """Ensure built-in risk-level policies exist and return their mapping."""
        mapping: dict[str, str] = {}
        for risk_level, (policy_id, rules) in _RISK_LEVEL_POLICY_MAP.items():
            policy = Policy(
                policy_id=policy_id,
                name=f"Risk policy ({risk_level})",
                description=f"Auto-generated policy template for risk level '{risk_level}'.",
                rules=list(rules),
            )
            self.register_policy(policy)
            mapping[risk_level] = policy_id
        return mapping

    def resolve_risk_policy(self, risk_level: str) -> str:
        """Resolve a policy id for the provided risk level."""
        normalized = risk_level.strip().lower()
        if normalized not in _RISK_LEVEL_POLICY_MAP:
            normalized = "critical"
        return _RISK_LEVEL_POLICY_MAP[normalized][0]

    def enforce_risk_level(
        self,
        risk_level: str,
        actor: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> PolicyEvalResult:
        """Enforce policy template derived from risk level."""
        self.register_risk_level_templates()
        policy_id = self.resolve_risk_policy(risk_level)
        return self.enforce(policy_id, actor=actor, action=action, context=context)
