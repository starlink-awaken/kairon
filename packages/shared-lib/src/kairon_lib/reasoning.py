"""Advanced reasoning toolkit.

Port of agentmesh /memory/ReasoningBank.ts, /memory/Principles.ts,
and /memory/SelfJudge.ts.

Provides ReasoningBank for closed-loop learning from task results,
Principles for constitutional agent governance, and SelfJudge for
self-evaluation against criteria.
"""

from __future__ import annotations

import math
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

EmbeddingProvider = Callable[[str], Awaitable[list[float]]]
StorageAdapter = Callable[[], Awaitable[None]]

@dataclass
class TaskResult:

    task_id: str
    input: Any = None
    output: Any = None
    success: bool = False
    trajectory: list[str] = field(default_factory=list)
    duration: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ReasoningMemory:
    memory_id: str = ""
    title: str = ""
    description: str = ""
    content: str = ""
    outcome: str = "unknown"
    refinement_level: int = 1
    original_task: str = ""
    trajectory: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    embedding: list[float] | None = None

@dataclass
class Principle:

    pid: int = 0
    name: str = ""
    level: str = "silver"
    rule: str = ""
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)

@dataclass
class Scenario:

    sid: str = ""
    name: str = ""
    keywords: list[str] = field(default_factory=list)
    recommended_principles: list[int] = field(default_factory=list)
    description: str = ""

# ReasoningBank

class ReasoningBank:
    """Structured reasoning memory with closed-loop learning.

    Port of TS ReasoningBank: retrieve -> construct -> consolidate cycle.
    Supports both simple text search and embedding-based semantic search.
    """

    def __init__(
        self,
        max_memories: int = 10000,
        embedding_provider: EmbeddingProvider | None = None,
        auto_persist: bool = False,
        storage_adapter: StorageAdapter | None = None,
    ) -> None:
        self._memories: dict[str, ReasoningMemory] = {}
        self._max_memories = max_memories
        self._embedding_provider = embedding_provider
        self._auto_persist = auto_persist
        self._storage_adapter = storage_adapter
        self._self_judge = SelfJudge()

    async def retrieve(self, query: str, limit: int = 5) -> list[ReasoningMemory]:
        if self._embedding_provider:
            return await self._embedding_search(query, limit)
        return self._simple_search(query, limit)

    def _simple_search(self, query: str, limit: int) -> list[ReasoningMemory]:
        q = query.lower()
        scored: list[tuple[ReasoningMemory, float]] = []
        for mem in self._memories.values():
            score = sum(10 for _ in [1] if q in mem.title.lower())
            score += sum(5 for _ in [1] if q in mem.description.lower())
            score += sum(3 for _ in [1] if q in mem.content.lower())
            score += sum(2 for _ in mem.tags if q in _.lower())
            score += math.log(mem.access_count + 1)  # type: ignore[assignment]
            if score > 0:
                scored.append((mem, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        result = [mem for mem, _ in scored[:limit]]
        for mem in result:
            mem.access_count += 1
        return result

    async def _embedding_search(self, query: str, limit: int) -> list[ReasoningMemory]:
        try:
            q_emb = await self._embedding_provider(query)  # type: ignore
        except Exception:
            return self._simple_search(query, limit)
        scored: list[tuple[ReasoningMemory, float]] = []
        for mem in self._memories.values():
            if mem.embedding is not None:
                sim = self._cosine_similarity(q_emb, mem.embedding)
                scored.append((mem, sim))
            else:
                scored.append((mem, 0.0))
        scored.sort(key=lambda x: x[1], reverse=True)
        result = [mem for mem, _ in scored[:limit]]
        for mem in result:
            mem.access_count += 1
        return result

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(ai * bi for ai, bi in zip(a, b))
        na, nb = math.sqrt(sum(x*x for x in a)), math.sqrt(sum(x*x for x in b))
        return dot / (na * nb) if na and nb else 0.0

    async def construct(self, result: TaskResult) -> ReasoningMemory:

        outcome = await self._self_judge.judge(result)
        if outcome == "success":
            return self._learn_from_success(result)
        return self._learn_from_failure(result)

    async def learn(self, result: TaskResult) -> ReasoningMemory:

        memory = await self.construct(result)
        await self.consolidate(memory)
        return memory

    async def consolidate(self, memory: ReasoningMemory) -> None:

        if len(self._memories) >= self._max_memories:
            self._evict()
        self._memories[memory.memory_id] = memory

    def _learn_from_success(self, result: TaskResult) -> ReasoningMemory:
        desc = str(result.input)[:50] if result.input else ""
        traj = result.trajectory or []
        return ReasoningMemory(
            memory_id=f"rb_success_{uuid.uuid4().hex[:8]}",
            title=self._extract_title(result, "Strategy"),
            description=f"Successfully completed: {desc}...",
            content=self._format_trajectory(traj, result.output),
            outcome="success",
            original_task=str(result.input)[:200] if result.input else "",
            trajectory=traj,
            tags=self._infer_tags(result),
        )

    def _learn_from_failure(self, result: TaskResult) -> ReasoningMemory:
        desc = str(result.input)[:50] if result.input else ""
        analysis = self._self_judge.analyze_failure(result)
        traj = result.trajectory or []
        return ReasoningMemory(
            memory_id=f"rb_failure_{uuid.uuid4().hex[:8]}",
            title=self._extract_title(result, "Failure"),
            description=f"Failed: {desc}...",
            content=self._build_failure_guide(analysis, traj, result.error),
            outcome="failure",
            original_task=str(result.input)[:200] if result.input else "",
            trajectory=traj,
            tags=self._infer_tags(result) + ["failure", "lesson-learned"],
        )

    @staticmethod
    def _extract_title(result: TaskResult, prefix: str) -> str:
        meta = result.metadata or {}
        if "strategy" in meta:
            return str(meta["strategy"])
        traj = result.trajectory or []
        if traj:
            return f"{prefix}: {traj[-1][:50]}"
        return f"{prefix}: task completed"

    @staticmethod
    def _format_trajectory(trajectory: list[str], output: Any) -> str:
        parts = ["Steps taken:"]
        for i, step in enumerate(trajectory, 1):
            parts.append(f"{i}. {step}")
        if output is not None:
            parts.append(f"\nResult: {str(output)[:200]}")
        return "\n".join(parts)

    @staticmethod
    def _build_failure_guide(analysis: str, trajectory: list[str], error: str | None) -> str:
        parts = ["## Failure Analysis", analysis, "\n## Trajectory"] + [f"{i}. {s}" for i, s in enumerate(trajectory, 1)]
        parts.append("\n## Recommendations")
        if error:
            el = error.lower()
            if "timeout" in el: parts += ["- Increase timeout", "- Check connectivity"]
            if "permission" in el or "denied" in el: parts += ["- Verify permissions", "- Check auth"]
            if "not found" in el or "404" in el: parts += ["- Verify resource", "- Check identifiers"]
        return "\n".join(parts)

    @staticmethod
    def _infer_tags(result: TaskResult) -> list[str]:
        tags: list[str] = []
        inp = str(result.input).lower() if result.input else ""
        if "search" in inp:
            tags.append("search")
        if "code" in inp:
            tags.append("coding")
        if "test" in inp:
            tags.append("testing")
        meta = result.metadata or {}
        if "category" in meta:
            tags.append(str(meta["category"]))
        return tags or ["general"]

    def _evict(self) -> None:
        oldest: str | None = None
        min_access = float("inf")
        for mid, mem in self._memories.items():
            if mem.access_count < min_access:
                min_access = mem.access_count
                oldest = mid
        if oldest:
            del self._memories[oldest]

    def get_all(self) -> list[ReasoningMemory]:
        return list(self._memories.values())

    def clear(self) -> None:
        self._memories.clear()

class SelfJudge:
    """Self-evaluation against task criteria."""

    def __init__(self, enable_refinement: bool = False) -> None:
        self._enable_refinement = enable_refinement

    async def judge(self, result: TaskResult) -> str:

        if result.success:
            return "success"
        if result.error:
            return "failure"
        if result.output is not None:
            return "success"
        return "failure"

    def analyze_failure(self, result: TaskResult) -> str:
        traj = result.trajectory or []
        if not traj:
            return "No trajectory available for analysis"
        patterns = self._detect_failure_patterns(traj)
        if patterns:
            return "; ".join(patterns)
        last = traj[-3:]
        return f"Failed at: {' -> '.join(last)}"

    async def refine(self, content: str, trajectory: list[str] | None = None) -> str:
        if not self._enable_refinement or not trajectory:
            return content
        insights: list[str] = []
        for step in trajectory:
            low = step.lower()
            if any(kw in low for kw in ("think", "reason", "maybe")):
                insights.append(step)
        if not insights:
            return content
        return f"{content}\n\n---\nRefined insights:\n" + "\n".join(insights)

    @staticmethod
    def _detect_failure_patterns(trajectory: list[str]) -> list[str]:
        patterns: list[str] = []
        for step in trajectory:
            low = step.lower()
            if "error" in low or "fail" in low:
                patterns.append(f"Error detected: {step}")
            if "timeout" in low:
                patterns.append("Operation timeout")
            if "permission" in low or "denied" in low:
                patterns.append("Permission denied")
            if "not found" in low or "404" in low:
                patterns.append("Resource not found")
        return patterns

# Principles

CORE_PRINCIPLES: list[Principle] = [
    Principle(pid=1, name="User Need Validation", level="iron", rule="Never assume — ask first",
              description="Confirm requirements with user before acting.",
              keywords=["user needs", "validation", "confirm"], scenarios=["new-project"], questions=["Has this been confirmed?"]),
    Principle(pid=2, name="ROI Conservatism", level="iron", rule="Optimism is fantasy",
              description="Consider worst case. Costs and risks exceed estimates.",
              keywords=["cost", "budget", "ROI", "risk"], scenarios=["cost-budget"], questions=["What is worst-case cost?"]),
    Principle(pid=3, name="XY Problem Awareness", level="gold", rule="Ask why 5x first",
              description="Proposed solution (Y) != real problem (X). Trace root cause.",
              keywords=["XY problem", "root cause"], scenarios=["major-decision"], questions=["What is the core problem?"]),
    Principle(pid=4, name="Multi-Agent Analysis ROI", level="gold", rule="Small spend prevents big loss",
              description="Analyse complex decisions from multiple agent perspectives.",
              keywords=["multi-agent", "analysis"], scenarios=["major-decision"], questions=["Multiple perspectives needed?"]),
    Principle(pid=5, name="Competitor Silence", level="silver", rule="90% there is a reason",
              description="If competitors avoid something, understand why.",
              keywords=["competitor", "market"], scenarios=["tech-selection"], questions=["Why not done by competitors?"]),
    Principle(pid=6, name="Document Pyramid", level="silver", rule="5/20/75 rule",
              description="Conclusion first, then solution, then detail.",
              keywords=["documentation", "pyramid"], scenarios=["documentation"], questions=["Key takeaway clear?"]),
    Principle(pid=7, name="Hidden Costs", level="silver", rule="Tip of the iceberg",
              description="Training, migration, opportunity costs are often overlooked.",
              keywords=["cost", "hidden"], scenarios=["cost-budget"], questions=["Hidden costs accounted for?"]),
    Principle(pid=8, name="Measurability", level="gold", rule="Vague = Invalid",
              description="Every target must be measurable.",
              keywords=["metric", "KPI"], scenarios=["verification"], questions=["How to quantify success?"]),
    Principle(pid=9, name="Tech Selection", level="iron", rule="POC before commit",
              description="Proof-of-concept before adopting new tech.",
              keywords=["tech selection", "POC"], scenarios=["tech-selection"], questions=["Has POC been done?"]),
    Principle(pid=10, name="Phased Decisions", level="silver", rule="Exit point per phase",
             description="Every phase must have a go/no-go exit point.",
             keywords=["phased", "milestone"], scenarios=["new-project"], questions=["Exit criteria defined?"]),
]

SCENARIOS: list[Scenario] = [
    Scenario(sid="new-project", name="New Project", keywords=["new project", "start", "greenfield"], recommended_principles=[1, 10, 2], description="Starting a new project"),
    Scenario(sid="tech-selection", name="Tech Selection", keywords=["tech", "framework", "tool"], recommended_principles=[9, 5, 7], description="Choosing technology"),
    Scenario(sid="user-research", name="User Research", keywords=["user", "interview", "feedback"], recommended_principles=[1, 3], description="Understanding users"),
    Scenario(sid="cost-budget", name="Cost Budget", keywords=["cost", "budget", "ROI"], recommended_principles=[2, 7, 8], description="Cost evaluation"),
    Scenario(sid="major-decision", name="Major Decision", keywords=["decision", "trade-off"], recommended_principles=[3, 4, 2], description="High-stakes decisions"),
    Scenario(sid="documentation", name="Documentation", keywords=["doc", "report", "summary"], recommended_principles=[6], description="Writing docs"),
    Scenario(sid="risk-management", name="Risk Management", keywords=["risk", "issue", "challenge"], recommended_principles=[4, 2, 8], description="Risk mitigation"),
    Scenario(sid="verification", name="Verification", keywords=["verify", "test", "validate"], recommended_principles=[9, 8, 10], description="Solution verification"),
]

class Principles:
    """Constitutional principles for agent governance."""

    def __init__(self) -> None:
        self._principles = CORE_PRINCIPLES
        self._scenarios = SCENARIOS

    def search(self, query: str) -> list[Principle]:
        q = query.lower()
        return [p for p in self._principles if (q in p.name.lower() or q in p.rule.lower() or q in p.description.lower() or any(q in kw.lower() for kw in p.keywords))]

    def match_scenario(self, text: str) -> Scenario | None:
        t = text.lower()
        for s in self._scenarios:
            if s.sid == t:
                return s
        best: Scenario | None = None
        best_score = 0
        for s in self._scenarios:
            score = sum(len(kw) for kw in s.keywords if kw.lower() in t)
            if score > best_score:
                best_score = score
                best = s
        return best

    def recommend(self, text: str) -> list[Principle]:
        scenario = self.match_scenario(text)
        if scenario:
            return [p for p in self._principles if p.pid in scenario.recommended_principles]
        return self.search(text)

__all__ = [
    "TaskResult", "ReasoningMemory", "Principle", "Scenario",
    "ReasoningBank", "SelfJudge", "Principles",
    "CORE_PRINCIPLES", "SCENARIOS",
    "EmbeddingProvider", "StorageAdapter",
]
