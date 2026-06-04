"""Energy resource accounting data models — extracted from SharedBrain D_Economy.

Provides core abstractions independent of SharedBrain's CoreService/PersistenceProvider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResourceType(Enum):
    EU = "eu"
    NECTAR = "nectar"
    QUOTA = "quota"


@dataclass
class EnergyEntry:
    """A single energy consumption/budget record."""

    caller_id: str
    operation: str
    cost: float
    balance_before: float
    balance_after: float
    idempotency_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "caller_id": self.caller_id,
            "operation": self.operation,
            "cost": self.cost,
            "balance_before": self.balance_before,
            "balance_after": self.balance_after,
            "idempotency_key": self.idempotency_key,
        }


@dataclass
class EnergyBudget:
    """Per-caller energy budget."""

    caller_id: str
    limit: float = 1000.0
    consumed: float = 0.0
    entries: list[EnergyEntry] = field(default_factory=list)

    @property
    def balance(self) -> float:
        return max(0.0, self.limit - self.consumed)

    def can_afford(self, cost: float) -> bool:
        return self.balance >= cost

    def consume(self, operation: str, cost: float, idempotency_key: str = "") -> EnergyEntry | None:
        if not self.can_afford(cost):
            return None
        balance_before = self.balance
        entry = EnergyEntry(
            caller_id=self.caller_id,
            operation=operation,
            cost=cost,
            balance_before=balance_before,
            balance_after=balance_before - cost,
            idempotency_key=idempotency_key,
        )
        self.consumed += cost
        self.entries.append(entry)
        return entry


DEFAULT_PRICING: dict[str, float] = {
    "minerva_research": 10.0,
    "ontoderive_engine": 5.0,
    "eidos_validate": 2.0,
    "kos_index": 3.0,
    "kronos_ingest": 1.0,
    "sophia_compile": 5.0,
    "agora_route": 0.5,
    "codeanalyze_scan": 2.0,
}
