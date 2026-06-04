"""Workflow orchestration + team management.

Migrated from agentmesh toolkit/src/team/ (WorkflowOrchestrator, TeamManager,
MultiRoleAgentManager, types) and integrates the existing WorkflowEngine from
workflow_engine.py concepts.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

WorkflowPhase = str  # "requirements" | "architecture" | "implementation" | "review" | "debugging" | "documentation"
AgentRole = str
TaskStatus = str  # "pending" | "in_progress" | "reviewing" | "completed" | "failed"


# ----- Team Types -----

@dataclass
class Teammate:
    id: str = ""
    name: str = ""
    role: str = ""
    status: str = "idle"
    current_task: str = ""
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class TeamTask:
    id: str = ""
    title: str = ""
    description: str = ""
    assignee: str = ""
    status: str = "pending"
    priority: str = "medium"
    dependencies: list[str] = field(default_factory=list)
    result: Any = None
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class IterationTask:
    id: str = ""
    phase: WorkflowPhase = ""
    description: str = ""
    agent_role: AgentRole = ""
    status: TaskStatus = "pending"
    iterations: int = 0
    max_iterations: int = 3
    human_approval_required: bool = False
    result: Any = None
    feedback: str = ""
    approved: bool = False


@dataclass
class HumanInterventionRequest:
    id: str = ""
    task_id: str = ""
    type: str = "approval"
    message: str = ""
    options: list[str] = field(default_factory=list)
    response: str = ""
    timestamp: float = 0.0
    resolved: bool = False


# ----- Phase Gate Types (from WorkflowEngine) -----

@dataclass
class GateReview:
    phase_name: str = ""
    test_count: int = 0
    passed: bool = False
    notes: list[str] = field(default_factory=list)
    reviewed_at: float = 0.0


@dataclass
class Retrospective:
    phase_name: str = ""
    what_went_well: list[str] = field(default_factory=list)
    what_to_improve: list[str] = field(default_factory=list)


# ----- TeamManager -----

class TeamManager:
    """Lightweight multi-agent team management with task allocation and messaging."""

    def __init__(self, name: str = "team") -> None:
        self._name = name
        self._teammates: dict[str, Teammate] = {}
        self._tasks: dict[str, TeamTask] = {}
        self._messages: list[dict[str, Any]] = []
        self._next_task = 0

    def add_teammate(self, name: str, role: str, context: dict[str, Any] | None = None) -> Teammate:
        tid = f"tm_{len(self._teammates) + 1}"
        tm = Teammate(id=tid, name=name, role=role, context=context or {})
        self._teammates[tid] = tm
        return tm

    def get_teammates(self) -> list[Teammate]:
        return list(self._teammates.values())

    def get_by_role(self, role: str) -> list[Teammate]:
        return [t for t in self._teammates.values() if t.role == role]

    def update_status(self, teammate_id: str, status: str, task: str = "") -> None:
        tm = self._teammates.get(teammate_id)
        if tm:
            tm.status = status
            tm.current_task = task

    def create_task(self, title: str, description: str = "", priority: str = "medium", deps: list[str] | None = None) -> TeamTask:
        self._next_task += 1
        now = time.time()
        task = TeamTask(id=f"task_{self._next_task}", title=title, description=description, priority=priority, dependencies=deps or [], created_at=now, updated_at=now)
        self._tasks[task.id] = task
        return task

    def get_tasks(self) -> list[TeamTask]:
        return list(self._tasks.values())

    def get_available(self) -> list[TeamTask]:
        return [t for t in self._tasks.values() if t.status == "pending" and all(self._tasks.get(d, TeamTask()).status == "completed" for d in t.dependencies)]

    def assign(self, task_id: str, teammate_id: str) -> bool:
        task = self._tasks.get(task_id)
        tmate = self._teammates.get(teammate_id)
        if not task or not tmate:
            return False
        if any(self._tasks.get(d, TeamTask()).status != "completed" for d in task.dependencies):
            task.status = "blocked"
            return False
        task.assignee = teammate_id
        task.status = "in_progress"
        task.updated_at = time.time()
        tmate.status = "working"
        tmate.current_task = task_id
        return True

    def complete_task(self, task_id: str, result: Any = None) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.status = "completed"
        task.result = result
        task.updated_at = time.time()
        if task.assignee:
            tm = self._teammates.get(task.assignee)
            if tm:
                tm.status = "idle"
                tm.current_task = ""
        return True

    def send_message(self, from_id: str, to: str, content: str) -> dict[str, Any]:
        msg = {"id": f"msg_{len(self._messages) + 1}", "from": from_id, "to": to, "content": content, "timestamp": time.time()}
        self._messages.append(msg)
        return msg

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self._messages)


# ----- WorkflowOrchestrator -----

DEFAULT_PHASES: list[WorkflowPhase] = ["requirements", "architecture", "implementation", "review", "debugging", "documentation"]


class WorkflowOrchestrator:
    """Phase sequence manager with transition rules and human intervention checks."""

    def __init__(self, phases: list[str] | None = None) -> None:
        self._phases: list[str] = phases or DEFAULT_PHASES
        self._current_idx: int = 0
        self._phase_completed: set[str] = set()
        self._interventions: list[HumanInterventionRequest] = []
        self._next_iv = 0

    @property
    def current_phase(self) -> str:
        return self._phases[self._current_idx] if self._current_idx < len(self._phases) else self._phases[-1]

    @property
    def is_complete(self) -> bool:
        return self._current_idx >= len(self._phases) - 1 and self._phases[-1] in self._phase_completed

    def can_advance(self) -> bool:
        return self._current_idx < len(self._phases) - 1

    def advance(self) -> bool:
        if not self.can_advance():
            return False
        self._phase_completed.add(self.current_phase)
        self._current_idx += 1
        return True

    def jump_to(self, phase: str) -> bool:
        if phase in self._phases:
            self._current_idx = self._phases.index(phase)
            return True
        return False

    def get_progress(self) -> dict[str, Any]:
        completed = len(self._phase_completed)
        total = len(self._phases)
        return {"current_phase": self.current_phase, "completed": completed, "total": total, "percentage": round(completed / max(total, 1) * 100), "phase_completed": self.current_phase in self._phase_completed}

    def request_intervention(self, task_id: str, msg: str, options: list[str] | None = None, type: str = "approval") -> HumanInterventionRequest:
        self._next_iv += 1
        req = HumanInterventionRequest(id=f"iv_{self._next_iv}", task_id=task_id, type=type, message=msg, options=options or [], timestamp=time.time())
        self._interventions.append(req)
        return req

    def resolve_intervention(self, intervention_id: str, response: str) -> bool:
        for req in self._interventions:
            if req.id == intervention_id and not req.resolved:
                req.response = response
                req.resolved = True
                return True
        return False

    def get_pending_interventions(self) -> list[HumanInterventionRequest]:
        return [r for r in self._interventions if not r.resolved]


# ----- WorkflowEngine (simplified FullCycleWorkflow) -----

class WorkflowEngine:
    """Full-cycle workflow engine: OBSERVE -> THINK -> PLAN -> EXECUTE -> VERIFY -> LEARN."""

    PHASES = ["observe", "think", "plan", "execute", "verify", "learn"]

    def __init__(self, name: str = "") -> None:
        self.name = name or f"wf_{uuid.uuid4().hex[:6]}"
        self._phases: dict[str, dict[str, Any]] = {}
        self._gates: list[GateReview] = []
        self._retros: list[Retrospective] = []
        self._start = time.time()
        self._active: str = ""

    def enter_phase(self, phase: str) -> dict[str, Any]:
        ctx: dict[str, Any] = {"phase": phase, "data": {}, "workstreams": [], "started_at": time.time()}
        self._phases[phase] = ctx
        self._active = phase
        return ctx

    def record(self, key: str, value: Any) -> None:
        if self._active and self._active in self._phases:
            self._phases[self._active]["data"][key] = value

    def add_workstream(self, ws_id: str, title: str, owner: str = "") -> None:
        if self._active and self._active in self._phases:
            ws = {"id": ws_id, "title": title, "owner": owner, "status": "pending", "tests_added": 0}
            self._phases[self._active]["workstreams"].append(ws)

    def add_gate(self, gate: GateReview) -> None:
        self._gates.append(gate)

    def add_retro(self, retro: Retrospective) -> None:
        self._retros.append(retro)

    def get_summary(self) -> dict[str, Any]:
        all_ws = [ws for p in self._phases.values() for ws in p["workstreams"]]
        return {"name": self.name, "phases_completed": list(self._phases.keys()), "workstreams": len(all_ws), "gates": len(self._gates), "retros": len(self._retros), "duration_s": round(time.time() - self._start, 2)}
