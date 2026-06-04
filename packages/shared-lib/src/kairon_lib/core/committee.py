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
# Committee ≡ Module
# 内涵 ≝ {Committee}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Committee)}
# 功能 ⊢ {Init_Committee, Execute_Committee, Validate_Committee}
# =============================================================================

"""Dynamic committee system for B-OS project governance.

A Committee is a collection of Roles that can deliberate, vote, and drive
project execution from requirements to delivery.  This module is the ONE
canonical source of truth for all Committee-related Python code; the
conductor layer re-exports from here for backward compatibility.

Usage:
    # Create a standard product+execution committee
    committee = Committee.create_standard("My Project")

    # Or generate a custom committee for a specific domain
    committee = CommitteeFactory.for_domain("ml-ops", goal="Deploy ML pipeline")

    # Run a deliberation
    result = committee.deliberate("Should we use async or sync workers?")

    # Create from a built-in template (conductor-compatible API)
    committee = CommitteeFactory.from_template("product")
"""

import logging
import time

_log = logging.getLogger(__name__)
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class RoleType(StrEnum):
    # Executive roles
    CTO = "cto"  # Technical architecture, quality standards
    CPO = "cpo"  # Product vision, user stories, acceptance criteria
    CGO = "cgo"  # Growth, ecosystem, external integrations
    QA_LEAD = "qa_lead"  # Quality gates, test coverage, regression
    TECH_LEAD = "tech_lead"  # Day-to-day execution, workstream coordination
    # Specialist roles
    SECURITY = "security"  # Security review, RBAC, audit
    DATA_ARCHITECT = "data_architect"  # Data models, schemas, storage
    PLATFORM = "platform"  # Infrastructure, DevOps, deployment
    RESEARCHER = "researcher"  # Research, benchmarks, state-of-the-art
    DOMAIN_EXPERT = "domain_expert"  # Domain-specific expertise
    # Process roles
    FACILITATOR = "facilitator"  # Meeting facilitation, decision capture
    DEVIL_ADVOCATE = "devil_advocate"  # Challenge assumptions, red-team
    SYNTHESIZER = "synthesizer"  # Integrate perspectives, find consensus


class DecisionAuthority(StrEnum):
    """Voting/authority model for a committee role (conductor-compatible)."""

    UNILATERAL = "unilateral"  # single role decides
    CONSENSUS = "consensus"  # all roles must agree
    MAJORITY = "majority"  # >50% agree
    ADVISORY = "advisory"  # role advises, no veto


# ─────────────────────────────────────────────────────────────────────────────
# CommitteeRole  (merged nucleus rich model + conductor flat model)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CommitteeRole:
    """A role within a committee.

    Supports both the nucleus rich model (role_type / decision_weight /
    veto_domains) and the conductor flat model (archetype / authority /
    decision_domains / outputs_per_phase / agent_prompt_hint).
    """

    name: str  # e.g. "@Prime"
    # ── nucleus fields ──────────────────────────────────────────────────────
    role_type: RoleType | None = None
    decision_weight: float = 1.0  # voting weight
    veto_domains: list[str] = field(default_factory=list)
    # ── conductor fields ─────────────────────────────────────────────────────
    archetype: str = ""  # e.g. "CTO", "CPO", "QA"
    authority: DecisionAuthority = DecisionAuthority.ADVISORY
    decision_domains: list[str] = field(default_factory=list)
    outputs_per_phase: list[str] = field(default_factory=list)
    agent_prompt_hint: str = ""
    # ── shared fields ────────────────────────────────────────────────────────
    responsibilities: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    # ── conductor-compatible serialisation ───────────────────────────────────

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "responsibilities": self.responsibilities,
            "decision_domains": self.decision_domains,
            "authority": self.authority.value,
            "outputs_per_phase": self.outputs_per_phase,
        }

    # ── nucleus named constructors ────────────────────────────────────────────

    @classmethod
    def prime(cls) -> CommitteeRole:
        """@Prime — CTO / 架构总监"""
        return cls(
            name="@Prime",
            role_type=RoleType.CTO,
            archetype="CTO",
            responsibilities=[
                "技术架构最终裁决 (ADR审批)",
                "代码质量标准 (Ruff/分层/测试)",
                "技术债务优先级",
                "Agent可读性原则 (ADR-015)",
            ],
            decision_weight=1.5,
            veto_domains=["architecture", "security", "tech_debt"],
        )

    @classmethod
    def nyx(cls) -> CommitteeRole:
        """@Nyx — CPO / 产品总监"""
        return cls(
            name="@Nyx",
            role_type=RoleType.CPO,
            archetype="CPO",
            responsibilities=[
                "用户故事优先级排序",
                "验收标准确认",
                "产品完整性判断",
                "用户体验一致性",
            ],
            decision_weight=1.5,
            veto_domains=["feature_scope", "user_experience", "acceptance_criteria"],
        )

    @classmethod
    def omega(cls) -> CommitteeRole:
        """@Omega — CGO / 增长总监"""
        return cls(
            name="@Omega",
            role_type=RoleType.CGO,
            archetype="CGO",
            responsibilities=[
                "外部生态整合 (MCP/CrewAI/LangChain)",
                "第三方插件市场规划",
                "社区增长指标",
            ],
            decision_weight=1.0,
            veto_domains=["ecosystem", "integrations"],
        )

    @classmethod
    def guardian(cls) -> CommitteeRole:
        """@Guardian — QA / 质量守护者"""
        return cls(
            name="@Guardian",
            role_type=RoleType.QA_LEAD,
            archetype="QA",
            responsibilities=[
                "测试覆盖率标准 (>80%)",
                "Gate Review最终通过权",
                "回归测试策略",
                "性能基准",
            ],
            decision_weight=1.0,
            veto_domains=["quality_gates", "test_strategy"],
        )

    @classmethod
    def forge(cls) -> CommitteeRole:
        """@Forge — Tech Lead / 执行负责人"""
        return cls(
            name="@Forge",
            role_type=RoleType.TECH_LEAD,
            archetype="TechLead",
            responsibilities=[
                "Workstream任务分配",
                "并行执行协调",
                "技术方案落地",
                "日常站会主持",
            ],
            decision_weight=1.0,
            veto_domains=["execution_plan", "workstream_assignment"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# Deliberation support (nucleus)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DeliberationItem:
    question: str
    context: str = ""
    options: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class DeliberationResult:
    item: DeliberationItem
    perspectives: dict[str, str] = field(default_factory=dict)  # role_name → perspective
    decision: str = ""
    rationale: str = ""
    decided_at: float = field(default_factory=time.time)
    consensus_level: float = 1.0  # 0.0-1.0


@dataclass
class CommitteeCharter:
    name: str
    purpose: str
    domain: str
    roles: list[CommitteeRole] = field(default_factory=list)
    decision_protocol: str = "weighted_majority"  # or "consensus", "veto_override", "cto_final"
    created_at: float = field(default_factory=time.time)
    version: str = "1.0"


# ─────────────────────────────────────────────────────────────────────────────
# Committee  (merged nucleus charter model + conductor dataclass model)
# ─────────────────────────────────────────────────────────────────────────────


class Committee:
    """A Committee drives project governance from requirements to delivery.

    Supports two construction styles:

        # nucleus style (via CommitteeCharter)
        Committee(charter)

        # conductor style (flat kwargs)
        Committee(name="...", purpose="...", roles=[...])
    """

    def __init__(
        self,
        charter: CommitteeCharter | None = None,
        *,
        name: str = "",
        purpose: str = "",
        domain: str = "general",
        roles: list[CommitteeRole] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if charter is None:
            charter = CommitteeCharter(
                name=name,
                purpose=purpose,
                domain=domain,
                roles=list(roles or []),
            )
        self.charter = charter
        self.metadata: dict[str, object] = metadata or {}
        self._deliberations: list[DeliberationResult] = []
        self._committee_id = str(uuid.uuid4())[:8]
        self._decision_callbacks: list[Callable] = []  # A10: event callbacks

    # ── convenience properties (conductor-compatible) ─────────────────────────

    @property
    def name(self) -> str:
        return self.charter.name

    @property
    def purpose(self) -> str:
        return self.charter.purpose

    @property
    def roles(self) -> list[CommitteeRole]:
        return self.charter.roles

    # ── role lookup ───────────────────────────────────────────────────────────

    def get_role(self, identifier: RoleType | str) -> CommitteeRole | None:
        """Look up a role by RoleType (nucleus) or by name string (conductor)."""
        if isinstance(identifier, RoleType):
            return next((r for r in self.roles if r.role_type == identifier), None)
        return next((r for r in self.roles if r.name == identifier), None)

    def get_by_archetype(self, archetype: str) -> list[CommitteeRole]:
        """Return all roles matching the given archetype string (conductor)."""
        return [r for r in self.roles if r.archetype == archetype]

    def decision_makers(self) -> list[CommitteeRole]:
        """Roles with non-advisory authority (conductor)."""
        return [r for r in self.roles if r.authority != DecisionAuthority.ADVISORY]

    def role_names(self) -> list[str]:
        """Ordered list of role name strings (conductor)."""
        return [r.name for r in self.roles]

    def add_role(self, role: CommitteeRole) -> None:
        self.charter.roles.append(role)

    # ── deliberation (nucleus) ────────────────────────────────────────────────

    def deliberate(
        self,
        question: str,
        context: str = "",
        options: list[str] | None = None,
    ) -> DeliberationResult:
        """Record a deliberation decision."""
        item = DeliberationItem(question=question, context=context, options=options or [])
        result = DeliberationResult(item=item)
        self._deliberations.append(result)
        return result

    def record_decision(
        self,
        result: DeliberationResult,
        decision: str,
        rationale: str,
        perspectives: dict[str, str] | None = None,
    ) -> None:
        result.decision = decision
        result.rationale = rationale
        result.perspectives = perspectives or {}
        result.decided_at = time.time()
        # A10: Trigger downstream execution via registered callbacks
        if self._decision_callbacks:
            for cb in self._decision_callbacks:
                try:
                    cb(result)
                except (ValueError, TypeError, RuntimeError) as e:
                    _log.warning("[Committee] Decision callback failed: %s", e)

    def register_decision_callback(self, callback: Callable) -> None:
        """Register a callback to be invoked when a decision is recorded.

        Callback receives (result: DeliberationResult).
        """
        self._decision_callbacks.append(callback)

    def get_decision_log(self) -> list[dict[str, object]]:
        return [
            {
                "question": r.item.question,
                "decision": r.decision,
                "rationale": r.rationale,
                "decided_at": r.decided_at,
            }
            for r in self._deliberations
        ]

    # ── rendering ─────────────────────────────────────────────────────────────

    def summary(self) -> str:
        """Nucleus-style text summary."""
        lines = [
            f"Committee: {self.charter.name}",
            f"Purpose: {self.charter.purpose}",
            f"Domain: {self.charter.domain}",
            f"Roles ({len(self.roles)}): {', '.join(r.name for r in self.roles)}",
            f"Protocol: {self.charter.decision_protocol}",
            f"Deliberations: {len(self._deliberations)}",
        ]
        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Conductor-style Markdown rendering."""
        lines = [f"# {self.charter.name}", f"> {self.charter.purpose}", ""]
        for role in self.roles:
            lines += [
                f"## {role.name} — {role.archetype}",
                "",
                "**Responsibilities:**",
                *[f"- {r}" for r in role.responsibilities],
                "",
                f"**Authority:** {role.authority.value}",
                "",
                "**Decision Domains:**",
                *[f"- {d}" for d in role.decision_domains],
                "",
            ]
        return "\n".join(lines)

    # ── constructors ──────────────────────────────────────────────────────────

    @classmethod
    def create_standard(cls, project_name: str, purpose: str = "") -> Committee:
        """Create the standard B-OS Product+Execution Committee (5 roles)."""
        charter = CommitteeCharter(
            name=f"{project_name} Committee",
            purpose=purpose or f"Drive {project_name} from requirements to delivery",
            domain="software_development",
            roles=[
                CommitteeRole.prime(),
                CommitteeRole.nyx(),
                CommitteeRole.omega(),
                CommitteeRole.guardian(),
                CommitteeRole.forge(),
            ],
        )
        return cls(charter)


# ─────────────────────────────────────────────────────────────────────────────
# Built-in committee template functions (conductor-compatible module-level API)
# ─────────────────────────────────────────────────────────────────────────────


def make_product_committee() -> Committee:
    """Standard 3-role product committee for requirement review."""
    return Committee(
        name="Product Committee",
        purpose="Requirement review, feature scope, user story prioritization",
        roles=[
            CommitteeRole(
                name="@CPO",
                archetype="CPO",
                responsibilities=[
                    "Feature scope definition",
                    "User story prioritization",
                    "Acceptance criteria",
                ],
                decision_domains=["feature_scope", "user_stories", "ux_consistency"],
                authority=DecisionAuthority.UNILATERAL,
                outputs_per_phase=["Product spec", "Acceptance criteria per workstream"],
                agent_prompt_hint="You are the Chief Product Officer. Focus on user value, scope, and acceptance criteria.",
            ),
            CommitteeRole(
                name="@CGO",
                archetype="CGO",
                responsibilities=[
                    "Ecosystem integrations",
                    "Growth metrics",
                    "External compatibility",
                ],
                decision_domains=["ecosystem", "integrations", "external_api"],
                authority=DecisionAuthority.ADVISORY,
                outputs_per_phase=["Ecosystem requirements", "Integration spec"],
                agent_prompt_hint="You are the Chief Growth Officer. Focus on ecosystem fit and external integration.",
            ),
            CommitteeRole(
                name="@QA",
                archetype="QA",
                responsibilities=["Test strategy", "Coverage standards", "Quality gates"],
                decision_domains=["test_strategy", "quality_gates", "coverage"],
                authority=DecisionAuthority.UNILATERAL,
                outputs_per_phase=["Test plan per workstream", "Gate review criteria"],
                agent_prompt_hint="You are the QA Champion. Define test strategy and quality gates.",
            ),
        ],
    )


def make_execution_committee() -> Committee:
    """Standard 3-role execution committee for implementation oversight."""
    return Committee(
        name="Execution Committee",
        purpose="Workstream decomposition, technical architecture, delivery oversight",
        roles=[
            CommitteeRole(
                name="@CTO",
                archetype="CTO",
                responsibilities=[
                    "Technical architecture",
                    "ADR approvals",
                    "Tech debt prioritization",
                ],
                decision_domains=["architecture", "tech_stack", "code_quality"],
                authority=DecisionAuthority.UNILATERAL,
                outputs_per_phase=["Architecture review", "ADR updates"],
                agent_prompt_hint="You are the CTO. Focus on architecture, code quality, and technical correctness.",
            ),
            CommitteeRole(
                name="@Lead",
                archetype="TechLead",
                responsibilities=[
                    "Workstream decomposition",
                    "Agent task specs",
                    "Day-to-day delivery",
                ],
                decision_domains=["workstream_split", "task_specs", "agent_dispatch"],
                authority=DecisionAuthority.UNILATERAL,
                outputs_per_phase=["Workstream specs", "Execution plan"],
                agent_prompt_hint="You are the Lead Engineer. Break work into parallel workstreams and write detailed task specs.",
            ),
            CommitteeRole(
                name="@QA",
                archetype="QA",
                responsibilities=["Gate review execution", "Regression prevention"],
                decision_domains=["gate_pass", "test_baseline"],
                authority=DecisionAuthority.UNILATERAL,
                outputs_per_phase=["Gate review report", "Test delta"],
                agent_prompt_hint="You are the QA Guardian. Run gate reviews and ensure no regressions.",
            ),
        ],
    )


def make_advisory_committee(domain: str = "general") -> Committee:
    """Advisory committee for strategic review — pure advisory, no blockers."""
    return Committee(
        name=f"Advisory Committee ({domain})",
        purpose=f"Strategic advisors for {domain} decisions — advisory only",
        roles=[
            CommitteeRole(
                name="@Advisor-Security",
                archetype="SecurityAdvisor",
                responsibilities=["Security review", "Threat modeling"],
                decision_domains=["security"],
                authority=DecisionAuthority.ADVISORY,
                agent_prompt_hint="You are the Security Advisor. Identify security risks and suggest mitigations.",
            ),
            CommitteeRole(
                name="@Advisor-Perf",
                archetype="PerformanceAdvisor",
                responsibilities=["Performance review", "Scalability concerns"],
                decision_domains=["performance"],
                authority=DecisionAuthority.ADVISORY,
                agent_prompt_hint="You are the Performance Advisor. Identify bottlenecks and suggest optimizations.",
            ),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# CommitteeFactory  (merged nucleus domain presets + conductor templates)
# ─────────────────────────────────────────────────────────────────────────────


def get_role_registry() -> Any:
    """Placeholder: return an empty role registry.

    Replace with a real registry when the role system is connected.
    """
    return type("_EmptyRegistry", (), {
        "list_roles": staticmethod(lambda: []),
        "get_role": staticmethod(lambda _: None),
    })()


class CommitteeFactory:
    """Factory for generating domain-specific committees dynamically.

    Supports two creation patterns:
        # nucleus-style: domain-optimised committees
        CommitteeFactory.for_domain("security_review", goal="Audit auth layer")

        # conductor-style: named templates
        CommitteeFactory.from_template("product")
    """

    # ── nucleus domain presets ────────────────────────────────────────────────

    DOMAIN_PRESETS: dict[str, list[RoleType]] = {
        "software_development": [
            RoleType.CTO,
            RoleType.CPO,
            RoleType.CGO,
            RoleType.QA_LEAD,
            RoleType.TECH_LEAD,
        ],
        "ml_ops": [
            RoleType.CTO,
            RoleType.DATA_ARCHITECT,
            RoleType.PLATFORM,
            RoleType.QA_LEAD,
            RoleType.RESEARCHER,
        ],
        "security_review": [
            RoleType.CTO,
            RoleType.SECURITY,
            RoleType.QA_LEAD,
            RoleType.DEVIL_ADVOCATE,
            RoleType.FACILITATOR,
        ],
        "product_discovery": [
            RoleType.CPO,
            RoleType.RESEARCHER,
            RoleType.DOMAIN_EXPERT,
            RoleType.DEVIL_ADVOCATE,
            RoleType.SYNTHESIZER,
        ],
        "architecture_review": [
            RoleType.CTO,
            RoleType.PLATFORM,
            RoleType.SECURITY,
            RoleType.DOMAIN_EXPERT,
            RoleType.DEVIL_ADVOCATE,
        ],
        "ecosystem": [
            RoleType.CGO,
            RoleType.CTO,
            RoleType.CPO,
            RoleType.DOMAIN_EXPERT,
            RoleType.FACILITATOR,
        ],
    }

    ROLE_DEFAULTS: dict[RoleType, dict[str, object]] = {
        RoleType.SECURITY: {
            "name": "@Shield",
            "responsibilities": ["安全审查", "威胁建模", "渗透测试规划", "合规性"],
            "veto_domains": ["security", "auth", "data_access"],
        },
        RoleType.DATA_ARCHITECT: {
            "name": "@Schema",
            "responsibilities": ["数据建模", "存储方案", "迁移策略", "数据质量"],
            "veto_domains": ["data_model", "schema_changes"],
        },
        RoleType.PLATFORM: {
            "name": "@Infra",
            "responsibilities": ["基础设施", "CI/CD", "容器化", "可观测性"],
            "veto_domains": ["infrastructure", "deployment"],
        },
        RoleType.RESEARCHER: {
            "name": "@Scout",
            "responsibilities": ["技术调研", "基准测试", "竞品分析", "前沿跟踪"],
            "veto_domains": [],
        },
        RoleType.DOMAIN_EXPERT: {
            "name": "@Expert",
            "responsibilities": ["领域知识", "业务规则", "用例验证"],
            "veto_domains": ["domain_rules"],
        },
        RoleType.DEVIL_ADVOCATE: {
            "name": "@Challenger",
            "responsibilities": ["挑战假设", "红队攻击", "风险识别", "边界条件"],
            "veto_domains": [],
        },
        RoleType.SYNTHESIZER: {
            "name": "@Bridge",
            "responsibilities": ["整合视角", "寻找共识", "化解分歧", "形成决议"],
            "veto_domains": [],
        },
        RoleType.FACILITATOR: {
            "name": "@Anchor",
            "responsibilities": ["议程管理", "时间控制", "决策记录", "行动追踪"],
            "veto_domains": [],
        },
    }

    # ── conductor template registry ───────────────────────────────────────────

    TEMPLATES: dict[str, object] = {
        "product": make_product_committee,
        "execution": make_execution_committee,
        "advisory": make_advisory_committee,
    }

    # ── nucleus domain API ────────────────────────────────────────────────────

    @classmethod
    def for_domain(
        cls,
        domain: str,
        goal: str = "",
        custom_roles: list[RoleType] | None = None,
    ) -> Committee:
        """Generate a committee optimised for the given domain."""
        role_types = custom_roles or list(cls.DOMAIN_PRESETS.get(domain, cls.DOMAIN_PRESETS["software_development"]))

        roles: list[CommitteeRole] = []
        for rt in role_types:
            if rt == RoleType.CTO:
                roles.append(CommitteeRole.prime())
            elif rt == RoleType.CPO:
                roles.append(CommitteeRole.nyx())
            elif rt == RoleType.CGO:
                roles.append(CommitteeRole.omega())
            elif rt == RoleType.QA_LEAD:
                roles.append(CommitteeRole.guardian())
            elif rt == RoleType.TECH_LEAD:
                roles.append(CommitteeRole.forge())
            else:
                defaults = cls.ROLE_DEFAULTS.get(rt, {})
                roles.append(
                    CommitteeRole(
                        name=defaults.get("name", f"@{rt.value.title()}"),
                        role_type=rt,
                        responsibilities=list(defaults.get("responsibilities", [])),
                        veto_domains=list(defaults.get("veto_domains", [])),
                    )
                )

        charter = CommitteeCharter(
            name=f"{domain.replace('_', ' ').title()} Committee",
            purpose=goal or f"Drive {domain} initiatives to completion",
            domain=domain,
            roles=roles,
        )
        return Committee(charter)

    @classmethod
    def from_config(cls, config: dict[str, object]) -> Committee:
        """Build a committee from a dict config (e.g., loaded from YAML)."""
        role_types = [RoleType(rt) for rt in config.get("roles", ["cto", "cpo", "qa_lead", "tech_lead"])]
        return cls.for_domain(
            domain=config.get("domain", "software_development"),
            goal=config.get("goal", ""),
            custom_roles=role_types,
        )

    @classmethod
    def list_domains(cls) -> list[str]:
        return list(cls.DOMAIN_PRESETS.keys())

    # ── conductor template API ────────────────────────────────────────────────

    @classmethod
    def from_template(cls, template_name: str, **kwargs: Any) -> Committee:
        """Create a committee from a named template."""
        fn = cls.TEMPLATES.get(template_name)
        if not fn:
            raise ValueError(f"Unknown template: {template_name!r}. Available: {list(cls.TEMPLATES)}")
        return fn(**kwargs)

    @classmethod
    def register_template(cls, name: str, factory_fn: Any) -> None:
        """Register a custom template factory function."""
        cls.TEMPLATES[name] = factory_fn

    @classmethod
    def from_role_files(cls, role_dir: str | Path, name: str, purpose: str) -> Committee:
        """Build a committee from role YAML/MD files in a directory."""

        registry = get_role_registry()
        roles_data = registry.list_roles()
        roles: list[CommitteeRole] = []
        for role_name in roles_data:
            role_info = registry.get_role(role_name)
            if role_info:
                roles.append(
                    CommitteeRole(
                        name=f"@{role_info.get('name', role_name)}",
                        archetype=role_info.get("archetype", role_info.get("type", "Contributor")),
                        responsibilities=role_info.get("responsibilities", []),
                        decision_domains=role_info.get("domains", []),
                        authority=DecisionAuthority.ADVISORY,
                    )
                )
        return Committee(name=name, purpose=purpose, roles=roles)

    @classmethod
    def full_committee(cls) -> Committee:
        """Merge product + execution committees for joint sessions."""
        product = cls.from_template("product")
        execution = cls.from_template("execution")
        all_roles = product.roles + [r for r in execution.roles if r.name not in product.role_names()]
        return Committee(
            name="Full Project Committee",
            purpose="Joint product + execution oversight for major decisions",
            roles=all_roles,
        )

    # ── named template class methods (convenience) ────────────────────────────

    @classmethod
    def product_committee(cls) -> Committee:
        """Standard 3-role product committee."""
        return make_product_committee()

    @classmethod
    def execution_committee(cls) -> Committee:
        """Standard 3-role execution committee."""
        return make_execution_committee()

    @classmethod
    def advisory_committee(cls, domain: str = "general") -> Committee:
        """Advisory committee for strategic review."""
        return make_advisory_committee(domain)
