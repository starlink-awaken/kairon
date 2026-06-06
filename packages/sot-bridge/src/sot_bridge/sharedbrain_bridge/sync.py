"""Batch Sync Bridge — DEPRECATED.

SharedBrain has been decommissioned. This module is a no-op stub retained for
import compatibility.

Debt resolved: BYPASS-005 (hardcoded DEFAULT_SB localhost:7421)
               BYPASS-003 (SharedBrain organs path dependency)
Deprecated at: 2026-06-06 (Phase 31 cleanup)
"""

import logging
from typing import Any

_log = logging.getLogger(__name__)

# SharedBrain has been decommissioned.
# DEFAULT_SB constant and SHAREDBRAIN_ORGANS path intentionally removed.
# BYPASS-003/005 resolved: no more hardcoded localhost:7421 or organs path references.


class SyncBridge:
    """Batch Sync Bridge stub.

    SharedBrain has been decommissioned. All methods return safe no-op responses.
    This class is retained for import compatibility only.
    """

    def __init__(self, sharedbrain: str = "") -> None:
        if sharedbrain:
            _log.warning("SyncBridge: SharedBrain has been decommissioned. Connection argument is ignored.")
        self.sb = sharedbrain

    def get_active_organs(self) -> list[dict[str, Any]]:
        """No-op stub — SharedBrain organs directory no longer exists."""
        _log.debug("SyncBridge.get_active_organs: SharedBrain decommissioned, returning empty list.")
        return []

    def batch_sync_to_memory(self, organs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """No-op stub — SharedBrain is decommissioned."""
        _log.debug("SyncBridge.batch_sync_to_memory: SharedBrain decommissioned, skipping sync.")
        count = len(organs) if organs is not None else 0
        return {"synced": False, "error": "SharedBrain decommissioned", "count": count, "fp": ""}
