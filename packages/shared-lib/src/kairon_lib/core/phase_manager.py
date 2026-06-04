from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# Phase Manager ≡ Manager
# 内涵 ≝ {Phase, Manager}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, PhaseManager)}
# 功能 ⊢ {Phase_Manager, Init_Phase, Validate_Manager}
# =============================================================================

"""Phase lifecycle manager — tracks milestones and gates across project phases.

Canonical source for:
  - Nucleus-style: PhaseStatus, Milestone, ProjectPhase, PhaseManager
  - Conductor-style: WorkstreamStatus, WorkstreamSpec, GateCriteria, PhasePlan
conductor/phase_plan.py is a thin re-export facade.
"""

import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class PhaseStatus(StrEnum):
    """Unified phase status — covers both nucleus and conductor usage."""

    DRAFT = "draft"  # conductor: initial draft state
    PENDING = "pending"  # nucleus: not yet started
    ACTIVE = "active"  # both: currently running
    GATE_REVIEW = "gate_review"  # conductor: under gate review
    IN_GATE_REVIEW = "in_gate_review"  # nucleus: under gate review (alias)
    DONE = "done"  # both: completed
    ARCHIVED = "archived"  # both: archived


# ─────────────────────────────────────────────────────────────────
# Conductor-style: WorkstreamStatus
# ─────────────────────────────────────────────────────────────────


class WorkstreamStatus(StrEnum):
    """Conductor-style workstream lifecycle status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass
class Milestone:
    milestone_id: str  # e.g., "M1", "M4"
    title: str
    description: str = ""
    depends_on: list[str] = field(default_factory=list)  # milestone_ids
    acceptance_criteria: list[str] = field(default_factory=list)
    status: str = "pending"
    completed_at: float | None = None

    def complete(self) -> None:
        self.status = "done"
        self.completed_at = time.time()


@dataclass
class ProjectPhase:
    phase_id: str  # e.g., "phase-1", "phase-4"
    name: str
    milestones: list[Milestone] = field(default_factory=list)
    workstream_ids: list[str] = field(default_factory=list)
    status: PhaseStatus = PhaseStatus.PENDING
    test_baseline: int = 0
    test_final: int = 0
    started_at: float | None = None
    completed_at: float | None = None
    commit: str = ""

    def start(self, test_baseline: int = 0) -> None:
        self.status = PhaseStatus.ACTIVE
        self.started_at = time.time()
        self.test_baseline = test_baseline

    def enter_gate_review(self) -> None:
        self.status = PhaseStatus.IN_GATE_REVIEW

    def complete(self, test_final: int = 0, commit: str = "") -> None:
        self.status = PhaseStatus.DONE
        self.completed_at = time.time()
        self.test_final = test_final
        self.commit = commit

    def archive(self) -> None:
        self.status = PhaseStatus.ARCHIVED

    @property
    def tests_added(self) -> int:
        return max(0, self.test_final - self.test_baseline)

    @property
    def duration_s(self) -> float | None:
        if self.started_at and self.completed_at:
            return round(self.completed_at - self.started_at, 2)
        return None


class PhaseManager:
    """Manages the lifecycle of project phases across a full project."""

    def __init__(self, project_name: str) -> None:
        self.project_name = project_name
        self._phases: list[ProjectPhase] = []

    def add_phase(self, phase: ProjectPhase) -> None:
        self._phases.append(phase)

    def get_phase(self, phase_id: str) -> ProjectPhase | None:
        return next((p for p in self._phases if p.phase_id == phase_id), None)

    def get_active_phase(self) -> ProjectPhase | None:
        return next((p for p in self._phases if p.status == PhaseStatus.ACTIVE), None)

    def get_done_phases(self) -> list[ProjectPhase]:
        return [p for p in self._phases if p.status in (PhaseStatus.DONE, PhaseStatus.ARCHIVED)]

    def get_next_phase(self) -> ProjectPhase | None:
        return next((p for p in self._phases if p.status == PhaseStatus.PENDING), None)

    @property
    def total_tests_added(self) -> int:
        return sum(p.tests_added for p in self._phases)

    def build_from_history(self) -> PhaseManager:
        """Pre-populate with the actual B-OS Phase 1-6 history."""
        history = [
            ("phase-1", "Foundation (M1+M2+M3)", 4231),
            ("phase-2", "Federation (M4+M5)", 4332),
            ("phase-3", "Integration (M6+M7+M8)", 4395),
            ("phase-4", "Autonomy (M9+M10+M11)", 4506),
            ("phase-5", "Hardening (M12)", 4619),
            ("phase-6", "Completion (M13)", 4667),
        ]
        prev_count = 0
        for phase_id, name, final_count in history:
            p = ProjectPhase(phase_id=phase_id, name=name)
            p.start(test_baseline=prev_count)
            p.complete(test_final=final_count)
            p.archive()
            self.add_phase(p)
            prev_count = final_count
        return self

    def get_roadmap(self) -> list[dict[str, Any]]:
        return [
            {
                "phase_id": p.phase_id,
                "name": p.name,
                "status": p.status.value,
                "tests_added": p.tests_added,
                "duration_s": p.duration_s,
                "commit": p.commit,
            }
            for p in self._phases
        ]


# ─────────────────────────────────────────────────────────────────
# Conductor-style: GateCriteria
# ─────────────────────────────────────────────────────────────────


@dataclass
class GateCriteria:
    """Quantitative criteria for phase gate review."""

    min_tests_passed: int = 0
    max_tests_failed: int = 0
    ruff_errors: int = 0
    min_test_delta: int = 0  # min new tests this phase
    required_files: list[str] = field(default_factory=list)
    custom_checks: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────
# Conductor-style: WorkstreamSpec (id-based, for PhasePlan)
# ─────────────────────────────────────────────────────────────────


@dataclass
class WorkstreamSpec:
    """Specification for a single workstream (maps to one Agent task)."""

    id: str  # e.g. "WS-A"
    title: str
    description: str
    assignee: str = ""  # role name or agent type
    deliverables: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: WorkstreamStatus = WorkstreamStatus.PENDING
    commit_sha: str = ""
    test_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_markdown_row(self) -> str:
        status_icon = {
            "pending": "⏳",
            "in_progress": "🔄",
            "done": "✅",
            "blocked": "🔴",
            "failed": "❌",
        }
        icon = status_icon.get(self.status.value, "?")
        return f"| {self.id} | {self.title} | {self.assignee} | {icon} {self.status.value} | {self.test_count} |"


# ─────────────────────────────────────────────────────────────────
# Conductor-style: PhasePlan
# ─────────────────────────────────────────────────────────────────


@dataclass
class PhasePlan:
    """A complete phase execution plan — the single source of truth for one cycle."""

    phase_number: int
    title: str
    milestones: list[str]
    purpose: str
    workstreams: list[WorkstreamSpec] = field(default_factory=list)
    gate_criteria: GateCriteria = field(default_factory=GateCriteria)
    status: PhaseStatus = PhaseStatus.DRAFT
    baseline_tests: int = 0
    final_tests: int = 0
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    principles_extracted: list[str] = field(default_factory=list)
    retrospective: str = ""

    def parallel_workstreams(self) -> list[WorkstreamSpec]:
        """Return workstreams with no unfulfilled dependencies."""
        done_ids = {ws.id for ws in self.workstreams if ws.status == WorkstreamStatus.DONE}
        return [
            ws
            for ws in self.workstreams
            if ws.status == WorkstreamStatus.PENDING and all(dep in done_ids for dep in ws.depends_on)
        ]

    def is_gate_ready(self) -> bool:
        return all(ws.status == WorkstreamStatus.DONE for ws in self.workstreams)

    def test_delta(self) -> int:
        return self.final_tests - self.baseline_tests

    def to_markdown(self) -> str:
        lines = [
            f"# Phase {self.phase_number}: {self.title}",
            f"> Milestones: {', '.join(self.milestones)}",
            f"> Status: {self.status.value}",
            f"> Baseline tests: {self.baseline_tests} | Final: {self.final_tests} (+{self.test_delta()})",
            "",
            "## Workstreams",
            "| ID | Title | Assignee | Status | Tests |",
            "|----|-------|----------|--------|-------|",
        ]
        for ws in self.workstreams:
            lines.append(ws.to_markdown_row())
        lines += [
            "",
            "## Gate Criteria",
            f"- Min tests passed: {self.gate_criteria.min_tests_passed}",
            f"- Max ruff errors: {self.gate_criteria.ruff_errors}",
            f"- Min test delta: {self.gate_criteria.min_test_delta}",
            "",
        ]
        if self.retrospective:
            lines += ["## Retrospective", self.retrospective, ""]
        if self.principles_extracted:
            lines += [
                "## Principles Extracted",
                *[f"- {p}" for p in self.principles_extracted],
            ]
        return "\n".join(lines)

    def save(self, base_dir: str | Path = "docs/exec-plans/active") -> Path:
        path = Path(base_dir) / f"Phase-{self.phase_number}-{self.title.replace(' ', '-')}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path


# ─────────────────────────────────────────────────────────────────
# __all__
# ─────────────────────────────────────────────────────────────────

__all__ = [
    # Shared
    "PhaseStatus",
    # Nucleus-style
    "Milestone",
    "ProjectPhase",
    "PhaseManager",
    # Conductor-style
    "WorkstreamStatus",
    "WorkstreamSpec",
    "GateCriteria",
    "PhasePlan",
]
