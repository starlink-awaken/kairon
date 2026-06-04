"""Role SLO Registry — service-level objective tracking per role.

Extracted from SharedBrain D_Governance (organs/role/role_slo_registry.py).
Zero external dependencies — pure dataclasses and in-memory registry.

Provides:
- RoleSLO: a service-level objective bound to a role (target metric + window)
- RoleSLOViolation: a recorded SLO violation event
- RoleSLORegistry: in-memory registry for registering SLOs, recording metrics,
  checking compliance, and surfacing at-risk roles.

Usage:
    registry = RoleSLORegistry()
    registry.register_slo(RoleSLO("reviewer", "review_latency_s", target=300.0))
    registry.record_metric("reviewer", "review_latency_s", 250.0)
    compliance = registry.check_compliance("reviewer")
"""

import time
from dataclasses import dataclass


@dataclass
class RoleSLO:
    """A service-level objective bound to a role."""

    role_id: str
    metric: str
    target: float
    window_seconds: int = 3600
    description: str = ""


@dataclass
class RoleSLOViolation:
    """A recorded SLO violation event."""

    role_id: str
    metric: str
    actual: float
    target: float
    timestamp: float


class RoleSLORegistry:
    """Registry and evaluator for per-role SLOs."""

    def __init__(self) -> None:
        # (role_id, metric) -> RoleSLO
        self._slos: dict[tuple[str, str], RoleSLO] = {}
        # (role_id, metric) -> list[(timestamp, value)]
        self._samples: dict[tuple[str, str], list[tuple[float, float]]] = {}
        self._violations: list[RoleSLOViolation] = []

    def register_slo(self, slo: RoleSLO) -> None:
        """Define or replace an SLO."""
        self._slos[(slo.role_id, slo.metric)] = slo

    def record_metric(self, role_id: str, metric: str, value: float) -> None:
        """Record a metric sample and check for violations."""
        now = time.time()
        key = (role_id, metric)
        self._samples.setdefault(key, []).append((now, value))
        slo = self._slos.get(key)
        if slo is not None and value > slo.target:
            self._violations.append(
                RoleSLOViolation(
                    role_id=role_id,
                    metric=metric,
                    actual=value,
                    target=slo.target,
                    timestamp=now,
                )
            )

    def _window_samples(self, role_id: str, metric: str) -> list[tuple[float, float]]:
        key = (role_id, metric)
        slo = self._slos.get(key)
        if slo is None:
            return []
        cutoff = time.time() - slo.window_seconds
        return [(ts, v) for ts, v in self._samples.get(key, []) if ts >= cutoff]

    def check_compliance(self, role_id: str) -> dict[str, dict]:
        """Check compliance for each metric of *role_id*."""
        result: dict[str, dict] = {}
        for (rid, metric), slo in self._slos.items():
            if rid != role_id:
                continue
            samples = self._window_samples(role_id, metric)
            if not samples:
                result[metric] = {"compliant": True, "samples": 0, "violations": 0}
                continue
            violations = sum(1 for _, v in samples if v > slo.target)
            result[metric] = {
                "compliant": violations == 0,
                "samples": len(samples),
                "violations": violations,
            }
        return result

    def get_violations(self, role_id: str | None = None) -> list[RoleSLOViolation]:
        """Return recorded violations, optionally filtered by role."""
        if role_id is None:
            return list(self._violations)
        return [v for v in self._violations if v.role_id == role_id]

    def get_compliance_rate(self, role_id: str) -> float:
        """Return fraction of SLOs currently met for *role_id* (0.0–1.0)."""
        compliance = self.check_compliance(role_id)
        if not compliance:
            return 1.0
        met = sum(1 for c in compliance.values() if c["compliant"])
        return met / len(compliance)

    def list_slos(self, role_id: str | None = None) -> list[RoleSLO]:
        """Return registered SLOs, optionally filtered by role."""
        if role_id is None:
            return list(self._slos.values())
        return [s for s in self._slos.values() if s.role_id == role_id]

    def get_at_risk_roles(self) -> list[str]:
        """Return role IDs with compliance rate below 90%."""
        role_ids = {rid for rid, _ in self._slos}
        return [rid for rid in role_ids if self.get_compliance_rate(rid) < 0.9]


__all__ = [
    "RoleSLO",
    "RoleSLORegistry",
    "RoleSLOViolation",
]
