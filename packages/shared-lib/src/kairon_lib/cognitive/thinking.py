"""Thinking path library — structured deliberation paths with multi-mode reasoning.

Extracted from SharedBrain D_Governance (organs/governance/ai/thinking_paths.py).
Zero external dependencies — pure dataclasses, enum, and factory functions.

Provides:
- ThinkingMode enum: 17 reasoning modes (council, red_team, socratic, first_principles, ...)
- ThinkingStep dataclass: a single reasoning step with mode, prompt, and formatting
- ThinkingPath dataclass: an ordered sequence of steps for structured deliberation
- 7 factory functions: first_principles, adversarial_review, constraint_first, etc.
- ThinkingPathLibrary: registry with name-based and mode-based lookup + 7 nucleus-style static constructors
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

# ─────────────────────────────────────────────────────────────────
# Unified ThinkingMode enum
# ─────────────────────────────────────────────────────────────────


class ThinkingMode(StrEnum):
    """17 reasoning modes — path-level and step-level."""

    # Path-level modes
    COUNCIL = "council"
    RED_TEAM = "red_team"
    SOCRATIC = "socratic"
    DELPHI = "delphi"
    DESIGN_THINKING = "design_thinking"
    SYSTEMS_THINKING = "systems_thinking"
    # Step-level reasoning modes
    OBSERVE = "observe"
    FIRST_PRINCIPLES = "first_principles"
    ASSUMPTION_AUDIT = "assumption_audit"
    DEVILS_ADVOCATE = "devils_advocate"
    CONSTRAINT_MAPPING = "constraint_mapping"
    RISK_DECOMPOSITION = "risk_decomposition"
    DIVERGE = "diverge"
    CONVERGE = "converge"
    SYNTHESIS = "synthesis"
    VALIDATE = "validate"
    RETROSPECT = "retrospect"


# Backward-compatible alias
ReasoningMode = ThinkingMode


# ─────────────────────────────────────────────────────────────────
# ThinkingStep
# ─────────────────────────────────────────────────────────────────


@dataclass
class ThinkingStep:
    """A single reasoning step within a ThinkingPath.

    Field order preserves conductor-style positional usage:
      ThinkingStep(ReasoningMode.OBSERVE, "List all facts.")
    Optional fields support nucleus-style named usage:
      ThinkingStep(ThinkingMode.OBSERVE, "...", step_id="fp-1", perspective="architect")
    """

    mode: ThinkingMode
    prompt: str
    output_format: str = "free"  # free | bullet_list | scored_options | decision
    required: bool = True
    min_depth: int = 1
    step_id: str = ""
    perspective: str = ""

    def render_prompt(self, context: str = "") -> str:
        base = f"[{self.mode.value.upper()}] {self.prompt}"
        if context:
            base = f"Context: {context}\n\n{base}"
        if self.output_format == "bullet_list":
            base += "\n\nRespond with a bullet list."
        elif self.output_format == "scored_options":
            base += "\n\nRespond with each option scored 1-10."
        elif self.output_format == "decision":
            base += "\n\nConclude with a clear DECISION statement."
        return base


# ─────────────────────────────────────────────────────────────────
# ThinkingPath
# ─────────────────────────────────────────────────────────────────


@dataclass
class ThinkingPath:
    """An ordered sequence of reasoning steps for structured deliberation."""

    name: str
    description: str
    best_for: list[str] = field(default_factory=list)
    steps: list[ThinkingStep] = field(default_factory=list)
    mode: ThinkingMode | None = None
    avoid_when: list[str] = field(default_factory=list)
    typical_duration_min: int = 30

    # ── Conductor-style methods ────────────────────────────────────

    def step_names(self) -> list[str]:
        return [s.mode.value for s in self.steps]

    def required_steps(self) -> list[ThinkingStep]:
        return [s for s in self.steps if s.required]

    def render_full_prompt(self, context: str = "") -> str:
        sections = [f"# {self.name}", f"_{self.description}_", ""]
        for i, step in enumerate(self.steps, 1):
            sections.append(f"## Step {i}: {step.mode.value.replace('_', ' ').title()}")
            sections.append(step.render_prompt(context if i == 1 else ""))
            sections.append("")
        return "\n".join(sections)

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return {
            "name": self.name,
            "description": self.description,
            "best_for": self.best_for,
            "steps": [{"mode": s.mode.value, "prompt": s.prompt} for s in self.steps],
        }

    # ── Nucleus-style methods ──────────────────────────────────────

    def get_step(self, step_id: str) -> ThinkingStep | None:
        return next((s for s in self.steps if s.step_id == step_id), None)

    def summary(self) -> str:
        return f"{self.name}: {len(self.steps)} steps — {self.description[:60]}"


# ─────────────────────────────────────────────────────────────────
# Conductor-style factory functions
# ─────────────────────────────────────────────────────────────────


def first_principles_path() -> ThinkingPath:
    """Decompose problem to fundamentals before building up."""
    return ThinkingPath(
        name="First Principles",
        description="Break to fundamentals, challenge inherited assumptions, rebuild from scratch",
        best_for=["architectural decisions", "novel feature design", "performance problems"],
        mode=ThinkingMode.FIRST_PRINCIPLES,
        steps=[
            ThinkingStep(
                ThinkingMode.OBSERVE,
                "List all known facts about the problem. No interpretation.",
                "bullet_list",
            ),
            ThinkingStep(
                ThinkingMode.FIRST_PRINCIPLES,
                "What are the irreducible fundamentals? Strip away inherited conventions.",
                "bullet_list",
                min_depth=3,
            ),
            ThinkingStep(
                ThinkingMode.ASSUMPTION_AUDIT,
                "What are we assuming? Which assumptions are load-bearing vs. optional?",
                "bullet_list",
            ),
            ThinkingStep(
                ThinkingMode.SYNTHESIS,
                "Given only the fundamentals and challenged assumptions, what solution emerges?",
                "decision",
            ),
        ],
    )


def adversarial_review_path() -> ThinkingPath:
    """Red-team a proposal before committing."""
    return ThinkingPath(
        name="Adversarial Review",
        description="Play devil's advocate to stress-test assumptions and find failure modes",
        best_for=["validating plans", "security review", "pre-mortem analysis"],
        mode=ThinkingMode.RED_TEAM,
        steps=[
            ThinkingStep(ThinkingMode.OBSERVE, "Summarize the proposal being reviewed.", "free"),
            ThinkingStep(
                ThinkingMode.ASSUMPTION_AUDIT,
                "List every assumption the proposal depends on.",
                "bullet_list",
            ),
            ThinkingStep(
                ThinkingMode.DEVILS_ADVOCATE,
                "Argue strongly that this will FAIL. What are the three most likely failure modes?",
                "bullet_list",
                min_depth=3,
            ),
            ThinkingStep(
                ThinkingMode.RISK_DECOMPOSITION,
                "For each failure mode: probability (H/M/L), impact (H/M/L), mitigation.",
                "bullet_list",
            ),
            ThinkingStep(
                ThinkingMode.SYNTHESIS,
                "Given the risks, should we proceed? If yes, what safeguards?",
                "decision",
            ),
        ],
    )


def constraint_first_path() -> ThinkingPath:
    """Map hard constraints before generating solutions."""
    return ThinkingPath(
        name="Constraint First",
        description="Map non-negotiable limits before exploring the solution space",
        best_for=["technical planning", "capacity planning", "compliance-heavy decisions"],
        mode=ThinkingMode.CONSTRAINT_MAPPING,
        steps=[
            ThinkingStep(
                ThinkingMode.CONSTRAINT_MAPPING,
                "List ALL hard constraints (immovable). Then soft constraints (negotiable).",
                "bullet_list",
                min_depth=2,
            ),
            ThinkingStep(
                ThinkingMode.OBSERVE,
                "Within the constrained space, what facts define the problem?",
                "bullet_list",
            ),
            ThinkingStep(
                ThinkingMode.DIVERGE,
                "Generate 3+ approaches that respect ALL hard constraints.",
                "scored_options",
            ),
            ThinkingStep(
                ThinkingMode.CONVERGE,
                "Which approach best satisfies soft constraints too?",
                "decision",
            ),
        ],
    )


def multi_perspective_path() -> ThinkingPath:
    """Gather diverse viewpoints before converging."""
    return ThinkingPath(
        name="Multi-Perspective",
        description="Collect opposing views from different stakeholders before synthesizing",
        best_for=["committee decisions", "trade-off analysis", "cross-team alignment"],
        mode=ThinkingMode.COUNCIL,
        steps=[
            ThinkingStep(
                ThinkingMode.OBSERVE,
                "Frame the decision: what exactly are we choosing between?",
                "free",
            ),
            ThinkingStep(
                ThinkingMode.DIVERGE,
                "From each stakeholder angle (user/engineer/ops/business), what would they want?",
                "bullet_list",
            ),
            ThinkingStep(
                ThinkingMode.DEVILS_ADVOCATE,
                "What would a critic of the leading option say?",
                "bullet_list",
            ),
            ThinkingStep(
                ThinkingMode.SYNTHESIS,
                "Integrate all perspectives. What solution satisfies the most stakeholders?",
                "decision",
            ),
        ],
    )


def scientific_validation_path() -> ThinkingPath:
    """Form hypothesis, design experiment, validate empirically."""
    return ThinkingPath(
        name="Scientific Validation",
        description="Treat the decision as a hypothesis — define falsifiable tests",
        best_for=["A/B decisions", "performance claims", "architecture proposals"],
        mode=ThinkingMode.DELPHI,
        steps=[
            ThinkingStep(
                ThinkingMode.FIRST_PRINCIPLES,
                "State the hypothesis precisely and measurably.",
                "free",
            ),
            ThinkingStep(
                ThinkingMode.ASSUMPTION_AUDIT,
                "What must be true for the hypothesis to hold? List preconditions.",
                "bullet_list",
            ),
            ThinkingStep(
                ThinkingMode.VALIDATE,
                "Design a minimal experiment that could falsify the hypothesis. What metrics?",
                "free",
            ),
            ThinkingStep(
                ThinkingMode.RISK_DECOMPOSITION,
                "What are the costs if the hypothesis is wrong?",
                "bullet_list",
            ),
            ThinkingStep(
                ThinkingMode.SYNTHESIS,
                "Given the evidence and costs, proceed or reject?",
                "decision",
            ),
        ],
    )


def retrospective_extraction_path() -> ThinkingPath:
    """Extract durable principles from a completed phase."""
    return ThinkingPath(
        name="Retrospective Extraction",
        description="Distill principles and patterns from what just happened",
        best_for=["phase retrospectives", "incident reviews", "learning sessions"],
        mode=ThinkingMode.RETROSPECT,
        steps=[
            ThinkingStep(
                ThinkingMode.OBSERVE,
                "What happened? Describe the phase/incident objectively.",
                "free",
            ),
            ThinkingStep(
                ThinkingMode.RETROSPECT,
                "What went well? What went poorly? What was surprising?",
                "bullet_list",
            ),
            ThinkingStep(
                ThinkingMode.FIRST_PRINCIPLES,
                "Beneath the surface events, what underlying patterns drove outcomes?",
                "bullet_list",
                min_depth=2,
            ),
            ThinkingStep(
                ThinkingMode.SYNTHESIS,
                "State 3-5 durable principles that should guide future behavior.",
                "bullet_list",
                min_depth=3,
            ),
        ],
    )


def creative_divergence_path() -> ThinkingPath:
    """Maximum creative exploration before any evaluation."""
    return ThinkingPath(
        name="Creative Divergence",
        description="Defer judgment — generate the widest possible solution space first",
        best_for=["brainstorming", "feature ideation", "novel problem solving"],
        mode=ThinkingMode.DIVERGE,
        steps=[
            ThinkingStep(
                ThinkingMode.OBSERVE,
                "Describe the opportunity or problem without constraints.",
                "free",
            ),
            ThinkingStep(
                ThinkingMode.DIVERGE,
                "Generate 10+ ideas — wild, impractical, and conventional all welcome.",
                "bullet_list",
                min_depth=8,
            ),
            ThinkingStep(
                ThinkingMode.DIVERGE,
                "Now generate 5 more ideas by combining pairs from above.",
                "bullet_list",
                min_depth=5,
            ),
            ThinkingStep(
                ThinkingMode.CONVERGE,
                "Score top 5 ideas by feasibility (1-10) and novelty (1-10).",
                "scored_options",
            ),
            ThinkingStep(ThinkingMode.SYNTHESIS, "Recommend the 2 best ideas to explore further.", "decision"),
        ],
    )


# ─────────────────────────────────────────────────────────────────
# ThinkingPathLibrary — unified registry + static methods
# ─────────────────────────────────────────────────────────────────


_CONDUCTOR_FACTORIES: list[Callable[[], ThinkingPath]] = [
    first_principles_path,
    adversarial_review_path,
    constraint_first_path,
    multi_perspective_path,
    scientific_validation_path,
    retrospective_extraction_path,
    creative_divergence_path,
]


class ThinkingPathLibrary:
    """Registry and factory for all thinking paths.

    Class-level _PATHS dict stores conductor-named paths (SSOT for name-based access).
    Static methods provide nucleus-style direct construction.
    """

    _PATHS: dict[str, ThinkingPath] = {}
    _initialized: bool = False

    # ── Conductor-style registry interface ────────────────────────

    @classmethod
    def _ensure_init(cls) -> None:
        if not cls._initialized:
            for fn in _CONDUCTOR_FACTORIES:
                path = fn()
                cls._PATHS[path.name] = path
            cls._initialized = True

    @classmethod
    def get(cls, name: str) -> ThinkingPath:
        cls._ensure_init()
        if name not in cls._PATHS:
            raise KeyError(f"ThinkingPath {name!r} not found. Available: {list(cls._PATHS)}")
        return cls._PATHS[name]

    @classmethod
    def all_paths(cls) -> list[ThinkingPath]:
        cls._ensure_init()
        return list(cls._PATHS.values())

    @classmethod
    def names(cls) -> list[str]:
        cls._ensure_init()
        return list(cls._PATHS.keys())

    @classmethod
    def register(cls, path: ThinkingPath) -> None:
        cls._PATHS[path.name] = path

    @classmethod
    def for_context(cls, best_for_keyword: str) -> list[ThinkingPath]:
        """Return paths whose best_for list contains the keyword."""
        cls._ensure_init()
        kw = best_for_keyword.lower()
        return [p for p in cls._PATHS.values() if any(kw in b.lower() for b in p.best_for)]

    # ── Nucleus-style static constructors ─────────────────────────

    @staticmethod
    def first_principles() -> ThinkingPath:
        return ThinkingPath(
            mode=ThinkingMode.FIRST_PRINCIPLES,
            name="First Principles Analysis",
            description="Break assumptions, return to fundamentals, rebuild from scratch",
            steps=[
                ThinkingStep(
                    ThinkingMode.OBSERVE, "What is the current problem? State it in one sentence.", step_id="fp-1"
                ),
                ThinkingStep(
                    ThinkingMode.ASSUMPTION_AUDIT,
                    "What assumptions are we making? List all (especially the 'obvious' ones).",
                    step_id="fp-2",
                ),
                ThinkingStep(
                    ThinkingMode.FIRST_PRINCIPLES,
                    "Decompose to fundamental facts. Which assumptions are verifiable?",
                    step_id="fp-3",
                ),
                ThinkingStep(
                    ThinkingMode.DIVERGE,
                    "From these fundamentals, what solution paths exist?",
                    step_id="fp-4",
                ),
                ThinkingStep(
                    ThinkingMode.CONVERGE, "Evaluate each path's feasibility; select the best.", step_id="fp-5"
                ),
            ],
            best_for=["disruptive innovation", "breaking fixed mindsets", "cost optimization", "architecture redesign"],
            avoid_when=["time pressure", "established solutions exist", "low-risk daily decisions"],
            typical_duration_min=45,
        )

    @staticmethod
    def council() -> ThinkingPath:
        return ThinkingPath(
            mode=ThinkingMode.COUNCIL,
            name="Council of Perspectives",
            description="Multi-role perspective debate covering all sides of a problem",
            steps=[
                ThinkingStep(
                    ThinkingMode.OBSERVE,
                    "Tech perspective: what is the technical feasibility, complexity, and risk?",
                    step_id="c-1",
                    perspective="architect",
                ),
                ThinkingStep(
                    ThinkingMode.DIVERGE,
                    "Product perspective: does this solve a real user pain point? What is the MVP?",
                    step_id="c-2",
                    perspective="product_manager",
                ),
                ThinkingStep(
                    ThinkingMode.OBSERVE,
                    "User perspective: as the end user, what is my experience?",
                    step_id="c-3",
                    perspective="user",
                ),
                ThinkingStep(
                    ThinkingMode.RISK_DECOMPOSITION,
                    "Risk perspective: what is the worst case? How do we mitigate?",
                    step_id="c-4",
                    perspective="risk_manager",
                ),
                ThinkingStep(
                    ThinkingMode.DIVERGE,
                    "Innovation perspective: is there a better approach we have not considered?",
                    step_id="c-5",
                    perspective="innovator",
                ),
                ThinkingStep(
                    ThinkingMode.SYNTHESIS,
                    "Synthesis: integrate all perspectives into an optimal decision.",
                    step_id="c-6",
                    perspective="synthesizer",
                ),
            ],
            best_for=[
                "major architecture decisions",
                "feature prioritization",
                "tech selection",
                "cross-team decisions",
            ],
            avoid_when=["urgent P0 incidents", "clear answer already exists", "pure implementation tasks"],
            typical_duration_min=60,
        )

    @staticmethod
    def red_team() -> ThinkingPath:
        return ThinkingPath(
            mode=ThinkingMode.RED_TEAM,
            name="Red Team Challenge",
            description="Attack all assumptions and proposals from an adversarial perspective",
            steps=[
                ThinkingStep(ThinkingMode.OBSERVE, "List our core assumptions and proposals.", step_id="rt-1"),
                ThinkingStep(
                    ThinkingMode.DEVILS_ADVOCATE,
                    "As a 'malicious attacker', how would you compromise this system? List attack vectors.",
                    step_id="rt-2",
                    perspective="attacker",
                ),
                ThinkingStep(
                    ThinkingMode.DEVILS_ADVOCATE,
                    "As a 'pessimistic user', where is this most likely to disappoint users?",
                    step_id="rt-3",
                    perspective="pessimist",
                ),
                ThinkingStep(
                    ThinkingMode.ASSUMPTION_AUDIT,
                    "As a 'competitor analyst', how would competitors respond? What is our moat?",
                    step_id="rt-4",
                    perspective="competitor",
                ),
                ThinkingStep(
                    ThinkingMode.RISK_DECOMPOSITION,
                    "List all challenged assumptions; assess which require plan changes.",
                    step_id="rt-5",
                ),
                ThinkingStep(ThinkingMode.SYNTHESIS, "Update the plan, strengthen weak points.", step_id="rt-6"),
            ],
            best_for=[
                "security design review",
                "security review",
                "risk assessment",
                "pre-release",
                "final architecture",
            ],
            avoid_when=["early brainstorming", "low team confidence"],
            typical_duration_min=40,
        )

    @staticmethod
    def socratic() -> ThinkingPath:
        return ThinkingPath(
            mode=ThinkingMode.SOCRATIC,
            name="Socratic Method",
            description="Deep-dive through successive questioning; reject surface-level answers",
            steps=[
                ThinkingStep(ThinkingMode.OBSERVE, "What is the core problem?", step_id="s-1"),
                ThinkingStep(
                    ThinkingMode.FIRST_PRINCIPLES,
                    "Why is this a problem? (Ask 'why' at least 3 times)",
                    step_id="s-2",
                ),
                ThinkingStep(
                    ThinkingMode.ASSUMPTION_AUDIT,
                    "Do we truly understand the problem? Provide a counterexample.",
                    step_id="s-3",
                ),
                ThinkingStep(ThinkingMode.DEVILS_ADVOCATE, "What if our assumptions are wrong?", step_id="s-4"),
                ThinkingStep(ThinkingMode.VALIDATE, "What evidence would change our conclusion?", step_id="s-5"),
                ThinkingStep(ThinkingMode.SYNTHESIS, "What is the conclusion? Confidence level?", step_id="s-6"),
            ],
            best_for=["root cause analysis", "requirements clarification", "deep understanding", "incident postmortem"],
            avoid_when=["known-answer implementations", "extreme time pressure"],
            typical_duration_min=30,
        )

    @staticmethod
    def delphi() -> ThinkingPath:
        return ThinkingPath(
            mode=ThinkingMode.DELPHI,
            name="Delphi Consensus",
            description="Multi-round iterative expert consensus converging to optimal answer",
            steps=[
                ThinkingStep(
                    ThinkingMode.DIVERGE,
                    "Round 1: each role independently gives solutions/estimates, no cross-influence.",
                    "list",
                    step_id="d-1",
                ),
                ThinkingStep(
                    ThinkingMode.OBSERVE, "Aggregate round 1 results; identify divergence points.", step_id="d-2"
                ),
                ThinkingStep(
                    ThinkingMode.DEVILS_ADVOCATE,
                    "Roles with greatest divergence explain their reasoning.",
                    step_id="d-3",
                ),
                ThinkingStep(
                    ThinkingMode.CONVERGE,
                    "Round 2: re-evaluate based on others' reasoning; revise or hold.",
                    "bullet_list",
                    step_id="d-4",
                ),
                ThinkingStep(
                    ThinkingMode.VALIDATE, "Aggregate round 2; check convergence (variance < 20%).", step_id="d-5"
                ),
                ThinkingStep(
                    ThinkingMode.SYNTHESIS,
                    "Form final consensus decision; record minority opinions.",
                    "decision",
                    step_id="d-6",
                ),
            ],
            best_for=["estimation calibration", "tech selection voting", "priority ranking", "long-range planning"],
            avoid_when=["urgent decisions", "only one expert available"],
            typical_duration_min=50,
        )

    @staticmethod
    def synthesis() -> ThinkingPath:
        return ThinkingPath(
            mode=ThinkingMode.SYNTHESIS,
            name="Synthesis Integration",
            description="Integrate multiple perspectives and proposals into unified insight",
            steps=[
                ThinkingStep(
                    ThinkingMode.OBSERVE, "Collect all existing analyses, proposals, and perspectives.", step_id="sy-1"
                ),
                ThinkingStep(ThinkingMode.OBSERVE, "Identify common themes and patterns.", step_id="sy-2"),
                ThinkingStep(
                    ThinkingMode.CONSTRAINT_MAPPING, "Find contradictions and tension points.", step_id="sy-3"
                ),
                ThinkingStep(
                    ThinkingMode.SYNTHESIS,
                    "Propose a unifying framework that integrates all perspectives.",
                    step_id="sy-4",
                ),
                ThinkingStep(
                    ThinkingMode.VALIDATE,
                    "Validate: is this framework better than any single perspective?",
                    step_id="sy-5",
                ),
                ThinkingStep(
                    ThinkingMode.SYNTHESIS,
                    "Output unified insight and action recommendations.",
                    "decision",
                    step_id="sy-6",
                ),
            ],
            best_for=["cross-phase summaries", "strategic planning", "knowledge capture", "complex decision closure"],
            avoid_when=["insufficient information", "irreconcilable conflicting perspectives"],
            typical_duration_min=35,
        )

    @staticmethod
    def systems_thinking() -> ThinkingPath:
        return ThinkingPath(
            mode=ThinkingMode.SYSTEMS_THINKING,
            name="Systems Thinking",
            description="Identify feedback loops, emergent behavior, and leverage points",
            steps=[
                ThinkingStep(
                    ThinkingMode.CONSTRAINT_MAPPING,
                    "Draw system boundaries: what is inside the system? What is outside?",
                    step_id="st-1",
                ),
                ThinkingStep(
                    ThinkingMode.OBSERVE, "Identify major components and their relationships.", step_id="st-2"
                ),
                ThinkingStep(
                    ThinkingMode.FIRST_PRINCIPLES,
                    "Find reinforcing loops (amplify) and balancing loops (stabilize).",
                    step_id="st-3",
                ),
                ThinkingStep(
                    ThinkingMode.RISK_DECOMPOSITION,
                    "Identify delays: which effects appear only after a lag?",
                    step_id="st-4",
                ),
                ThinkingStep(
                    ThinkingMode.DIVERGE,
                    "Find leverage points: where can a small change produce a large impact?",
                    step_id="st-5",
                ),
                ThinkingStep(
                    ThinkingMode.SYNTHESIS, "Predict system behavior; propose intervention strategy.", step_id="st-6"
                ),
            ],
            best_for=[
                "complex system design",
                "emergent problem analysis",
                "long-term strategy",
                "organizational design",
            ],
            avoid_when=["simple linear problems", "local optimization only"],
            typical_duration_min=60,
        )

    # ── Recommend / from_mode ─────────────────────────────────────

    @classmethod
    def recommend(cls, problem_type: str) -> ThinkingPath:
        dispatch = {
            "architecture": cls.council,
            "root_cause": cls.socratic,
            "security": cls.red_team,
            "innovation": cls.first_principles,
            "consensus": cls.delphi,
            "summary": cls.synthesis,
            "complex_system": cls.systems_thinking,
        }
        factory = dispatch.get(problem_type, cls.council)
        return factory()

    @classmethod
    def from_mode(cls, mode: str) -> ThinkingPath | None:
        dispatch = {
            "first_principles": cls.first_principles,
            "council": cls.council,
            "red_team": cls.red_team,
            "socratic": cls.socratic,
            "delphi": cls.delphi,
            "synthesis": cls.synthesis,
            "systems_thinking": cls.systems_thinking,
        }
        factory = dispatch.get(mode)
        return factory() if factory else None

    @classmethod
    def from_name(cls, name: str) -> ThinkingPath | None:
        """Alias for get() that returns None instead of raising."""
        try:
            return cls.get(name)
        except KeyError:
            return None


__all__ = [
    "ReasoningMode",
    "ThinkingMode",
    "ThinkingPath",
    "ThinkingPathLibrary",
    "ThinkingStep",
    # factory functions
    "adversarial_review_path",
    "constraint_first_path",
    "creative_divergence_path",
    "first_principles_path",
    "multi_perspective_path",
    "retrospective_extraction_path",
    "scientific_validation_path",
]
