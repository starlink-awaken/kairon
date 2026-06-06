"""Immune Audit Bridge — DEPRECATED.

SharedBrain has been decommissioned. This module is a no-op stub retained for
import compatibility.

Debt resolved: BYPASS-005 (hardcoded DEFAULT_SB localhost:7421)
Deprecated at: 2026-06-06 (Phase 31 cleanup)
"""

import logging

_log = logging.getLogger(__name__)

# SharedBrain has been decommissioned — DEFAULT_SB constant intentionally removed.
# BYPASS-005 resolved: no more hardcoded localhost:7421 reference.


class ImmuneBridge:
    """Immune Audit Bridge stub.

    SharedBrain has been decommissioned. All methods return safe no-op responses.
    This class is retained for import compatibility only.
    """

    def __init__(self, sharedbrain: str = "") -> None:
        if sharedbrain:
            _log.warning("ImmuneBridge: SharedBrain has been decommissioned. Connection argument is ignored.")
        self.sb = sharedbrain

    def audit(self, content: str, title: str = "", source: str = "") -> dict:
        """No-op stub — SharedBrain is decommissioned."""
        _log.debug("ImmuneBridge.audit: SharedBrain decommissioned, skipping immune audit.")
        return {"risk": "UNKNOWN", "error": "SharedBrain decommissioned"}
