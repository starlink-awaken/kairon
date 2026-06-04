from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Governance Observability Bridge ≡ Module
# 内涵 ≝ {Governance, Observability, Bridge}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, GovernanceObservabilityBridge)}
# 功能 ⊢ {Governance_Observability, Observability_Bridge, Bridge_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

"""
Bridge validation failures into governance, audit, and event observability.

This module intentionally depends only on D-Governance local primitives plus
injected callbacks for audit logging and event publishing. That keeps the
bridge aligned with the B-OS layering rules while still letting integration
tests wire it to real D-Immunity and D-Execution surfaces.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from kairon_lib.organs.approval_router import ApprovalRouter
from kairon_lib.organs.audit.audit_query import (
    SEVERITY_INFO,
    SEVERITY_WARN,
    AuditQueryEngine,
)
from kairon_lib.organs.execution.workflow_engine import WorkflowEngine, WorkflowPhase
from kairon_lib.organs.governance.collaboration.collab_protocol import (
    ChecklistItem,
    PhaseGateReview,
    ProtocolStatus,
)
from kairon_lib.organs.governance.consensus.committee import Committee
from kairon_lib.organs.policy_registry import PolicyRegistry


class AuditLogger(Protocol):
    def log_action(
        self,
        actor: str,
        action: str,
        resource: str,
        result: str,
        details: dict[str, object] | None = None,
    ) -> None: ...


EventPublisher = callable


@dataclass
class GovernanceEscalationRecord:
    model_id: str
    decision: str
    question: str
    event_topic: str
    event_payload: dict[str, object]
    gate_review: PhaseGateReview
    workflow: WorkflowEngine
    audit_logged: bool


@dataclass
class EvaluationGateDecision:
    evaluation_id: str
    decision: str
    risk_level: str
    gate_passed: bool
    approval_required: bool
    policy_id: str
    policy_allowed: bool
    approval_request_id: str = ""
    event_topic: str = ""
    event_payload: dict[str, object] | None = None


class GovernanceObservabilityBridge:
    """Create a minimal governance escalation trail for failed validations."""

    EVENT_TOPIC = "governance.validation_failure_escalated"
    EVENT_TOPIC_EVALUATION = "governance.evaluation_gate_decided"

    def __init__(
        self,
        committee: Committee | None = None,
        *,
        audit_logger: AuditLogger | None = None,
        event_publisher: Any | None = None,
        policy_registry: PolicyRegistry | None = None,
        approval_router: ApprovalRouter | None = None,
        audit_query: AuditQueryEngine | None = None,
    ) -> None:
        self._committee = committee or Committee.create_standard("Governance Observability")
        self._audit_logger = audit_logger
        self._event_publisher = event_publisher
        self._policy_registry = policy_registry
        self._approval_router = approval_router
        self._audit_query = audit_query

    def escalate_validation_failure(
        self,
        validation_result: Any,
        *,
        actor: str,
        reviewer: str = "@Prime",
        trace_id: str = "",
        remediation: dict[str, object] | None = None,
        reverified_result: Any | None = None,
    ) -> GovernanceEscalationRecord:
        model_id = str(getattr(validation_result, "model_id", "unknown-model"))
        issues = list(getattr(validation_result, "issues", []))
        status = self._enum_value(getattr(validation_result, "status", "unknown"))
        question = f"Should we remediate validation failure for {model_id}?"
        context = f"status={status}; issues={issues or ['unspecified failure']}"

        deliberation = self._committee.deliberate(
            question,
            context=context,
            options=["remediate", "ignore"],
        )
        decision = "remediate" if not bool(getattr(validation_result, "is_valid", False)) else "accept"
        self._committee.record_decision(
            deliberation,
            decision=decision,
            rationale="Validation failures should become visible governance items with audit evidence.",
        )

        gate_review = PhaseGateReview(
            phase_number=1,
            checklist=[
                ChecklistItem(
                    "Validation failure confirmed",
                    required=True,
                    passed=not bool(getattr(validation_result, "is_valid", False)),
                ),
                ChecklistItem("Governance decision recorded", required=True, passed=True),
                ChecklistItem(
                    "Re-verification passed",
                    required=True,
                    passed=self._reverified_passed(reverified_result),
                ),
            ],
            status=self._gate_status(reverified_result),
            reviewer=reviewer,
        )

        workflow = WorkflowEngine("Governance Observability Bridge")
        with workflow.phase(WorkflowPhase.OBSERVE) as ctx:
            ctx.record("validation_failure", self._result_to_dict(validation_result))
            ctx.record("trace_id", trace_id)
        with workflow.phase(WorkflowPhase.THINK) as ctx:
            ctx.record("question", question)
            ctx.record("decision", decision)
        with workflow.phase(WorkflowPhase.PLAN) as ctx:
            ctx.add_workstream("ws-governance-escalation", "Escalate validation failure", owner=reviewer)
        with workflow.phase(WorkflowPhase.EXECUTE) as ctx:
            ctx.record("remediation", remediation or {"required": decision == "remediate"})
        with workflow.phase(WorkflowPhase.VERIFY) as ctx:
            ctx.record("gate_review_passed", gate_review.is_passing())
            if reverified_result is not None:
                ctx.record("reverified_result", self._result_to_dict(reverified_result))
        with workflow.phase(WorkflowPhase.LEARN) as ctx:
            ctx.record("principle", "validation failures must produce a governance-visible audit trail")

        event_payload = {
            "trace_id": trace_id,
            "model_id": model_id,
            "validation_status": status,
            "issues": issues,
            "decision": decision,
            "gate_review_status": gate_review.status.value,
            "gate_review_passed": gate_review.is_passing(),
            "remediation_attached": remediation is not None,
        }

        audit_logged = False
        if self._audit_logger is not None:
            self._audit_logger.log_action(
                actor,
                "governance.validation_escalation",
                model_id,
                decision.upper(),
                details=event_payload,
            )
            audit_logged = True

        if self._event_publisher is not None:
            self._event_publisher(self.EVENT_TOPIC, event_payload)

        return GovernanceEscalationRecord(
            model_id=model_id,
            decision=decision,
            question=question,
            event_topic=self.EVENT_TOPIC,
            event_payload=event_payload,
            gate_review=gate_review,
            workflow=workflow,
            audit_logged=audit_logged,
        )

    @staticmethod
    def _enum_value(value: Any) -> str:
        return str(getattr(value, "value", value))

    @staticmethod
    def _result_to_dict(result: Any) -> dict[str, object]:
        to_dict = getattr(result, "to_dict", None)
        if callable(to_dict):
            return dict(to_dict())
        return {
            "is_valid": bool(getattr(result, "is_valid", False)),
            "issues": list(getattr(result, "issues", [])),
            "status": str(getattr(getattr(result, "status", None), "value", getattr(result, "status", ""))),
            "model_id": str(getattr(result, "model_id", "")),
        }

    @staticmethod
    def _reverified_passed(reverified_result: Any | None) -> bool | None:
        if reverified_result is None:
            return None
        return bool(getattr(reverified_result, "is_valid", False))

    @staticmethod
    def _gate_status(reverified_result: Any | None) -> ProtocolStatus:
        if reverified_result is None:
            return ProtocolStatus.IN_PROGRESS
        if bool(getattr(reverified_result, "is_valid", False)):
            return ProtocolStatus.PASSED
        return ProtocolStatus.FAILED

    @staticmethod
    def _risk_level_from_score(risk_score: float) -> str:
        if risk_score >= 85.0:
            return "low"
        if risk_score >= 70.0:
            return "medium"
        if risk_score >= 50.0:
            return "high"
        return "critical"

    def evaluate_execution_gate(
        self,
        *,
        evaluation_id: str,
        actor: str,
        quality_score: float,
        slo_score: float,
        risk_score: float,
        quality_floor: float = 70.0,
        slo_floor: float = 70.0,
        risk_floor: float = 60.0,
        action: str = "release",
        committee_id: str = "governance-risk-committee",
        context: dict[str, object] | None = None,
    ) -> EvaluationGateDecision:
        risk_level = self._risk_level_from_score(risk_score)
        gate_passed = quality_score >= quality_floor and slo_score >= slo_floor and risk_score >= risk_floor
        policy_registry = self._policy_registry or PolicyRegistry()
        policy_registry.register_risk_level_templates()
        policy_id = policy_registry.resolve_risk_policy(risk_level)

        merged_context = dict(context or {})
        merged_context.setdefault("evaluation_id", evaluation_id)
        merged_context.setdefault("quality_score", quality_score)
        merged_context.setdefault("slo_score", slo_score)
        merged_context.setdefault("risk_score", risk_score)

        policy_result = policy_registry.enforce_risk_level(
            risk_level=risk_level,
            actor=actor,
            action=action,
            context=merged_context,
        )

        approval_required = (risk_level in {"high", "critical"}) or (not policy_result.allowed) or (not gate_passed)
        decision = "approval_required" if approval_required else "auto_approved"
        approval_request_id = ""

        if approval_required:
            router = self._approval_router or ApprovalRouter()
            request = router.submit_request(
                "evaluation_gate",
                payload={
                    "evaluation_id": evaluation_id,
                    "scores": {
                        "quality": quality_score,
                        "slo": slo_score,
                        "risk": risk_score,
                    },
                    "risk_level": risk_level,
                    "policy_id": policy_id,
                    "policy_allowed": policy_result.allowed,
                    "gate_passed": gate_passed,
                },
                requester=actor,
            )
            router.route_to_committee(request.id, committee_id)
            approval_request_id = request.id

        event_payload = {
            "evaluation_id": evaluation_id,
            "actor": actor,
            "risk_level": risk_level,
            "scores": {
                "quality": quality_score,
                "slo": slo_score,
                "risk": risk_score,
            },
            "gate_passed": gate_passed,
            "policy_id": policy_id,
            "policy_allowed": policy_result.allowed,
            "approval_required": approval_required,
            "approval_request_id": approval_request_id,
            "decision": decision,
        }

        if self._audit_query is not None:
            self._audit_query.record(
                event_type="evaluation_gate_decision",
                domain="D-Governance",
                actor=actor,
                payload=event_payload,
                severity=SEVERITY_WARN if approval_required else SEVERITY_INFO,
            )

        if self._event_publisher is not None:
            self._event_publisher(self.EVENT_TOPIC_EVALUATION, event_payload)

        return EvaluationGateDecision(
            evaluation_id=evaluation_id,
            decision=decision,
            risk_level=risk_level,
            gate_passed=gate_passed,
            approval_required=approval_required,
            policy_id=policy_id,
            policy_allowed=policy_result.allowed,
            approval_request_id=approval_request_id,
            event_topic=self.EVENT_TOPIC_EVALUATION,
            event_payload=event_payload,
        )


__all__ = [
    "GovernanceEscalationRecord",
    "EvaluationGateDecision",
    "GovernanceObservabilityBridge",
]
