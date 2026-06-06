"""SharedBrain Bridge — DEPRECATED STUB.

SharedBrain has been decommissioned (Phase 31, 2026-06-06).
This package is retained for import compatibility only. All bridge classes
return safe no-op responses.

Migration: Use kairon-native data stores (kos, eidos, gbrain) instead.

Resolved debts:
  BYPASS-003: agent-runtime identity → SharedBrain direct connection
  BYPASS-004: sharedbrain-bridge/eu.py DEFAULT_AGORA hardcoded localhost:7430
  BYPASS-005: sharedbrain-bridge hardcoded DEFAULT_SB localhost:7421
"""

__version__ = "0.3.0"
__all__ = ("__version__",)
