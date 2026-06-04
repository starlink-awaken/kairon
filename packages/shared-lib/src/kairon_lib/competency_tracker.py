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
# Competency Tracker ≡ Tracker
# 内涵 ≝ {Competency, Tracker}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CompetencyTracker)}
# 功能 ⊢ {Competency_Tracker, Init_Competency, Validate_Tracker}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

"""Competency Tracker — skill-level assessment and gap analysis for agents.

Tracks per-agent competency profiles, finds experts, and identifies skill gaps
relative to required capability sets.

Usage:
    tracker = CompetencyTracker()
    tracker.assess("agent-1", "python", CompetencyLevel.ADVANCED, ["passed-review"])
    experts = tracker.find_experts("python")
"""

import time
from dataclasses import dataclass, field
from enum import IntEnum


class CompetencyLevel(IntEnum):
    """Ordered proficiency scale."""

    NOVICE = 1
    BEGINNER = 2
    INTERMEDIATE = 3
    ADVANCED = 4
    EXPERT = 5


@dataclass
class CompetencyRecord:
    """A single competency assessment for an agent × skill pair."""

    agent_id: str
    skill: str
    level: CompetencyLevel
    evidence: list[str] = field(default_factory=list)
    last_assessed: float = 0.0


class CompetencyTracker:
    """Tracks agent competency profiles and performs gap analysis."""

    def __init__(self) -> None:
        # (agent_id, skill) -> CompetencyRecord
        self._records: dict[tuple[str, str], CompetencyRecord] = {}

    def assess(
        self,
        agent_id: str,
        skill: str,
        level: CompetencyLevel,
        evidence: list[str] | None = None,
    ) -> None:
        """Record or update a competency assessment."""
        key = (agent_id, skill)
        existing = self._records.get(key)
        if existing is not None:
            existing.level = level
            if evidence:
                existing.evidence.extend(evidence)
            existing.last_assessed = time.time()
        else:
            self._records[key] = CompetencyRecord(
                agent_id=agent_id,
                skill=skill,
                level=level,
                evidence=list(evidence or []),
                last_assessed=time.time(),
            )

    def get_competency(self, agent_id: str, skill: str) -> CompetencyRecord | None:
        """Return the competency record for an agent × skill, or None."""
        return self._records.get((agent_id, skill))

    def get_profile(self, agent_id: str) -> list[CompetencyRecord]:
        """Return all competency records for *agent_id*."""
        return [r for r in self._records.values() if r.agent_id == agent_id]

    def find_experts(self, skill: str, min_level: CompetencyLevel = CompetencyLevel.ADVANCED) -> list[str]:
        """Return agent IDs with *skill* at or above *min_level*."""
        return [r.agent_id for r in self._records.values() if r.skill == skill and r.level >= min_level]

    def get_skill_gap(
        self, agent_id: str, required: dict[str, CompetencyLevel]
    ) -> dict[str, tuple[CompetencyLevel | None, CompetencyLevel]]:
        """Identify unmet skills: {skill: (current_or_None, required)}."""
        gaps: dict[str, tuple[CompetencyLevel | None, CompetencyLevel]] = {}
        for skill, req_level in required.items():
            rec = self._records.get((agent_id, skill))
            current = rec.level if rec else None
            if current is None or current < req_level:
                gaps[skill] = (current, req_level)
        return gaps

    def suggest_training(self, agent_id: str) -> list[str]:
        """Return skills where agent is below INTERMEDIATE."""
        return [
            r.skill for r in self._records.values() if r.agent_id == agent_id and r.level < CompetencyLevel.INTERMEDIATE
        ]

    def get_team_coverage(self, skills: list[str]) -> dict[str, dict]:
        """For each skill, report whether any expert exists and who they are."""
        coverage: dict[str, dict] = {}
        for skill in skills:
            experts = self.find_experts(skill)
            coverage[skill] = {
                "covered": len(experts) > 0,
                "experts": experts,
            }
        return coverage
