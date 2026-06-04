"""Edge agent types, coordinator, prompt compression, and task offloading.

Port of agentmesh/packages/toolkit/src/edge/ to Python.
"""

from __future__ import annotations

import time
import zlib
from dataclasses import dataclass, field
from typing import Any

# ── Types ──────────────────────────────────────────────────────────────

EdgeAgentType = (
    "reasoning | personal_context | device_info | user_perception | external_knowledge | task_completion"
)
EdgeAgentTypes = (
    "reasoning",
    "personal_context",
    "device_info",
    "user_perception",
    "external_knowledge",
    "task_completion",
)
ComputeTier = str  # "cloud" | "edge" | "device"
OffloadStrategy = str  # "cloud_only" | "edge_only" | "cloud_first" | "edge_first" | "dynamic"


@dataclass
class EdgeAgentConfig:
    type_: str = ""
    name: str = ""
    description: str = ""
    tools: list[str] = field(default_factory=list)


@dataclass
class EdgeTask:
    id: str = ""
    type_: str = "query"  # query | action | retrieval
    input: str = ""
    required_agents: list[str] = field(default_factory=list)
    priority: str = "medium"  # low | medium | high
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeResult:
    task_id: str = ""
    success: bool = True
    output: Any = None
    agent_used: str = ""
    latency: float = 0.0
    error: str = ""


@dataclass
class OffloadDecision:
    target_tier: str = "device"
    reason: str = ""
    estimated_latency: float = 50.0
    estimated_cost: float = 0.001


@dataclass
class CompressionConfig:
    method: str = "token"  # token | summary | hybrid
    target_ratio: float = 0.04


# ── EdgeAgent ──────────────────────────────────────────────────────────


class EdgeAgent:
    """Base edge agent based on CAMPHOR design."""

    AGENT_CONFIGS: dict[str, dict[str, Any]] = {
        "reasoning": {
            "name": "Reasoning Agent",
            "description": "High-level reasoning and planning",
            "tools": ["plan", "delegate", "synthesize"],
        },
        "personal_context": {
            "name": "Personal Context Agent",
            "description": "Search personal context (contacts, calendar, messages)",
            "tools": ["get_contacts", "get_calendar", "get_messages"],
        },
        "device_info": {
            "name": "Device Info Agent",
            "description": "Retrieve device information (location, time, screen)",
            "tools": ["get_location", "get_time", "get_screen"],
        },
        "user_perception": {
            "name": "User Perception Agent",
            "description": "Get recent user activity data",
            "tools": ["get_activities", "get_history", "get_preferences"],
        },
        "external_knowledge": {
            "name": "External Knowledge Agent",
            "description": "Fetch information from external sources",
            "tools": ["web_search", "wiki_search", "calculator"],
        },
        "task_completion": {
            "name": "Task Completion Agent",
            "description": "Execute final actions to complete tasks",
            "tools": ["send_message", "create_event", "make_call"],
        },
    }

    def __init__(self, config: EdgeAgentConfig) -> None:
        self.config = config
        self._tools: dict[str, Any] = {}

    @classmethod
    def create(cls, type_: str) -> EdgeAgent:
        cfg = cls.AGENT_CONFIGS.get(type_)
        if not cfg:
            msg = f"Unknown edge agent type: {type_}"
            raise ValueError(msg)
        return cls(EdgeAgentConfig(type_=type_, name=cfg["name"], description=cfg["description"], tools=cfg["tools"]))

    def register_tool(self, name: str, handler: Any) -> None:
        self._tools[name] = handler

    async def execute(self, task: EdgeTask) -> EdgeResult:
        start = _now()
        try:
            tool_calls = self.config.tools[:1]
            results = []
            for tc in tool_calls:
                handler = self._tools.get(tc)
                if handler:
                    results.append(await handler())
            output = results[0] if len(results) == 1 else results
            return EdgeResult(task_id=task.id, success=True, output=output, agent_used=self.config.type_, latency=_now() - start)
        except Exception as e:
            return EdgeResult(task_id=task.id, success=False, agent_used=self.config.type_, latency=_now() - start, error=str(e))

    def get_info(self) -> dict[str, Any]:
        return {"type": self.config.type_, "name": self.config.name, "tools": self.config.tools}


# ── EdgeCoordinator ────────────────────────────────────────────────────


class EdgeCoordinator:
    """Coordinate multiple edge agents to complete complex tasks."""

    def __init__(self, default_tier: str = "edge") -> None:
        self.tier = default_tier
        self.agents: dict[str, EdgeAgent] = {}
        for t in EdgeAgentTypes:
            agent = EdgeAgent.create(t)
            self.agents[t] = agent

    async def execute(self, task: EdgeTask) -> EdgeResult:
        decision = self._decide_offload(task)
        if decision.target_tier == "cloud":
            return EdgeResult(task_id=task.id, success=True, output={"message": "Cloud execution", "tier": "cloud"}, agent_used="reasoning", latency=decision.estimated_latency)
        return await self._execute_on_edge(task)

    async def _execute_on_edge(self, task: EdgeTask) -> EdgeResult:
        start = _now()
        try:
            sub_results = []
            for agent_type in task.required_agents:
                agent = self.agents.get(agent_type)
                if agent:
                    sub_results.append(await agent.execute(task))
            successes = [r for r in sub_results if r.success]
            output = {"total": len(sub_results), "successful": len(successes), "outputs": [r.output for r in successes]}
            return EdgeResult(task_id=task.id, success=True, output=output, agent_used="reasoning", latency=_now() - start)
        except Exception as e:
            return EdgeResult(task_id=task.id, success=False, agent_used="reasoning", latency=_now() - start, error=str(e))

    def _decide_offload(self, task: EdgeTask) -> OffloadDecision:
        complexity = self._estimate_complexity(task)
        if complexity > 8 and self.tier == "device":
            return OffloadDecision(target_tier="cloud", reason="High complexity", estimated_latency=500)
        if complexity > 5 and self.tier == "edge":
            return OffloadDecision(target_tier="edge", reason="Medium complexity", estimated_latency=200)
        return OffloadDecision(target_tier=self.tier, reason="Low complexity", estimated_latency=50)

    def _estimate_complexity(self, task: EdgeTask) -> float:
        score = min(len(task.input) / 100, 3)
        score += len(task.required_agents)
        if task.type_ == "action":
            score += 2
        elif task.type_ == "query":
            score += 1
        return min(score, 10)

    def set_tier(self, tier: str) -> None:
        self.tier = tier

    def get_agents_info(self) -> list[dict[str, Any]]:
        return [a.get_info() for a in self.agents.values()]


# ── PromptCompressor ──────────────────────────────────────────────────


class PromptCompressor:
    """Compress function definitions into compact tokens (CAMPHOR-based)."""

    def __init__(self, config: CompressionConfig | None = None) -> None:
        self.config = config or CompressionConfig()
        self._cache: dict[str, dict[str, Any]] = {}

    def compress(self, functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.config.method == "summary":
            return [self._summarize(fn) for fn in functions]
        if self.config.method == "hybrid":
            return [self._summarize(fn) if len(fn.get("description", "")) > 100 else self._to_token(fn) for fn in functions]
        return [self._to_token(fn) for fn in functions]

    def _to_token(self, fn: dict[str, Any]) -> dict[str, Any]:
        name = fn.get("name", "")
        if name in self._cache:
            return self._cache[name]
        desc = fn.get("description", "")
        first = name[0].upper() if name else "X"
        h = format(zlib.crc32(desc.encode()) & 0xFFFFFFFF, "x")[:4]
        token = f"{first}{h}"
        embedding = [hash(f"{name}{i}") % 1000 / 500 - 1 for i in range(128)]
        result = {"name": name, "token": token, "embedding": embedding}
        self._cache[name] = result
        return result

    def _summarize(self, fn: dict[str, Any]) -> dict[str, Any]:
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = list(fn.get("parameters", {}).keys())
        key_words = " ".join(desc.split()[:5])
        token = f"{name}: {key_words}. Params: {', '.join(params)}"
        embedding = [hash(f"{name}{i}") % 1000 / 500 - 1 for i in range(128)]
        return {"name": name, "token": token, "embedding": embedding}

    def get_stats(self, functions: list[dict[str, Any]]) -> dict[str, float]:
        compressed = self.compress(functions)
        orig = sum(len(fn.get("name", "")) + len(fn.get("description", "")) / 4 for fn in functions)
        return {"original_tokens": round(orig), "compressed_tokens": len(compressed), "ratio": orig / len(compressed) if compressed else 0}


# ── TaskOffloader ──────────────────────────────────────────────────────


class TaskOffloader:
    """Decide whether to run a task on device, edge, or cloud."""

    def __init__(self, strategy: str = "dynamic", tier: str = "edge") -> None:
        self.strategy = strategy
        self.tier = tier
        self.edge_nodes: dict[str, dict[str, float]] = {}

    def decide(self, task: EdgeTask) -> OffloadDecision:
        if self.strategy == "cloud_only":
            return OffloadDecision(target_tier="cloud", reason="Strategy: cloud only", estimated_latency=600, estimated_cost=0.01)
        if self.strategy == "edge_only":
            return OffloadDecision(target_tier="edge", reason="Strategy: edge only", estimated_latency=75, estimated_cost=0.001)
        if self.strategy == "cloud_first":
            return self._decide_cloud_first(task)
        if self.strategy == "edge_first":
            return self._decide_edge_first(task)
        return self._decide_dynamic(task)

    def _decide_cloud_first(self, task: EdgeTask) -> OffloadDecision:
        c = self._estimate_complexity(task)
        if c > 5:
            return OffloadDecision(target_tier="cloud", reason="Complex task", estimated_latency=600, estimated_cost=0.01)
        return OffloadDecision(target_tier="edge", reason="Simple task", estimated_latency=75, estimated_cost=0.001)

    def _decide_edge_first(self, task: EdgeTask) -> OffloadDecision:
        c = self._estimate_complexity(task)
        load = self._avg_edge_load()
        if c < 8 and load < 0.8:
            return OffloadDecision(target_tier="edge", reason="Edge available", estimated_latency=75, estimated_cost=0.001)
        return OffloadDecision(target_tier="cloud", reason="Edge overloaded", estimated_latency=600, estimated_cost=0.01)

    def _decide_dynamic(self, task: EdgeTask) -> OffloadDecision:
        c = self._estimate_complexity(task)
        load = self._avg_edge_load()
        if c <= 3:
            return OffloadDecision(target_tier="device", reason="Local execution", estimated_latency=15, estimated_cost=0.0001)
        if load < 0.9:
            return OffloadDecision(target_tier="edge", reason="Best性价比", estimated_latency=75, estimated_cost=0.001)
        return OffloadDecision(target_tier="cloud", reason="Cloud best fit", estimated_latency=600, estimated_cost=0.01)

    def _estimate_complexity(self, task: EdgeTask) -> float:
        return min(len(task.input) / 100 + len(task.required_agents) * 2, 10)

    def _avg_edge_load(self) -> float:
        if not self.edge_nodes:
            return 0.5
        return sum(n["load"] for n in self.edge_nodes.values()) / len(self.edge_nodes)

    def register_edge_node(self, node_id: str, capability: float = 20.0) -> None:
        self.edge_nodes[node_id] = {"load": 0.0, "capability": capability}

    def update_edge_load(self, node_id: str, load: float) -> None:
        node = self.edge_nodes.get(node_id)
        if node:
            node["load"] = min(load, 1.0)

    async def migrate_horizontally(self, task: EdgeTask, from_node: str, to_node: str) -> dict[str, Any]:
        from_load = self.edge_nodes.get(from_node, {}).get("load", 1.0)
        to_load = self.edge_nodes.get(to_node, {}).get("load", 0.0)
        if to_load < from_load - 0.3:
            self.update_edge_load(from_node, from_load - 0.3)
            self.update_edge_load(to_node, to_load + 0.3)
            return {"success": True, "reason": f"Migrated {from_node} -> {to_node}"}
        return {"success": False, "reason": "Target node overloaded"}

    def set_strategy(self, strategy: str) -> None:
        self.strategy = strategy

    def get_strategy(self) -> str:
        return self.strategy


# ── Helpers ────────────────────────────────────────────────────────────


def _now() -> float:
    """Monotonic timestamp in milliseconds."""
    return time.monotonic_ns() // 1_000_000


__all__ = [
    "EdgeAgent", "EdgeCoordinator", "PromptCompressor", "TaskOffloader",
    "EdgeAgentConfig", "EdgeTask", "EdgeResult", "OffloadDecision",
]
