"""Energy Optimizer — optimize EU consumption across operations."""

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum


class Strategy(StrEnum):
    MINIMIZE_COST = "minimize_cost"
    MAXIMIZE_SPEED = "maximize_speed"
    BALANCED = "balanced"


@dataclass
class CostEstimate:
    operation: str
    estimated_eu: float
    confidence: float = 0.8
    factors: dict = field(default_factory=dict)


@dataclass
class Budget:
    agent_id: str = ""
    limit: float = 1000.0
    spent: float = 0.0
    reserved: float = 0.0
    alerts: list[str] = field(default_factory=list)

    @property
    def available(self) -> float:
        return max(0.0, self.limit - self.spent - self.reserved)

    @property
    def usage_pct(self) -> float:
        return (self.spent + self.reserved) / max(self.limit, 0.01) * 100


class EnergyOptimizer:
    """Optimize EU consumption with cost prediction and budget management."""

    def __init__(self):
        self._budgets: dict[str, Budget] = {}  # type: ignore[annotation-unchecked]
        self._usage_history: dict[str, deque] = {}  # type: ignore[annotation-unchecked]
        self._cost_model: dict[str, float] = {  # type: ignore[annotation-unchecked]
            "kos_search": 3.0, "minerva_research": 10.0, "code_analysis": 5.0,
            "llm_query": 2.0, "llm_generation": 8.0, "graph_query": 1.0,
            "embedding": 4.0, "index_build": 15.0,
        }

    def set_budget(self, agent_id: str, limit: float):
        if agent_id not in self._budgets:
            self._budgets[agent_id] = Budget(agent_id=agent_id, limit=limit)
        else:
            self._budgets[agent_id].limit = limit

    def get_budget(self, agent_id: str) -> Budget:
        if agent_id not in self._budgets:
            self._budgets[agent_id] = Budget(agent_id=agent_id)
        return self._budgets[agent_id]

    def estimate_cost(self, operation: str, complexity: float = 1.0, size: int = 1, urgency: float = 0.0) -> CostEstimate:
        base = self._cost_model.get(operation, 5.0)
        urgency_factor = 1.0 + urgency * 0.5
        estimated = base * complexity * size * urgency_factor
        return CostEstimate(operation=operation, estimated_eu=round(estimated, 2),
                           factors={"base": base, "complexity": complexity, "size": size, "urgency": urgency_factor})

    def can_afford(self, agent_id: str, operation: str, complexity: float = 1.0, size: int = 1) -> tuple[bool, CostEstimate]:
        budget = self.get_budget(agent_id)
        estimate = self.estimate_cost(operation, complexity, size)
        return estimate.estimated_eu <= budget.available, estimate

    def reserve(self, agent_id: str, amount: float) -> bool:
        budget = self.get_budget(agent_id)
        if budget.available >= amount:
            budget.reserved += amount
            return True
        return False

    def commit(self, agent_id: str, amount: float):
        budget = self.get_budget(agent_id)
        budget.reserved = max(0, budget.reserved - amount)
        budget.spent += amount
        self._usage_history.setdefault(agent_id, deque(maxlen=100)).append(amount)
        if budget.usage_pct > 80:
            budget.alerts.append(f"Budget at {budget.usage_pct:.0f}% for {agent_id}")

    def get_usage_trend(self, agent_id: str) -> str:
        history = list(self._usage_history.get(agent_id, deque()))
        if len(history) < 5:
            return "insufficient_data"
        mid = len(history) // 2
        first_half = sum(history[:mid]) / max(mid, 1)
        second_half = sum(history[mid:]) / max(len(history) - mid, 1)
        if second_half > first_half * 1.2:
            return "increasing"
        elif second_half < first_half * 0.8:
            return "decreasing"
        return "stable"
