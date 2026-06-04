"""EU Pricing Bridge — kairon pipeline → SharedBrain D-Economy.

Provides EU (Energy Unit) balance checks and consumption tracking
for kairon pipeline operations.
"""

import json
import logging
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)

DEFAULT_AGORA = "http://localhost:7430"
DEFAULT_SB = "http://localhost:7421"
PRICING = {
    "minerva_research": 10,
    "ontoderive_engine": 5,
    "eidos_validate": 2,
    "kos_index": 3,
    "kronos_ingest": 1,
    "sophia_compile": 5,
}


class EUBridge:
    def __init__(self, agora=DEFAULT_AGORA, sharedbrain=DEFAULT_SB):
        self.agora = agora
        self.sb = sharedbrain

    def check_balance(self, caller: str) -> dict:
        try:
            url = f"{self.sb}/api/v1/economy/balance?caller={caller}"
            resp = urlopen(Request(url, method="GET"), timeout=5)
            data = json.loads(resp.read().decode())
            return {"balance": data.get("balance", 100), "limit": data.get("limit", 1000), "ok": True}
        except Exception as e:
            return {"balance": 100, "limit": 1000, "ok": False, "error": str(e)}

    def consume(self, caller: str, operation: str) -> dict:
        cost = PRICING.get(operation, 1)
        balance = self.check_balance(caller)
        if balance["balance"] < cost:
            return {"success": False, "error": f"Insufficient EU: need {cost}, have {balance['balance']}"}
        try:
            payload = json.dumps({"caller": caller, "cost": cost, "operation": operation}).encode()
            req = Request(f"{self.sb}/api/v1/economy/consume", data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urlopen(req, timeout=5)
            return {"success": resp.status == 200, "cost": cost, "balance_after": balance["balance"] - cost}
        except Exception as e:
            return {"success": False, "error": str(e)}
