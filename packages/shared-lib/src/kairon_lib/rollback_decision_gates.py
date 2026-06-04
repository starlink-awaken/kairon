from __future__ import annotations

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RollbackGate:
    gate_id: str
    name: str
    condition: str
    threshold: float
    action: str = "rollback"
    enabled: bool = True


@dataclass
class RollbackDecision:
    gate_id: str
    triggered: bool
    metric_value: float
    threshold: float
    timestamp: float = 0.0


class RollbackDecisionGates:
    """Gate-based rollback decision system for evolution safety."""

    def __init__(self) -> None:
        self._gates: dict[str, RollbackGate] = {}
        self._history: list[RollbackDecision] = []

    def register_gate(self, gate: RollbackGate) -> None:
        self._gates[gate.gate_id] = gate
        logger.info("Registered rollback gate %s: %s", gate.gate_id, gate.name)

    def evaluate_gate(self, gate_id: str, metric_value: float) -> RollbackDecision:
        gate = self._gates.get(gate_id)
        if gate is None:
            raise KeyError(f"Gate {gate_id} not found")
        triggered = gate.enabled and metric_value >= gate.threshold
        decision = RollbackDecision(
            gate_id=gate_id,
            triggered=triggered,
            metric_value=metric_value,
            threshold=gate.threshold,
            timestamp=time.time(),
        )
        self._history.append(decision)
        if triggered:
            logger.warning("Gate %s triggered: %.4f >= %.4f", gate_id, metric_value, gate.threshold)
        return decision

    def evaluate_all(self, metrics: dict[str, float]) -> list[RollbackDecision]:
        decisions: list[RollbackDecision] = []
        for gate_id, _gate in self._gates.items():
            if gate_id in metrics:
                decision = self.evaluate_gate(gate_id, metrics[gate_id])
                decisions.append(decision)
        return decisions

    def should_rollback(self, metrics: dict[str, float]) -> bool:
        decisions = self.evaluate_all(metrics)
        return any(d.triggered for d in decisions)

    def get_gate(self, gate_id: str) -> RollbackGate | None:
        return self._gates.get(gate_id)

    def list_gates(self) -> list[RollbackGate]:
        return list(self._gates.values())

    def get_trigger_history(self) -> list[RollbackDecision]:
        return list(self._history)

    def disable_gate(self, gate_id: str) -> None:
        gate = self._gates.get(gate_id)
        if gate is None:
            raise KeyError(f"Gate {gate_id} not found")
        gate.enabled = False
        logger.info("Disabled gate %s", gate_id)

    def enable_gate(self, gate_id: str) -> None:
        gate = self._gates.get(gate_id)
        if gate is None:
            raise KeyError(f"Gate {gate_id} not found")
        gate.enabled = True
        logger.info("Enabled gate %s", gate_id)
