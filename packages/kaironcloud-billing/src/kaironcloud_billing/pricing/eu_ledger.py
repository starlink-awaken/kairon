"""EU Ledger — virtual resource accounting for the kairon pipeline.

Integrates with SharedBrain D-Economy via Agora MCP to check and
consume EU (Energy Units) for pipeline operations.

Merged from eu-pricing package into kaironcloud-billing pricing subpackage.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)

# Pipeline step pricing (EU units per operation)
DEFAULT_PRICING: dict[str, int] = {
    "minerva_research": 10,
    "ontoderive_engine": 5,
    "eidos_validate": 2,
    "kos_index": 3,
    "kronos_ingest": 1,
    "sophia_compile": 5,
}


@dataclass
class EUBalance:
    caller: str
    balance: int
    limit: int = field(default=1000)
    blocked: bool = field(default=False)

    def sufficient(self, amount: int = 1) -> bool:
        return self.balance >= amount and not self.blocked


@dataclass
class EUTransaction:
    caller: str
    operation: str
    cost: int
    balance_after: int
    success: bool
    error: str | None = None


class EULedger:
    """EU virtual resource accounting — L2 capability layer.

    Queries SharedBrain D-Economy for EU balances via Agora MCP.
    """

    def __init__(self, agora_endpoint: str = "http://localhost:7430"):
        self.endpoint = agora_endpoint.rstrip("/")
        self._cache: dict[str, EUBalance] = {}

    def check_balance(self, caller: str) -> EUBalance:
        """Check EU balance for a caller."""
        if caller in self._cache:
            return self._cache[caller]
        balance = self._fetch_balance(caller)
        self._cache[caller] = balance
        return balance

    def consume(self, caller: str, operation: str) -> EUTransaction:
        """Consume EU for a pipeline operation."""
        cost = self._get_cost(operation)
        balance = self.check_balance(caller)

        if not balance.sufficient(cost):
            return EUTransaction(
                caller=caller,
                operation=operation,
                cost=cost,
                balance_after=balance.balance,
                success=False,
                error=f"Insufficient EU: need {cost}, have {balance.balance}",
            )

        result = self._push_consumption(caller, cost, operation)
        if result.get("ok"):
            new_balance = balance.balance - cost
            self._cache[caller] = EUBalance(
                caller=caller,
                balance=new_balance,
                limit=balance.limit,
            )
            return EUTransaction(
                caller=caller,
                operation=operation,
                cost=cost,
                balance_after=new_balance,
                success=True,
            )
        else:
            return EUTransaction(
                caller=caller,
                operation=operation,
                cost=cost,
                balance_after=balance.balance,
                success=False,
                error=result.get("error", "Unknown economy error"),
            )

    def _get_cost(self, operation: str) -> int:
        return DEFAULT_PRICING.get(operation, 1)

    def _fetch_balance(self, caller: str) -> EUBalance:
        try:
            url = f"{self.endpoint}/api/v1/economy/balance?caller={caller}"
            req = Request(url, method="GET")  # noqa: S310
            resp = urlopen(req, timeout=5)  # noqa: S310
            data = json.loads(resp.read().decode())
            return EUBalance(
                caller=caller,
                balance=data.get("balance", 100),
                limit=data.get("limit", 1000),
            )
        except Exception:
            _log.warning("EU balance fetch failed — using default")
            return EUBalance(caller=caller, balance=100, limit=1000)

    def _push_consumption(self, caller: str, cost: int, operation: str) -> dict:
        try:
            payload = json.dumps({"caller": caller, "cost": cost, "operation": operation}).encode()
            req = Request(  # noqa: S310
                f"{self.endpoint}/api/v1/economy/consume",
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            resp = urlopen(req, timeout=5)  # noqa: S310
            return {"ok": resp.status == 200}
        except Exception as e:
            return {"ok": False, "error": str(e)}
