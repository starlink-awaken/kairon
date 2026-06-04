"""
---
Type: Module
Status: ACTIVE
Layer: L3
---

FullCycleWorkflow engine for B-OS — OBSERVE→THINK→PLAN→EXECUTE→VERIFY→LEARN.

This encodes the actual workflow used across B-OS Phases 1-6.

Usage:
    engine = WorkflowEngine(name="Feature X")

    with engine.phase(WorkflowPhase.OBSERVE) as ctx:
        ctx.record("user_request", "add federation support")
        ctx.record("constraints", ["stdlib only", "no breaking changes"])

    with engine.phase(WorkflowPhase.PLAN) as ctx:
        ctx.add_workstream("ws-a", "Node identity", owner="@Forge")
        ctx.add_workstream("ws-b", "Federation router", owner="@Forge")

    summary = engine.get_summary()
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, TypedDict


class TraceContextProtocol(Protocol):
    def add_span(self, name: str, **metadata: Any) -> Any: ...

    def finish_span(self, span: Any) -> None: ...


class WorkflowSummary(TypedDict):
    name: str
    workflow_id: str
    phases_completed: list[str]
    workstreams: int
    gate_reviews: int
    retrospectives: int
    total_tests_added: int
    duration_s: float


from kairon_lib._compat import get_current_trace

_TRACING_AVAILABLE = True  # stubs from _compat are always available


class WorkflowPhase(StrEnum):
    OBSERVE = "observe"  # Perceive requirements, constraints, context
    THINK = "think"  # Analyze, deliberate, synthesize options
    PLAN = "plan"  # Decompose into workstreams, set milestones
    EXECUTE = "execute"  # Parallel workstream execution
    VERIFY = "verify"  # Gate review, test counts, ruff, quality checks
    LEARN = "learn"  # Retrospective, principle extraction, archiving


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass
class WorkstreamSpec:
    ws_id: str
    title: str
    owner: str = ""
    description: str = ""
    tasks: list[str] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: dict[str, object] = field(default_factory=dict)
    started_at: float | None = None
    completed_at: float | None = None
    tests_added: int = 0
    commit: str = ""

    def start(self) -> None:
        self.status = WorkflowStatus.IN_PROGRESS
        self.started_at = time.time()

    def complete(self, commit: str = "", tests_added: int = 0) -> None:
        self.status = WorkflowStatus.DONE
        self.completed_at = time.time()
        self.commit = commit
        self.tests_added = tests_added

    @property
    def duration_s(self) -> float | None:
        if self.started_at and self.completed_at:
            return round(self.completed_at - self.started_at, 2)
        return None


@dataclass
class GateReview:
    phase_name: str
    test_count: int = 0
    test_baseline: int = 0
    ruff_errors: int = 0
    passed: bool = False
    notes: list[str] = field(default_factory=list)
    reviewed_at: float = field(default_factory=time.time)

    @property
    def tests_added(self) -> int:
        return self.test_count - self.test_baseline

    def check_gate(self, min_tests_added: int = 0, max_ruff_errors: int = 0) -> bool:
        self.passed = self.tests_added >= min_tests_added and self.ruff_errors <= max_ruff_errors
        return self.passed


@dataclass
class Retrospective:
    phase_name: str
    what_went_well: list[str] = field(default_factory=list)
    what_to_improve: list[str] = field(default_factory=list)
    principles_extracted: list[str] = field(default_factory=list)
    tech_debt_opened: list[str] = field(default_factory=list)
    tech_debt_closed: list[str] = field(default_factory=list)
    archived_at: float = field(default_factory=time.time)


@dataclass
class PhaseContext:
    """Context passed to `with engine.phase(...)` blocks."""

    phase: WorkflowPhase
    data: dict[str, object] = field(default_factory=dict)
    workstreams: list[WorkstreamSpec] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def record(self, key: str, value: Any) -> None:
        self.data[key] = value

    def add_workstream(
        self,
        ws_id: str,
        title: str,
        owner: str = "",
        description: str = "",
        tasks: list[str] | None = None,
    ) -> WorkstreamSpec:
        ws = WorkstreamSpec(
            ws_id=ws_id,
            title=title,
            owner=owner,
            description=description,
            tasks=tasks or [],
        )
        self.workstreams.append(ws)
        return ws


class WorkflowEngine:
    """Encodes the FullCycleWorkflow (OBSERVE→THINK→PLAN→EXECUTE→VERIFY→LEARN).

    This is the machine-executable version of the B-OS Phases 1-6 methodology.
    """

    PHASE_ORDER = [
        WorkflowPhase.OBSERVE,
        WorkflowPhase.THINK,
        WorkflowPhase.PLAN,
        WorkflowPhase.EXECUTE,
        WorkflowPhase.VERIFY,
        WorkflowPhase.LEARN,
    ]

    def __init__(
        self,
        name: str,
        description: str = "",
        trace_ctx: TraceContextProtocol | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.workflow_id = str(uuid.uuid4())[:8]
        self._phases: dict[WorkflowPhase, PhaseContext] = {}
        self._gate_reviews: list[GateReview] = []
        self._retrospectives: list[Retrospective] = []
        self._current_phase: WorkflowPhase | None = None
        self._started_at = time.time()
        # Optional TraceContext for cross-domain tracing propagation.
        self.trace_ctx: TraceContextProtocol | None = trace_ctx or get_current_trace()

    @contextmanager
    def phase(
        self,
        phase: WorkflowPhase,
        trace_ctx: TraceContextProtocol | None = None,
    ) -> Generator[PhaseContext]:
        """Context manager to run a workflow phase.

        Args:
            phase:     The workflow phase to enter.
            trace_ctx: Optional TraceContext for distributed tracing.  Falls
                       back to self.trace_ctx then the ambient context var.
        """
        effective_trace: TraceContextProtocol | None = trace_ctx or self.trace_ctx or get_current_trace()
        span = None
        if (
            effective_trace is not None
            and hasattr(effective_trace, "add_span")
            and hasattr(effective_trace, "finish_span")
        ):
            span = effective_trace.add_span(f"workflow.{phase.value}", workflow_id=self.workflow_id)

        ctx = PhaseContext(phase=phase)
        self._current_phase = phase
        self._phases[phase] = ctx
        try:
            yield ctx
        finally:
            self._current_phase = None
            if effective_trace is not None and span is not None:
                effective_trace.finish_span(span)

    def get_phase(self, phase: WorkflowPhase) -> PhaseContext | None:
        return self._phases.get(phase)

    def get_phase_context(self, phase: WorkflowPhase) -> PhaseContext | None:
        """Legacy alias for get_phase()."""
        return self.get_phase(phase)

    def add_gate_review(self, gate: GateReview) -> None:
        self._gate_reviews.append(gate)

    def add_retrospective(self, retro: Retrospective) -> None:
        self._retrospectives.append(retro)

    def get_all_workstreams(self) -> list[WorkstreamSpec]:
        ws: list[WorkstreamSpec] = []
        for ctx in self._phases.values():
            ws.extend(ctx.workstreams)
        return ws

    def get_workstream(self, ws_id: str) -> WorkstreamSpec | None:
        for ws in self.get_all_workstreams():
            if ws.ws_id == ws_id:
                return ws
        return None

    @property
    def completed_phases(self) -> list[WorkflowPhase]:
        return [p for p in self.PHASE_ORDER if p in self._phases]

    @property
    def total_tests_added(self) -> int:
        return sum(ws.tests_added for ws in self.get_all_workstreams())

    def get_summary(self) -> WorkflowSummary:
        return {
            "name": self.name,
            "workflow_id": self.workflow_id,
            "phases_completed": [p.value for p in self.completed_phases],
            "workstreams": len(self.get_all_workstreams()),
            "gate_reviews": len(self._gate_reviews),
            "retrospectives": len(self._retrospectives),
            "total_tests_added": self.total_tests_added,
            "duration_s": round(time.time() - self._started_at, 2),
        }

    def format_report(self) -> str:
        summary = self.get_summary()
        lines = [
            f"=== Workflow Report: {self.name} ===",
            f"ID: {self.workflow_id}",
            f"Phases: {' → '.join(summary['phases_completed'])}",
            f"Workstreams: {summary['workstreams']}",
            f"Tests added: {summary['total_tests_added']}",
            f"Gate reviews: {summary['gate_reviews']}",
            "",
        ]
        for gate in self._gate_reviews:
            status = "✅ PASSED" if gate.passed else "❌ FAILED"
            lines.append(
                f"  Gate [{gate.phase_name}]: {status} — {gate.test_count} tests, {gate.ruff_errors} ruff errors"
            )
        return "\n".join(lines)
