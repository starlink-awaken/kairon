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
# Reasoning Chain Auditor ≡ Auditor
# 内涵 ≝ {Reasoning, Chain, Auditor}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ReasoningChainAuditor)}
# 功能 ⊢ {Reasoning_Chain, Chain_Auditor, Auditor_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class AuditEntry:
    chain_id: str
    auditor: str
    verdict: str
    issues: list[str] = field(default_factory=list)
    timestamp: float = 0.0


class ReasoningChainAuditor:
    """Audits reasoning chains for logical consistency and quality."""

    def __init__(self, auditor_name: str = "system") -> None:
        self._auditor = auditor_name
        self._history: dict[str, list[AuditEntry]] = defaultdict(list)
        self._total_audits: int = 0
        self._pass_count: int = 0

    def audit_chain(self, chain_id: str, steps: list[dict], conclusion: str) -> AuditEntry:
        issues: list[str] = []
        issues.extend(self.check_logical_consistency(steps))
        issues.extend(self.check_confidence_degradation(steps))
        if self.check_circular_reasoning(steps):
            issues.append("Circular reasoning detected")
        if not steps:
            issues.append("Empty reasoning chain")
        if not conclusion:
            issues.append("Missing conclusion")

        verdict = "pass" if not issues else "fail"
        entry = AuditEntry(
            chain_id=chain_id,
            auditor=self._auditor,
            verdict=verdict,
            issues=issues,
            timestamp=time.time(),
        )
        self._history[chain_id].append(entry)
        self._total_audits += 1
        if verdict == "pass":
            self._pass_count += 1
        return entry

    def check_logical_consistency(self, steps: list[dict]) -> list[str]:
        issues: list[str] = []
        seen_outputs: set[str] = set()
        for i, step in enumerate(steps):
            step_type = step.get("type", "")
            output = str(step.get("output_data", ""))
            if not step_type:
                issues.append(f"Step {i} has no type")
            if output in seen_outputs and output:
                issues.append(f"Step {i} duplicates a previous output")
            if output:
                seen_outputs.add(output)
        return issues

    def check_confidence_degradation(self, steps: list[dict]) -> list[str]:
        issues: list[str] = []
        prev_conf: float | None = None
        drops = 0
        for i, step in enumerate(steps):
            conf = step.get("confidence", 0.0)
            if prev_conf is not None and conf < prev_conf - 0.3:
                drops += 1
                issues.append(f"Step {i}: confidence dropped sharply ({prev_conf:.2f} -> {conf:.2f})")
            prev_conf = conf
        return issues

    def check_circular_reasoning(self, steps: list[dict]) -> bool:
        seen_inputs: list[str] = []
        for step in steps:
            inp = str(step.get("input_data", ""))
            out = str(step.get("output_data", ""))
            if out and out in seen_inputs:
                return True
            if inp:
                seen_inputs.append(inp)
        return False

    def get_audit_history(self, chain_id: str) -> list[AuditEntry]:
        return list(self._history.get(chain_id, []))

    def get_stats(self) -> dict:
        return {
            "total_audits": self._total_audits,
            "passed": self._pass_count,
            "failed": self._total_audits - self._pass_count,
            "pass_rate": (self._pass_count / self._total_audits if self._total_audits > 0 else 0.0),
        }
