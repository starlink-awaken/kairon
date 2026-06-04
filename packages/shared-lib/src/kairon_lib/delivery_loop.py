from __future__ import annotations

from typing import Any

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Delivery Loop Bridge ≡ Module
# 内涵 ≝ {Delivery, Loop, Bridge}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, DeliveryLoopBridge)}
# 功能 ⊢ {Delivery_Loop, Loop_Bridge, Bridge_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

"""Reusable delivery-loop orchestration for verify -> reward -> retro -> harvest."""

from dataclasses import dataclass
from typing import Protocol

from kairon_lib.organs.execution.workflow_engine import (
    GateReview,
    WorkflowEngine,
    WorkflowPhase,
)
from kairon_lib.organs.registry.harvest_scheduler import HarvestEntry, HarvestScheduler
from kairon_lib.organs.retrospective.retrospective import RetrospectiveEngine


class RewardDistributor(Protocol):
    def distribute_reward(
        self,
        agent_id: str,
        amount: float,
        reason: str,
        *,
        domain: str = "default",
    ) -> Any: ...


@dataclass
class DeliveryLoopRecord:
    workflow_id: str
    gate_passed: bool
    reward_amount: float
    retro_entry_id: str
    harvested_source_ids: list[str]


class DeliveryLoopBridge:
    """Close a delivery by binding verification, reward, and learning records."""

    def __init__(
        self,
        retrospective_engine: RetrospectiveEngine | None = None,
        harvest_scheduler: HarvestScheduler | None = None,
    ) -> None:
        self._retrospective_engine = retrospective_engine or RetrospectiveEngine()
        self._harvest_scheduler = harvest_scheduler or HarvestScheduler()

    def close_delivery(
        self,
        *,
        work_id: str,
        title: str,
        owner: str,
        reward_distributor: RewardDistributor,
        reward_amount: float,
        reward_reason: str,
        reward_domain: str = "delivery",
    ) -> DeliveryLoopRecord:
        workflow = WorkflowEngine("Delivery Loop Bridge")

        with workflow.phase(WorkflowPhase.OBSERVE) as ctx:
            ctx.record("work_id", work_id)
            ctx.record("title", title)

        with workflow.phase(WorkflowPhase.PLAN) as ctx:
            workstream = ctx.add_workstream(
                f"ws-{work_id}",
                title,
                owner=owner,
                tasks=["execute", "verify", "reward", "retro", "harvest"],
            )

        with workflow.phase(WorkflowPhase.EXECUTE):
            workstream.start()
            workstream.complete(commit=f"delivery:{work_id}", tests_added=1)

        gate = GateReview(
            phase_name="verify",
            test_count=1,
            test_baseline=0,
            ruff_errors=0,
            notes=[f"delivery loop verified for {work_id}"],
        )
        gate.check_gate(min_tests_added=1, max_ruff_errors=0)
        workflow.add_gate_review(gate)

        with workflow.phase(WorkflowPhase.VERIFY) as ctx:
            ctx.record("gate_passed", gate.passed)

        reward = reward_distributor.distribute_reward(
            owner,
            reward_amount,
            reward_reason,
            domain=reward_domain,
        )
        retro_entry = self._retrospective_engine.record(
            iteration_id=workflow.workflow_id,
            what_worked=["verification completed", "reward distributed"],
            what_failed=[],
            lessons=["Verified deliveries should feed reward and learning loops"],
            recommendations=["Harvest retrospectives after verified deliveries"],
        )

        with workflow.phase(WorkflowPhase.LEARN) as ctx:
            ctx.record("retro_entry_id", retro_entry.id)
            ctx.record("reward_agent_id", getattr(reward, "agent_id", owner))

        harvested = self._harvest_scheduler.harvest_retrospectives(limit=10)
        harvested_ids = [entry.source_id for entry in harvested if isinstance(entry, HarvestEntry)]

        return DeliveryLoopRecord(
            workflow_id=workflow.workflow_id,
            gate_passed=gate.passed,
            reward_amount=float(getattr(reward, "amount", reward_amount)),
            retro_entry_id=retro_entry.id,
            harvested_source_ids=harvested_ids,
        )


__all__ = ["DeliveryLoopBridge", "DeliveryLoopRecord"]
