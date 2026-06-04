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
# Capability Standardization ≡ Module
# 内涵 ≝ {Capability, Standardization}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CapabilityStandardization)}
# 功能 ⊢ {Capability_Standardization, Init_Capability, Validate_Standardization}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

"""Capability Standardization — interface compliance enforcement.

Defines capability standards (required interface sets) and evaluates whether
entities meet them, producing a compliance matrix across the fleet.

Usage:
    cs = CapabilityStandardization()
    cs.define_standard(CapabilityStandard("mcp-v1", "MCP v1", "Basic MCP",
                                          required_interfaces=["tool_call", "list_tools"]))
    result = cs.check_compliance("agent-1", ["tool_call", "list_tools", "extra"], "mcp-v1")
    assert result.compliant
"""

from dataclasses import dataclass, field


@dataclass
class CapabilityStandard:
    """A named set of required interfaces that entities must implement."""

    standard_id: str
    name: str
    description: str
    required_interfaces: list[str] = field(default_factory=list)
    version: str = "1.0"


@dataclass
class ComplianceResult:
    """Result of checking an entity against a standard."""

    entity_id: str
    standard_id: str
    compliant: bool
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)


class CapabilityStandardization:
    """Defines capability standards and evaluates entity compliance."""

    def __init__(self) -> None:
        self._standards: dict[str, CapabilityStandard] = {}
        # entity_id -> standard_id -> ComplianceResult
        self._results: dict[str, dict[str, ComplianceResult]] = {}

    def define_standard(self, standard: CapabilityStandard) -> None:
        """Register or replace a capability standard."""
        self._standards[standard.standard_id] = standard

    def check_compliance(self, entity_id: str, interfaces: list[str], standard_id: str) -> ComplianceResult:
        """Check *entity_id* against *standard_id* given its *interfaces*."""
        std = self._standards.get(standard_id)
        if std is None:
            raise KeyError(f"Unknown standard: {standard_id}")
        provided = set(interfaces)
        required = set(std.required_interfaces)
        missing = sorted(required - provided)
        extra = sorted(provided - required)
        result = ComplianceResult(
            entity_id=entity_id,
            standard_id=standard_id,
            compliant=len(missing) == 0,
            missing=missing,
            extra=extra,
        )
        self._results.setdefault(entity_id, {})[standard_id] = result
        return result

    def get_standard(self, standard_id: str) -> CapabilityStandard | None:
        """Retrieve a standard by ID."""
        return self._standards.get(standard_id)

    def list_standards(self) -> list[CapabilityStandard]:
        """Return all registered standards."""
        return list(self._standards.values())

    def get_compliant_entities(self, standard_id: str) -> list[str]:
        """Return entity IDs that passed the given standard."""
        return [
            eid for eid, results in self._results.items() if standard_id in results and results[standard_id].compliant
        ]

    def get_non_compliant_entities(self, standard_id: str) -> list[str]:
        """Return entity IDs that failed the given standard."""
        return [
            eid
            for eid, results in self._results.items()
            if standard_id in results and not results[standard_id].compliant
        ]

    def get_compliance_matrix(self) -> dict[str, dict[str, bool]]:
        """Return {entity_id: {standard_id: bool}} for all evaluated pairs."""
        matrix: dict[str, dict[str, bool]] = {}
        for eid, results in self._results.items():
            matrix[eid] = {sid: r.compliant for sid, r in results.items()}
        return matrix
