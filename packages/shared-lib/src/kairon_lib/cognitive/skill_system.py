"""Skill execution, discovery, loading, routing, and control.

Migrated from agentmesh toolkit/src/skills/ (SkillExecutor, SkillDiscovery,
SkillLoader, SkillRouter, SkillController, types).
"""

from __future__ import annotations

import math
import secrets
from dataclasses import dataclass, field
from typing import Any

SkillAction = str  # "INSERT" | "UPDATE" | "DELETE" | "NOOP"
SkillRole = str  # "specialist" | "generalist" | "architect" | "reviewer"


@dataclass
class SkillDefinition:
    id: str = ""
    name: str = ""
    description: str = ""
    triggers: list[str] = field(default_factory=list)
    role: SkillRole = "specialist"
    category: str = "general"
    version: str = "1.0.0"
    dependencies: list[str] = field(default_factory=list)
    references: list[dict[str, str]] = field(default_factory=list)


@dataclass
class SkillMatchResult:
    skill: SkillDefinition
    confidence: float = 0.0
    matched_triggers: list[str] = field(default_factory=list)


@dataclass
class SkillExecutionContext:
    task: str = ""
    input: str = ""
    session_id: str = "default"
    retrieved_memories: list[str] = field(default_factory=list)
    selected_skills: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillExecutionResult:
    action: SkillAction = "NOOP"
    success: bool = True
    reasoning: str = ""


class SkillLoader:
    """Registry and discovery for skill definitions."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.id] = skill

    def register_many(self, skills: list[SkillDefinition]) -> None:
        for s in skills:
            self.register(s)

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    def get_all(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def search(self, query: str) -> list[SkillDefinition]:
        q = query.lower()
        scored: list[tuple[float, SkillDefinition]] = []
        for skill in self._skills.values():
            score = 0.0
            if q in skill.name.lower():
                score += 10
            if q in skill.description.lower():
                score += 5
            for t in skill.triggers:
                if q in t.lower():
                    score += 3
            if q in skill.category.lower():
                score += 2
            if score > 0:
                scored.append((score, skill))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored]


class SkillRouter:
    """Skill matching based on task keywords and context."""

    def __init__(self, loader: SkillLoader) -> None:
        self._loader = loader

    def match(self, task: str) -> list[SkillMatchResult]:
        task_lower = task.lower()
        results: list[SkillMatchResult] = []
        for skill in self._loader.get_all():
            matched: list[str] = []
            confidence = 0.0
            for trigger in skill.triggers:
                if trigger.lower() in task_lower:
                    matched.append(trigger)
                    confidence += 0.3
            name_parts = skill.name.lower().split("-")
            if any(p in task_lower for p in name_parts):
                confidence += 0.2
            results.append(SkillMatchResult(skill=skill, confidence=min(confidence, 1.0), matched_triggers=matched))
        results.sort(key=lambda r: r.confidence, reverse=True)
        return [r for r in results if r.confidence > 0.05]

    def get_best(self, task: str) -> SkillMatchResult | None:
        matches = self.match(task)
        return matches[0] if matches else None


class SkillController:
    """Skill scoring, top-K selection, and execution."""

    def __init__(self, top_k: int = 3, temperature: float = 1.0, threshold: float = 0.3) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        self._usage: dict[str, dict[str, int]] = {}  # skill_id -> {success, fail}
        self._top_k = top_k
        self._temperature = temperature
        self._threshold = threshold

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.id] = skill
        self._usage.setdefault(skill.id, {"success": 0, "fail": 0})

    def get_all(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def select(self, context: SkillExecutionContext) -> list[tuple[SkillDefinition, float]]:
        scored: list[tuple[SkillDefinition, float]] = []
        for skill in self._skills.values():
            score = self._score(skill, context)
            if score >= self._threshold:
                if self._temperature > 0:
                    gumbel = -math.log(-math.log(max(secrets.randbits(30) / (2**30), 1e-10)))
                    score += gumbel * self._temperature
                scored.append((skill, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[: self._top_k]

    def _score(self, skill: SkillDefinition, context: SkillExecutionContext) -> float:
        task = context.task.lower()
        score = 0.1
        for trigger in skill.triggers:
            if trigger.lower() in task:
                score = 1.0
                break
        usage = self._usage.get(skill.id, {"success": 0, "fail": 0})
        total = usage["success"] + usage["fail"]
        if total > 0:
            score = score * 0.7 + (usage["success"] / total) * 0.3
        return min(score, 1.0)

    def record_usage(self, skill_id: str, success: bool) -> None:
        entry = self._usage.setdefault(skill_id, {"success": 0, "fail": 0})
        if success:
            entry["success"] += 1
        else:
            entry["fail"] += 1


class SkillExecutor:
    """Skill execution with LLM prompting or rule-based fallback."""

    def __init__(self, verbose: bool = False) -> None:
        self._verbose = verbose

    async def execute(self, context: SkillExecutionContext) -> SkillExecutionResult:
        task = context.task.lower()
        if any(kw in task for kw in ["delete", "remove", "erase", "clear"]):
            return SkillExecutionResult(action="DELETE", reasoning="Task contains delete keywords")
        if any(kw in task for kw in ["update", "modify", "change", "edit"]):
            return SkillExecutionResult(action="UPDATE", reasoning="Task contains update keywords")
        if any(kw in task for kw in ["add", "create", "new", "insert", "build"]):
            return SkillExecutionResult(action="INSERT", reasoning="Task contains create keywords")
        return SkillExecutionResult(action="NOOP", reasoning="No clear action determined")
