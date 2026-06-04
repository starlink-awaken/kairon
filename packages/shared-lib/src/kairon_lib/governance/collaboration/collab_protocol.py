from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Collab Protocol ≡ Module
# 内涵 ≝ {Collab, Protocol}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CollabProtocol)}
# 功能 ⊢ {Collab_Protocol, Init_Collab, Validate_Protocol}
# =============================================================================


"""Collaboration protocol standards — canonical source (nucleus/governance).

conductor/collaboration_protocol.py is a thin re-export facade.

Two complementary protocol families are unified:
  - Conductor-style protocols: PhaseGateReview, PhaseRetrospective, PhaseHandoffProtocol,
    WorkstreamHandshakeProtocol, PrincipleExtractionProtocol (rich lifecycle classes)
  - Nucleus-style protocols: GateReviewProtocol, RetrospectiveProtocol (dict-based),
    ADRRecord, CollabArtifact, CollabProtocolRegistry

The conductor facade re-exports PhaseGateReview as GateReviewProtocol and
PhaseRetrospective as RetrospectiveProtocol for backward compatibility.
"""

# =============================================================================
# 0. 形式化摘要
# =============================================================================
# 内涵 ≝ {PhaseGateReview, PhaseRetrospective, PhaseHandoffProtocol,
#          WorkstreamHandshakeProtocol, PrincipleExtractionProtocol,
#          GateReviewProtocol, RetrospectiveProtocol, ADRRecord,
#          CollabArtifact, CollabProtocolRegistry}
# =============================================================================

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────


class ProtocolStatus(StrEnum):
    """Conductor-style protocol lifecycle status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"


class ProtocolType(StrEnum):
    """Nucleus-style protocol type classification."""

    RFC = "rfc"
    ADR = "adr"
    SPRINT_REVIEW = "sprint_review"
    GATE_REVIEW = "gate_review"
    RETROSPECTIVE = "retrospective"
    STANDUP = "standup"
    INCIDENT = "incident"
    OKR = "okr"


# ─────────────────────────────────────────────────────────────────
# Conductor-style: ChecklistItem (for PhaseGateReview)
# ─────────────────────────────────────────────────────────────────


@dataclass
class ChecklistItem:
    description: str
    required: bool = True
    passed: bool | None = None
    notes: str = ""

    def check(self, result: bool, notes: str = "") -> None:
        self.passed = result
        self.notes = notes

    def status_icon(self) -> str:
        if self.passed is None:
            return "⬜"
        return "✅" if self.passed else ("❌" if self.required else "⚠️")


# ─────────────────────────────────────────────────────────────────
# Conductor-style: PhaseHandoffProtocol
# ─────────────────────────────────────────────────────────────────


@dataclass
class PhaseHandoffProtocol:
    """Formalized state package passed from one phase to the next."""

    from_phase: int
    to_phase: int
    handoff_items: list[str] = field(default_factory=list)
    open_risks: list[str] = field(default_factory=list)
    test_baseline: int = 0
    commit_sha: str = ""
    accepted: bool = False
    accepted_by: str = ""
    timestamp: float = field(default_factory=time.time)

    def accept(self, role: str) -> None:
        self.accepted = True
        self.accepted_by = role
        self.timestamp = time.time()

    def to_markdown(self) -> str:
        status = "✅ ACCEPTED" if self.accepted else "⏳ PENDING"
        lines = [
            f"# Phase {self.from_phase} → Phase {self.to_phase} Handoff {status}",
            f"Commit: `{self.commit_sha or 'pending'}`",
            f"Test baseline: {self.test_baseline}",
            "",
            "## Confirmed Deliverables",
            *[f"- ✅ {item}" for item in self.handoff_items],
            "",
            "## Open Risks for Next Phase",
            *[f"- ⚠️ {risk}" for risk in self.open_risks],
        ]
        if self.accepted:
            lines += ["", f"**Accepted by:** {self.accepted_by}"]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Conductor-style: PhaseGateReview (exported as GateReviewProtocol
#                                    in conductor facade)
# ─────────────────────────────────────────────────────────────────


@dataclass
class PhaseGateReview:
    """Checklist-based phase gate review (conductor-style).

    The conductor facade re-exports this as ``GateReviewProtocol``.
    """

    phase_number: int
    checklist: list[ChecklistItem] = field(default_factory=list)
    status: ProtocolStatus = ProtocolStatus.PENDING
    reviewer: str = ""
    reviewed_at: float | None = None

    @classmethod
    def standard(cls, phase_number: int) -> PhaseGateReview:
        return cls(
            phase_number=phase_number,
            checklist=[
                ChecklistItem("All workstreams status = DONE", required=True),
                ChecklistItem("Test suite: 0 failures", required=True),
                ChecklistItem("Ruff: 0 errors", required=True),
                ChecklistItem("New tests added (delta > 0)", required=True),
                ChecklistItem("Deliverable files created/modified", required=True),
                ChecklistItem("No secrets committed", required=True),
                ChecklistItem("Retrospective written", required=False),
                ChecklistItem("Principles extracted to AGENTS.md", required=False),
            ],
        )

    def run_checks(self, results: dict[str, bool]) -> None:
        for item in self.checklist:
            key = item.description
            if key in results:
                item.check(results[key])

    def is_passing(self) -> bool:
        return all(item.passed is True for item in self.checklist if item.required and item.passed is not None)

    def unchecked_required(self) -> list[ChecklistItem]:
        return [i for i in self.checklist if i.required and i.passed is None]

    def to_markdown(self) -> str:
        lines = [f"# Gate Review — Phase {self.phase_number}", ""]
        for item in self.checklist:
            req_label = "[required]" if item.required else "[optional]"
            lines.append(f"{item.status_icon()} {req_label} {item.description}")
            if item.notes:
                lines.append(f"   → {item.notes}")
        lines += [
            "",
            f"**Status:** {'✅ PASSED' if self.is_passing() else '❌ NOT PASSED'}",
        ]
        if self.reviewer:
            lines.append(f"**Reviewer:** {self.reviewer}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Conductor-style: PhaseRetrospective (exported as RetrospectiveProtocol
#                                       in conductor facade)
# ─────────────────────────────────────────────────────────────────


@dataclass
class PhaseRetrospective:
    """Structured 4-section retrospective (conductor-style).

    The conductor facade re-exports this as ``RetrospectiveProtocol``.
    """

    phase_number: int
    went_well: list[str] = field(default_factory=list)
    went_poorly: list[str] = field(default_factory=list)
    surprising: list[str] = field(default_factory=list)
    principles: list[str] = field(default_factory=list)
    facilitator: str = ""
    timestamp: float = field(default_factory=time.time)

    def is_complete(self) -> bool:
        return bool(self.went_well and self.went_poorly and self.principles)

    def to_markdown(self) -> str:
        lines = [
            f"# Phase {self.phase_number} Retrospective",
            f"_Facilitated by: {self.facilitator or 'unknown'}_",
            "",
            "## ✅ What Went Well",
            *[f"- {item}" for item in self.went_well],
            "",
            "## ❌ What Went Poorly",
            *[f"- {item}" for item in self.went_poorly],
            "",
            "## 🤔 What Was Surprising",
            *[f"- {item}" for item in self.surprising],
            "",
            "## 📖 Principles Extracted",
            *[f"- {p}" for p in self.principles],
        ]
        return "\n".join(lines)

    def save(self, base_dir: str | Path = "docs/exec-plans/retros") -> Path:
        path = Path(base_dir) / f"Phase-{self.phase_number}-retro.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path


# ─────────────────────────────────────────────────────────────────
# Conductor-style: WorkstreamHandshakeProtocol
# ─────────────────────────────────────────────────────────────────


@dataclass
class WorkstreamHandshakeProtocol:
    """Agent ↔ coordinator contract for workstream execution."""

    ws_id: str
    title: str
    assignee: str
    deliverables: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    sla_seconds: int = 3600
    started_at: float | None = None
    completed_at: float | None = None
    result_sha: str = ""

    def start(self) -> None:
        self.started_at = time.time()

    def complete(self, result_sha: str = "") -> None:
        self.completed_at = time.time()
        self.result_sha = result_sha

    def elapsed_s(self) -> float | None:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def within_sla(self) -> bool:
        e = self.elapsed_s()
        return e is not None and e <= self.sla_seconds

    def to_brief(self) -> str:
        elapsed = self.elapsed_s()
        e_str = f"{elapsed:.0f}s" if elapsed else "running"
        return f"[{self.ws_id}] {self.title} → {self.assignee} ({e_str})"


# ─────────────────────────────────────────────────────────────────
# Conductor-style: PrincipleExtractionProtocol
# ─────────────────────────────────────────────────────────────────


@dataclass
class PrincipleExtractionProtocol:
    """Pipeline: retrospective principles → AGENTS.md update."""

    source_retro: PhaseRetrospective
    target_file: str = "AGENTS.md"
    section_header: str = "## Extracted Principles"
    principles_added: list[str] = field(default_factory=list)
    applied: bool = False

    def apply(self, base_dir: str | Path = ".") -> Path:
        """Append new principles to the target file (idempotent)."""
        path = Path(base_dir) / self.target_file
        if not path.exists():
            path.write_text(
                f"# Agent Guidelines\n\n{self.section_header}\n",
                encoding="utf-8",
            )

        content = path.read_text(encoding="utf-8")
        new_principles = [p for p in self.source_retro.principles if p not in content]

        if not new_principles:
            self.applied = True
            return path

        addition = f"\n### Phase {self.source_retro.phase_number} Principles\n"
        addition += "\n".join(f"- {p}" for p in new_principles) + "\n"

        if self.section_header in content:
            content = content.replace(self.section_header, self.section_header + addition)
        else:
            content += f"\n{self.section_header}{addition}"

        path.write_text(content, encoding="utf-8")
        self.principles_added = new_principles
        self.applied = True
        return path


# ─────────────────────────────────────────────────────────────────
# Nucleus-style: CollabArtifact
# ─────────────────────────────────────────────────────────────────


@dataclass
class CollabArtifact:
    """A formal collaboration artifact (RFC, ADR, retro doc, etc.)."""

    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    protocol_type: ProtocolType = ProtocolType.RFC
    title: str = ""
    author: str = ""
    status: str = "draft"
    created_at: float = field(default_factory=time.time)
    content: dict[str, object] = field(default_factory=dict)

    def accept(self) -> None:
        self.status = "accepted"

    def reject(self, reason: str = "") -> None:
        self.status = "rejected"
        if reason:
            self.content["rejection_reason"] = reason


# ─────────────────────────────────────────────────────────────────
# Nucleus-style: GateReviewProtocol (dict-based)
# ─────────────────────────────────────────────────────────────────


@dataclass
class GateReviewProtocol:
    """Standardized Gate Review checklist (nucleus-style, dict-based).

    For the conductor-style checklist version see ``PhaseGateReview``.
    """

    phase_name: str
    test_count: int = 0
    test_baseline: int = 0
    ruff_errors: int = 0
    new_commits: list[str] = field(default_factory=list)
    checklist: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    reviewer: str = "@Guardian"
    reviewed_at: float = field(default_factory=time.time)

    def _default_checklist(self) -> dict[str, bool]:
        return {
            "tests_increase": self.test_count > self.test_baseline,
            "ruff_clean": self.ruff_errors == 0,
            "no_new_failures": True,
            "commits_present": len(self.new_commits) > 0,
            "docs_updated": False,
        }

    def evaluate(self) -> bool:
        if not self.checklist:
            self.checklist = self._default_checklist()
        return all(self.checklist.values())

    @property
    def tests_delta(self) -> int:
        return self.test_count - self.test_baseline

    def format_report(self) -> str:
        passed = self.evaluate()
        status = "✅ GATE PASSED" if passed else "❌ GATE FAILED"
        lines = [
            f"=== Gate Review: {self.phase_name} ===",
            f"Status: {status}",
            f"Tests: {self.test_baseline} → {self.test_count} (+{self.tests_delta})",
            f"Ruff errors: {self.ruff_errors}",
            "",
            "Checklist:",
        ]
        for item, ok in self.checklist.items():
            icon = "✅" if ok else "❌"
            lines.append(f"  {icon} {item}")
        if self.notes:
            lines.append("\nNotes:")
            for note in self.notes:
                lines.append(f"  - {note}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Nucleus-style: RetrospectiveProtocol (field-based)
# ─────────────────────────────────────────────────────────────────


@dataclass
class RetrospectiveProtocol:
    """Standardized Retrospective (nucleus-style, field-based).

    For the conductor-style went_well/went_poorly version see ``PhaseRetrospective``.
    """

    phase_name: str
    author: str = "@Forge"
    what_went_well: list[str] = field(default_factory=list)
    what_to_improve: list[str] = field(default_factory=list)
    principles_extracted: list[str] = field(default_factory=list)
    tech_debt_opened: list[str] = field(default_factory=list)
    tech_debt_closed: list[str] = field(default_factory=list)
    action_items: list[dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def add_principle(self, principle_id: str, description: str) -> None:
        self.principles_extracted.append(f"{principle_id}: {description}")

    def add_action(self, description: str, owner: str, due: str = "") -> None:
        self.action_items.append({"description": description, "owner": owner, "due": due})

    def format_markdown(self) -> str:
        lines = [
            f"# {self.phase_name} — Retrospective",
            f"> Author: {self.author} | {time.strftime('%Y-%m-%d', time.gmtime(self.created_at))}",
            "",
            "## 进展良好 ✅",
        ]
        for item in self.what_went_well:
            lines.append(f"- {item}")
        lines += ["", "## 待改进 ⚠️"]
        for item in self.what_to_improve:
            lines.append(f"- {item}")
        if self.principles_extracted:
            lines += ["", "## 提炼原则 📚"]
            for p in self.principles_extracted:
                lines.append(f"- {p}")
        if self.tech_debt_closed:
            lines += ["", "## 技术债务关闭 ✅"]
            for td in self.tech_debt_closed:
                lines.append(f"- {td}")
        if self.tech_debt_opened:
            lines += ["", "## 技术债务新增 ⚠️"]
            for td in self.tech_debt_opened:
                lines.append(f"- {td}")
        if self.action_items:
            lines += ["", "## 行动项 →"]
            for ai in self.action_items:
                due_str = f" (due: {ai['due']})" if ai["due"] else ""
                lines.append(f"- [{ai['owner']}] {ai['description']}{due_str}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Nucleus-style: ADRRecord
# ─────────────────────────────────────────────────────────────────


@dataclass
class ADRRecord:
    """Architecture Decision Record."""

    adr_id: str
    title: str
    status: str = "proposed"
    context: str = ""
    decision: str = ""
    consequences: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    author: str = ""
    created_at: float = field(default_factory=time.time)

    def accept(self, rationale: str = "") -> None:
        self.status = "accepted"
        if rationale:
            self.consequences.append(f"Accepted: {rationale}")

    def format_markdown(self) -> str:
        return "\n".join(
            [
                f"# {self.adr_id}: {self.title}",
                f"Status: {self.status}",
                f"Author: {self.author}",
                "",
                "## Context",
                self.context,
                "",
                "## Decision",
                self.decision,
                "",
                "## Consequences",
                *[f"- {c}" for c in self.consequences],
            ]
        )


# ─────────────────────────────────────────────────────────────────
# Nucleus-style: CollabProtocolRegistry
# ─────────────────────────────────────────────────────────────────


class CollabProtocolRegistry:
    """Registry for collaboration artifacts and templates."""

    def __init__(self) -> None:
        self._artifacts: list[CollabArtifact] = []
        self._adrs: list[ADRRecord] = []

    def create_gate_review(self, phase_name: str, **kwargs: Any) -> GateReviewProtocol:
        return GateReviewProtocol(phase_name=phase_name, **kwargs)

    def create_retrospective(self, phase_name: str, **kwargs: Any) -> RetrospectiveProtocol:
        return RetrospectiveProtocol(phase_name=phase_name, **kwargs)

    def create_adr(self, adr_id: str, title: str, **kwargs: Any) -> ADRRecord:
        adr = ADRRecord(adr_id=adr_id, title=title, **kwargs)
        self._adrs.append(adr)
        return adr

    def get_adr(self, adr_id: str) -> ADRRecord | None:
        return next((a for a in self._adrs if a.adr_id == adr_id), None)

    def list_adrs(self, status: str | None = None) -> list[ADRRecord]:
        if status:
            return [a for a in self._adrs if a.status == status]
        return list(self._adrs)

    def register_artifact(self, artifact: CollabArtifact) -> None:
        self._artifacts.append(artifact)


# ─────────────────────────────────────────────────────────────────
# __all__
# ─────────────────────────────────────────────────────────────────

__all__ = [
    # Enums
    "ProtocolStatus",
    "ProtocolType",
    # Conductor-style classes
    "ChecklistItem",
    "PhaseGateReview",
    "PhaseHandoffProtocol",
    "PhaseRetrospective",
    "PrincipleExtractionProtocol",
    "WorkstreamHandshakeProtocol",
    # Nucleus-style classes
    "ADRRecord",
    "CollabArtifact",
    "CollabProtocolRegistry",
    "GateReviewProtocol",
    "RetrospectiveProtocol",
]
