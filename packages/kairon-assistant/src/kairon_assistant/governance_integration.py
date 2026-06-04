from __future__ import annotations

"""
---
Type: Stub
Layer: L3
Domain: D-Governance
Status: STUB
Version: 0.1.0
Summary: Governance integration stub — Wave 2 placeholder
Source: SharedBrain D_Governance/connectors/smart_assistant.py
---
"""

import logging
from typing import Any

from kairon_assistant.types import CommandType

logger = logging.getLogger(__name__)


class GovernanceIntegration:
    """Governance integration stub.

    NOTE: This is a placeholder implementation for Wave 2 migration.
    The real D-Governance integration has not been migrated yet.
    All permission checks return True (permitted) as stub behavior.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    async def initialize(self) -> None:
        """Initialize governance integration. (stub — no-op)"""
        logger.info("[GovernanceIntegration] Initialized (stub mode)")

    async def shutdown(self) -> None:
        """Shutdown governance integration. (stub — no-op)"""
        logger.info("[GovernanceIntegration] Shutdown complete (stub mode)")

    async def check_permission(
        self,
        user_id: str,
        command_type: CommandType,
        parameters: dict[str, Any] | None = None,
    ) -> bool:
        """Check if user has permission for a given command.

        Args:
            user_id: User identifier
            command_type: Type of command being requested
            parameters: Optional command parameters

        Returns:
            Always True (stub behavior — real governance not yet migrated)
        """
        if not self.enabled:
            return True

        logger.info(
            "[GovernanceIntegration] Permission check (stub): user=%s command=%s → permitted",
            user_id,
            command_type.value if command_type else None,
        )
        return True
