"""EU Pricing Bridge — DEPRECATED.

SharedBrain has been decommissioned. This module is a no-op stub retained for
import compatibility. All EU pricing logic should be migrated to kairon's
internal accounting mechanisms (see X3-NO_COSTING debt item).

Debt resolved: BYPASS-004 (hardcoded DEFAULT_AGORA localhost:7430)
               BYPASS-005 (hardcoded DEFAULT_SB localhost:7421)
Deprecated at: 2026-06-06 (Phase 31 cleanup)
"""

import logging

_log = logging.getLogger(__name__)

# SharedBrain has been decommissioned — these constants are intentionally removed.
# BYPASS-004/005 resolved: no more hardcoded localhost references.

PRICING = {
    "minerva_research": 10,
    "ontoderive_engine": 5,
    "eidos_validate": 2,
    "kos_index": 3,
    "kronos_ingest": 1,
    "sophia_compile": 5,
}


class EUBridge:
    """EU Pricing Bridge stub.

    SharedBrain has been decommissioned. All methods return safe no-op responses.
    This class is retained for import compatibility only.
    """

    def __init__(self, agora: str = "", sharedbrain: str = "") -> None:
        if agora or sharedbrain:
            _log.warning("EUBridge: SharedBrain has been decommissioned. Connection arguments are ignored.")
        self.agora = agora
        self.sb = sharedbrain

    def check_balance(self, caller: str) -> dict:
        """No-op stub — returns unlimited balance since SharedBrain is decommissioned."""
        _log.debug("EUBridge.check_balance: SharedBrain decommissioned, returning stub balance.")
        return {"balance": 1000, "limit": 1000, "ok": False, "error": "SharedBrain decommissioned"}

    def consume(self, caller: str, operation: str) -> dict:
        """No-op stub — SharedBrain is decommissioned."""
        cost = PRICING.get(operation, 1)
        _log.debug("EUBridge.consume: SharedBrain decommissioned, skipping EU consumption.")
        return {"success": False, "cost": cost, "error": "SharedBrain decommissioned"}
