"""Agent design patterns from the agentmesh toolkit.

Each pattern is a pure function that takes a context dict and returns a
PatternResult describing the pattern's execution plan.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Any


class StepStatus(str, enum.Enum):  # noqa: UP042 — StrEnum requires Python 3.11+
    """Execution status of a single pattern step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PatternStep:
    """A single step within an agent pattern execution plan."""

    step_id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING

    @classmethod
    def new(cls, action: str, **params: Any) -> PatternStep:
        return cls(step_id=uuid.uuid4().hex[:8], action=action, params=params)


@dataclass
class PatternResult:
    """Result of evaluating a pattern against a context."""

    pattern_name: str
    status: StepStatus
    steps: list[PatternStep] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 16 pattern functions
# ---------------------------------------------------------------------------


def prompt_chaining(ctx: dict[str, Any]) -> PatternResult:
    """Chain multiple prompts sequentially; output of one is input to the next."""
    steps = [
        PatternStep.new("stage_1", prompt=ctx.get("initial_prompt"), phase="prepare_input"),
        PatternStep.new("stage_2", prompt=None, phase="intermediate_transform"),
        PatternStep.new("stage_3", prompt=None, phase="final_output"),
    ]
    return PatternResult(
        pattern_name="prompt_chaining",
        status=StepStatus.PENDING,
        steps=steps,
        result={"chain_length": len(steps), "entry_prompt": ctx.get("initial_prompt")},
    )


def routing(ctx: dict[str, Any]) -> PatternResult:
    """Route input to different handlers based on classification."""
    routes = ctx.get("routes", ["handler_a", "handler_b", "handler_c"])
    classifier = ctx.get("classifier", "default_classifier")
    steps = [
        PatternStep.new("classify", classifier=classifier, input=ctx.get("input")),
        PatternStep.new("route", routes=routes, selected_route=None),
        PatternStep.new("dispatch", handler=None, payload=None),
    ]
    return PatternResult(
        pattern_name="routing",
        status=StepStatus.PENDING,
        steps=steps,
        result={"available_routes": routes, "classifier": classifier},
    )


def parallelization(ctx: dict[str, Any]) -> PatternResult:
    """Execute multiple agents in parallel and aggregate results."""
    agent_count = ctx.get("agent_count", 3)
    steps = [
        PatternStep.new("fan_out", agent_count=agent_count, task=ctx.get("task")),
        *[PatternStep.new(f"agent_{i}", role=f"worker_{i}") for i in range(agent_count)],
        PatternStep.new("aggregate", strategy=ctx.get("aggregation", "majority_vote")),
    ]
    return PatternResult(
        pattern_name="parallelization",
        status=StepStatus.PENDING,
        steps=steps,
        result={"agent_count": agent_count, "aggregation": ctx.get("aggregation", "majority_vote")},
    )


def planning(ctx: dict[str, Any]) -> PatternResult:
    """Decompose complex task into sub-tasks, execute them, synthesize."""
    sub_tasks = ctx.get("sub_tasks", ["research", "draft", "review"])
    steps = [
        PatternStep.new("decompose", task=ctx.get("task"), sub_tasks=sub_tasks),
        *[PatternStep.new(f"execute_{st}", sub_task=st) for st in sub_tasks],
        PatternStep.new("synthesize", sources=sub_tasks),
    ]
    return PatternResult(
        pattern_name="planning",
        status=StepStatus.PENDING,
        steps=steps,
        result={"sub_tasks": sub_tasks},
    )


def tool_use(ctx: dict[str, Any]) -> PatternResult:
    """Agent uses external tools to accomplish tasks."""
    tools = ctx.get("tools", ["web_search", "code_interpreter", "file_read"])
    steps = [
        PatternStep.new("tool_selection", task=ctx.get("task"), available_tools=tools, selected_tool=None),
        PatternStep.new("tool_execution", tool=None, arguments={}),
        PatternStep.new("tool_result_ingestion", raw_output=None),
    ]
    return PatternResult(
        pattern_name="tool_use",
        status=StepStatus.PENDING,
        steps=steps,
        result={"available_tools": tools, "max_retries": ctx.get("max_retries", 3)},
    )


def knowledge_retrieval(ctx: dict[str, Any]) -> PatternResult:
    """Retrieve relevant knowledge from store before acting."""
    steps = [
        PatternStep.new("embed_query", query=ctx.get("query"), embedding_model=ctx.get("embedding_model", "default")),
        PatternStep.new("vector_search", top_k=ctx.get("top_k", 5)),
        PatternStep.new("rerank", strategy=ctx.get("rerank_strategy", "cross_encoder")),
        PatternStep.new("context_inject", max_tokens=ctx.get("max_context_tokens", 4096)),
    ]
    return PatternResult(
        pattern_name="knowledge_retrieval",
        status=StepStatus.PENDING,
        steps=steps,
        result={
            "top_k": ctx.get("top_k", 5),
            "knowledge_base": ctx.get("knowledge_base", "default"),
        },
    )


def structured_output(ctx: dict[str, Any]) -> PatternResult:
    """Enforce structured output format via schema validation."""
    schema = ctx.get("schema", {"type": "object", "properties": {}})
    steps = [
        PatternStep.new("instruct", schema=schema, instruction=ctx.get("instruction")),
        PatternStep.new("generate", format=schema.get("type", "object")),
        PatternStep.new("validate", against=schema, is_valid=False),
        PatternStep.new("format", target=ctx.get("output_format", "json")),
    ]
    return PatternResult(
        pattern_name="structured_output",
        status=StepStatus.PENDING,
        steps=steps,
        result={
            "schema_type": schema.get("type"),
            "output_format": ctx.get("output_format", "json"),
        },
    )


def memory_management(ctx: dict[str, Any]) -> PatternResult:
    """Maintain and update working memory across turns."""
    memory_type = ctx.get("memory_type", "sliding_window")
    window_size = ctx.get("window_size", 10)
    steps = [
        PatternStep.new("read", source=memory_type, keys=ctx.get("memory_keys", ["last_turn"])),
        PatternStep.new("update", memory_type=memory_type, new_content=ctx.get("new_content"), window_size=window_size),
        PatternStep.new("summarize", strategy=ctx.get("summarization", "recency_weighted"), max_tokens=ctx.get("max_memory_tokens", 2048)),
        PatternStep.new("persist", store=ctx.get("memory_store", "ephemeral")),
    ]
    return PatternResult(
        pattern_name="memory_management",
        status=StepStatus.PENDING,
        steps=steps,
        result={
            "memory_type": memory_type,
            "window_size": window_size,
            "turn_count": ctx.get("turn_count", 0),
        },
    )


def reflection(ctx: dict[str, Any]) -> PatternResult:
    """Agent reflects on its own output and improves."""
    steps = [
        PatternStep.new("generate_output", task=ctx.get("task"), initial_output=None),
        PatternStep.new("self_review", criteria=ctx.get("criteria", ["accuracy", "clarity", "completeness"])),
        PatternStep.new("identify_gaps", gaps=[]),
        PatternStep.new("refine", improvement_plan=None),
    ]
    return PatternResult(
        pattern_name="reflection",
        status=StepStatus.PENDING,
        steps=steps,
        result={"criteria": ctx.get("criteria", ["accuracy", "clarity", "completeness"]), "max_iterations": ctx.get("max_iterations", 3)},
    )


def self_correction(ctx: dict[str, Any]) -> PatternResult:
    """Detect errors in own output and correct."""
    validators = ctx.get("validators", ["consistency", "factuality", "format"])
    steps = [
        PatternStep.new("produce", task=ctx.get("task")),
        PatternStep.new("validate", validators=validators, errors=[]),
        PatternStep.new("diagnose", error_type=None, root_cause=None),
        PatternStep.new("correct", patch=None),
        PatternStep.new("re_validate", passed=False),
    ]
    return PatternResult(
        pattern_name="self_correction",
        status=StepStatus.PENDING,
        steps=steps,
        result={"validators": validators, "max_attempts": ctx.get("max_attempts", 3)},
    )


def learning_adaptation(ctx: dict[str, Any]) -> PatternResult:
    """Learn from past experiences and adapt behavior."""
    experience_store = ctx.get("experience_store", "episodic_buffer")
    steps = [
        PatternStep.new("retrieve_experiences", store=experience_store, similar_to=ctx.get("task"), top_k=ctx.get("top_k", 5)),
        PatternStep.new("extract_lessons", patterns=[], failures=[], successes=[]),
        PatternStep.new("update_strategy", delta=None),
        PatternStep.new("execute_adapted", strategy=None),
        PatternStep.new("store_outcome", outcome=None),
    ]
    return PatternResult(
        pattern_name="learning_adaptation",
        status=StepStatus.PENDING,
        steps=steps,
        result={
            "experience_store": experience_store,
            "total_experiences": ctx.get("total_experiences", 0),
            "adaptation_rate": ctx.get("adaptation_rate", 0.1),
        },
    )


def multi_agent_collaboration(ctx: dict[str, Any]) -> PatternResult:
    """Multiple agents collaborate on a shared task."""
    agents = ctx.get("agents", ["researcher", "writer", "critic"])
    steps = [
        PatternStep.new("broadcast", task=ctx.get("task"), participants=agents),
        *[PatternStep.new(f"contribute_{a}", agent=a) for a in agents],
        PatternStep.new("merge", strategy=ctx.get("merge_strategy", "consensus")),
        PatternStep.new("finalize", output=None),
    ]
    return PatternResult(
        pattern_name="multi_agent_collaboration",
        status=StepStatus.PENDING,
        steps=steps,
        result={
            "agents": agents,
            "protocol": ctx.get("protocol", "broadcast"),
            "merge_strategy": ctx.get("merge_strategy", "consensus"),
        },
    )


def hierarchical_agents(ctx: dict[str, Any]) -> PatternResult:
    """Manager-worker hierarchy of agents."""
    depth = ctx.get("depth", 2)
    workers_per_level = ctx.get("workers_per_level", 3)
    steps = [
        PatternStep.new("manager_decompose", task=ctx.get("task"), sub_tasks=[]),
        *[PatternStep.new(f"worker_{i}", level=0) for i in range(workers_per_level)],
        PatternStep.new("manager_collect", results=[], pending_review=True),
        PatternStep.new("manager_revise", feedback=None),
        *([PatternStep.new(f"worker_level1_{i}", level=1) for i in range(workers_per_level)] if depth > 1 else []),
        PatternStep.new("manager_synthesize", final_output=None),
    ]
    return PatternResult(
        pattern_name="hierarchical_agents",
        status=StepStatus.PENDING,
        steps=steps,
        result={"depth": depth, "workers_per_level": workers_per_level},
    )


def debate(ctx: dict[str, Any]) -> PatternResult:
    """Multiple agents debate a topic and reach consensus."""
    debaters = ctx.get("debaters", ["proponent", "opponent", "moderator"])
    rounds = ctx.get("rounds", 3)
    steps = [
        PatternStep.new("position_statement", debaters=debaters, topic=ctx.get("topic")),
        *[PatternStep.new(f"round_{r}", round_number=r) for r in range(1, rounds + 1)],
        PatternStep.new("consensus_check", threshold=ctx.get("consensus_threshold", 0.7), reached=False),
        PatternStep.new("verdict", outcome=None, minority_report=None),
    ]
    return PatternResult(
        pattern_name="debate",
        status=StepStatus.PENDING,
        steps=steps,
        result={
            "debaters": debaters,
            "rounds": rounds,
            "consensus_threshold": ctx.get("consensus_threshold", 0.7),
        },
    )


def human_in_the_loop(ctx: dict[str, Any]) -> PatternResult:
    """Pause for human input at critical decision points."""
    decision_points = ctx.get("decision_points", ["verify_plan", "approve_execution", "confirm_delivery"])
    steps = [
        PatternStep.new("prepare_review", context=ctx.get("context"), options=ctx.get("options")),
        *[PatternStep.new(f"gate_{dp}", gate=dp, human_input=None) for dp in decision_points],
        PatternStep.new("apply_feedback", changes=None),
        PatternStep.new("resume", checkpoint=None),
    ]
    return PatternResult(
        pattern_name="human_in_the_loop",
        status=StepStatus.PENDING,
        steps=steps,
        result={
            "decision_points": decision_points,
            "timeout_seconds": ctx.get("timeout_seconds", 300),
            "fallback": ctx.get("fallback", "abort"),
        },
    )


def guardrails(ctx: dict[str, Any]) -> PatternResult:
    """Validate output against safety/quality constraints before returning."""
    rules = ctx.get("rules", ["no_pii", "no_harmful_content", "length_limit"])
    steps = [
        PatternStep.new("validate_input", rules=rules, input_data=ctx.get("input")),
        PatternStep.new("sanitize", transforms=[], redacted=None),
        PatternStep.new("proceed", guarded_input=None),
        PatternStep.new("validate_output", rules=rules, output_data=None),
        PatternStep.new("release", approved=False, violations=[]),
    ]
    return PatternResult(
        pattern_name="guardrails",
        status=StepStatus.PENDING,
        steps=steps,
        result={
            "rules": rules,
            "action_on_violation": ctx.get("action_on_violation", "block"),
        },
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


PATTERN_BUILDERS: dict[str, Any] = {
    "prompt_chaining": prompt_chaining,
    "routing": routing,
    "parallelization": parallelization,
    "planning": planning,
    "tool_use": tool_use,
    "knowledge_retrieval": knowledge_retrieval,
    "structured_output": structured_output,
    "memory_management": memory_management,
    "reflection": reflection,
    "self_correction": self_correction,
    "learning_adaptation": learning_adaptation,
    "multi_agent_collaboration": multi_agent_collaboration,
    "hierarchical_agents": hierarchical_agents,
    "debate": debate,
    "human_in_the_loop": human_in_the_loop,
    "guardrails": guardrails,
}


class PatternRegistry:
    """Register, list, get, and execute agent design patterns."""

    def __init__(self) -> None:
        self._builders: dict[str, Any] = dict(PATTERN_BUILDERS)

    def register(self, name: str, builder: Any) -> None:
        self._builders[name] = builder

    def list(self) -> list[str]:
        return list(self._builders)

    def get(self, name: str) -> Any:
        builder = self._builders.get(name)
        if builder is None:
            msg = f"Unknown pattern: {name!r}"
            raise KeyError(msg)
        return builder

    def execute(self, name: str, ctx: dict[str, Any]) -> PatternResult:
        builder = self.get(name)
        return builder(ctx)


__all__ = [
    "PatternStep",
    "PatternResult",
    "StepStatus",
    "PatternRegistry",
    "prompt_chaining",
    "routing",
    "parallelization",
    "planning",
    "tool_use",
    "knowledge_retrieval",
    "structured_output",
    "memory_management",
    "reflection",
    "self_correction",
    "learning_adaptation",
    "multi_agent_collaboration",
    "hierarchical_agents",
    "debate",
    "human_in_the_loop",
    "guardrails",
]
