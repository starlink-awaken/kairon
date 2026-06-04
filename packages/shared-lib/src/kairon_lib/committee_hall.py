from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.3.0 (Weighted)
Owner: "@Builder"
Layer: L3
Summary: CommitteeHall — The sovereign deliberation hub for multi-agent governance and RFC management.
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Committee Hall ≡ Module
# 内涵 ≝ {Committee, Hall}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CommitteeHall)}
# 功能 ⊢ {Committee_Hall, Init_Committee, Validate_Hall}
# =============================================================================

import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from kairon_lib.committee import Committee, CommitteeRole, DecisionAuthority, RoleType

_log = logging.getLogger(__name__)
type AuditLogEntry = dict[str, str | float]
type RFCMetadata = dict[str, object]

# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class RFCStatus(StrEnum):
    DRAFT = "draft"
    DELIBERATING = "deliberating"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    CANCELLED = "cancelled"


class DecisionMode(StrEnum):
    CONSENSUS = "consensus"  # Everyone must approve
    VOTING = "voting"  # Weighted majority
    SIMULATION = "simulation"  # Compare sandbox results
    STATIC_RULE = "static_rule"  # Rule-based validation (docs/archive/root_cleanup_20260428/SOUL.md)


# ─────────────────────────────────────────────────────────────────────────────
# RFC Protocol
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RFC:
    """Request for Change (RFC) — The standard protocol for system evolution proposals."""

    title: str
    description: str
    proposer: str  # Role name
    domain: str = "general"
    impact_level: str = "low"  # low, medium, high, critical
    rfc_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: RFCStatus = RFCStatus.DRAFT
    created_at: float = field(default_factory=time.time)
    metadata: RFCMetadata = field(default_factory=dict)
    votes: dict[str, str] = field(default_factory=dict)  # role_name -> vote (approve/reject/abstain)
    perspectives: dict[str, str] = field(default_factory=dict)  # role_name -> comment


# ─────────────────────────────────────────────────────────────────────────────
# CommitteeHall
# ─────────────────────────────────────────────────────────────────────────────


class CommitteeHall:
    """The central hub for multi-agent deliberation and RFC management."""

    def __init__(self) -> None:
        self._committee = Committee(
            name="Sovereign Evolution Committee",
            purpose="Govern the self-evolution and structural integrity of SharedBrain B-OS",
            domain="governance",
        )
        self._init_sovereign_roles()
        self._rfcs: dict[str, RFC] = {}
        self._audit_logs: dict[str, list[AuditLogEntry]] = {}

    def _init_sovereign_roles(self) -> None:
        """Initialise the trinity of sovereign roles: @Builder, @Devil, @Sage."""
        self._committee.add_role(
            CommitteeRole(
                name="@Builder",
                archetype="CTO",
                role_type=RoleType.TECH_LEAD,
                responsibilities=["Engineering feasibility", "MVP definition"],
                decision_weight=1.0,
                authority=DecisionAuthority.CONSENSUS,
                agent_prompt_hint="You are @Builder.",
            )
        )
        self._committee.add_role(
            CommitteeRole(
                name="@Devil",
                archetype="QA",
                role_type=RoleType.DEVIL_ADVOCATE,
                responsibilities=["Risk assessment", "Edge cases"],
                decision_weight=1.0,
                authority=DecisionAuthority.CONSENSUS,
                agent_prompt_hint="You are @Devil.",
            )
        )
        self._committee.add_role(
            CommitteeRole(
                name="@Sage",
                archetype="Architect",
                role_type=RoleType.CTO,
                responsibilities=["Architectural alignment", "docs/archive/root_cleanup_20260428/SOUL.md consistency"],
                decision_weight=1.2,
                authority=DecisionAuthority.CONSENSUS,
                agent_prompt_hint="You are @Sage.",
            )
        )

    def get_role_names(self) -> list[str]:
        return [str(role_name) for role_name in self._committee.role_names()]

    def submit_rfc(self, rfc: RFC) -> str:
        self._rfcs[rfc.rfc_id] = rfc
        self._audit_logs[rfc.rfc_id] = []
        self._log_event(rfc.rfc_id, "RFC_SUBMITTED", f"RFC '{rfc.title}' submitted by {rfc.proposer}")
        return rfc.rfc_id

    def get_rfc(self, rfc_id: str) -> RFC | None:
        return self._rfcs.get(rfc_id)

    def start_deliberation(self, rfc_id: str) -> None:
        rfc = self.get_rfc(rfc_id)
        if rfc:
            rfc.status = RFCStatus.DELIBERATING
            self._log_event(rfc_id, "DELIBERATION_STARTED", "Deliberation hall opened.")

    async def request_remote_deliberation(self, rfc_id: str) -> None:
        rfc = self.get_rfc(rfc_id)
        if not rfc:
            return
        try:
            from nucleus.Z_Microkernel.organs.uri_router import Router

            fact = {
                "sub": f"rfc:{rfc_id}",
                "pred": "requires_deliberation",
                "obj": rfc.title,
                "metadata": asdict(rfc),
            }
            res = await Router.call("bos://gateway/p2p/broadcast", {"facts": [fact]})
            if res.get("status") == "success":
                self._log_event(rfc_id, "REMOTE_DELIBERATION_REQUESTED", "Broadcasted RFC to federation.")
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as e:
            _log.error(f"❌ [CommitteeHall] Failed to request remote deliberation: {e}")

    def cast_vote(self, rfc_id: str, role_name: str, vote: str, perspective: str) -> None:
        rfc = self.get_rfc(rfc_id)
        if not rfc:
            raise ValueError(f"RFC {rfc_id} not found")
        rfc.votes[role_name] = vote
        rfc.perspectives[role_name] = perspective
        self._log_event(rfc_id, "VOTE_CAST", f"Role {role_name} voted {vote}: {perspective}")

    async def evaluate_rfc_weighted(self, rfc_id: str) -> bool:
        """[RFC-024] 执行基于声誉值的分布式加权决策。"""
        rfc = self.get_rfc(rfc_id)
        if not rfc:
            return False

        try:
            from nucleus.Z_Microkernel.organs.uri_router import Router

            total_weight = 0.0
            score = 0.0

            for role, vote in rfc.votes.items():
                # 调用 D-Economy 获取声誉权重
                rep_res = await Router.call("bos://economy/reputation/get", {"agent_id": role})
                weight = rep_res.get("reputation", 1.0) if rep_res.get("status") == "success" else 1.0

                vote_val = 1.0 if vote == "approve" else -1.0
                score += weight * vote_val
                total_weight += weight

            approved = score > 0
            rfc.status = RFCStatus.APPROVED if approved else RFCStatus.REJECTED
            self._log_event(rfc_id, "WEIGHTED_EVALUATION", f"Result: {rfc.status} (Score: {score:.2f})")
            return approved
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as e:
            _log.error(f"❌ [CommitteeHall] Weighted evaluation failed: {e}")
            return False

    def evaluate_rfc(self, rfc_id: str, mode: DecisionMode = DecisionMode.CONSENSUS) -> bool:
        rfc = self.get_rfc(rfc_id)
        if not rfc:
            return False
        active_roles = self.get_role_names()
        votes = [rfc.votes.get(role) for role in active_roles if role in rfc.votes]
        if len(votes) < len(active_roles):
            return False
        approved = (
            all(v == "approve" for v in votes)
            if mode == DecisionMode.CONSENSUS
            else votes.count("approve") > len(votes) / 2
        )
        rfc.status = RFCStatus.APPROVED if approved else RFCStatus.REJECTED
        self._log_event(rfc_id, "EVALUATION", f"Result: {rfc.status} (Mode: {mode})")
        return approved

    def get_audit_logs(self, rfc_id: str) -> list[AuditLogEntry]:
        return self._audit_logs.get(rfc_id, [])

    def _log_event(self, rfc_id: str, event_type: str, message: str) -> None:
        if rfc_id in self._audit_logs:
            self._audit_logs[rfc_id].append({"timestamp": time.time(), "type": event_type, "message": message})

    async def deliberate_with_op2(
        self, rfc_id: str, problem: str = "", perspectives: list[str] | None = None
    ) -> dict[str, object]:
        """Integrate op2 multi-perspective analysis for RFC deliberation.

        Args:
            rfc_id: RFC identifier
            problem: Problem description for op2 analysis
            perspectives: Optional list of perspective IDs (defaults to op2 config)

        Returns:
            Dict with status and op2 analysis results mapped to roles
        """
        rfc = self.get_rfc(rfc_id)
        if not rfc:
            return {"status": "error", "message": f"RFC {rfc_id} not found"}

        try:
            # Use RFC description if problem not provided
            if not problem:
                problem = rfc.description

            # Call op2 via BOS-URI
            from nucleus.Z_Microkernel.organs.uri_router import Router

            op2_params = {
                "problem": problem,
                "perspectives": perspectives,
                "context": {"rfc_id": rfc_id, "domain": rfc.domain},
            }

            op2_result = await Router.call("bos://meta/op2", op2_params)

            if op2_result.get("status") != "success":
                _log.error(f"op2 call failed: {op2_result.get('message')}")
                return {"status": "error", "message": "op2 analysis failed"}

            # Extract op2 perspective analyses
            output_data = op2_result.get("output_data", {})
            perspective_analyses = output_data.get("perspective_analyses", {})

            # Map op2 perspectives to @Builder/@Devil/@Sage roles
            # Default mapping: user -> @Builder, operator -> @Devil, architect -> @Sage
            perspective_to_role_map = {
                "user": "@Builder",
                "developer": "@Builder",
                "operator": "@Devil",
                "architect": "@Sage",
                "digital_life": "@Sage",
            }

            # Store mapped perspectives in RFC.perspectives
            for perspective_id, analysis in perspective_analyses.items():
                role_name = perspective_to_role_map.get(perspective_id)
                if role_name:
                    rfc.perspectives[role_name] = analysis
                    self._log_event(
                        rfc_id,
                        "PERSPECTIVE_MAPPED",
                        f"op2 perspective '{perspective_id}' -> {role_name}",
                    )

            # Store consensus and synthesis in metadata
            rfc.metadata["op2_consensus"] = output_data.get("consensus_points", [])
            rfc.metadata["op2_conflicts"] = output_data.get("conflict_points", [])
            rfc.metadata["op2_synthesis"] = output_data.get("synthesis", "")

            self._log_event(
                rfc_id,
                "OP2_INTEGRATION",
                f"Integrated {len(perspective_analyses)} perspectives via op2",
            )

            return {
                "status": "success",
                "rfc_id": rfc_id,
                "perspectives_mapped": len(perspective_analyses),
                "op2_result": output_data,
            }

        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as e:
            _log.error(f"❌ [CommitteeHall] op2 integration failed: {e}")
            return {"status": "error", "message": str(e)}
