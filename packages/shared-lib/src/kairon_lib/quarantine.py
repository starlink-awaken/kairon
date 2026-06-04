from __future__ import annotations

"""
Quarantine Manager — Isolate and release agents with reason tracking.

Based on D_Immunity patterns:
- organs/organ_quarantine.py (OrganQuarantine: quarantine, lift, is_quarantined, get_all)
- organs/immunity_guard.py (freeze/quarantine integration)

Provides:
- quarantine(agent_id, reason) — isolate an agent
- release(agent_id) — release from quarantine
- is_quarantined(agent_id) — check status
- active_quarantines() — list all
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable

_log = logging.getLogger(__name__)


# =============================================================================
# QuarantineEntry
# =============================================================================


@dataclass
class QuarantineEntry:
    """Represents a quarantined agent."""

    agent_id: str
    reason: str
    quarantined_at: float = field(default_factory=time.time)
    quarantined_by: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "reason": self.reason,
            "quarantined_at": self.quarantined_at,
            "quarantined_by": self.quarantined_by,
            "metadata": self.metadata,
        }


# =============================================================================
# QuarantineManager
# =============================================================================


class QuarantineManager:
    """Manages agent quarantine — isolate, check, release, and list.

    Typical usage::

        qm = QuarantineManager()
        qm.quarantine("agent-7", reason="Behavioral anomaly, Z=4.2")
        assert qm.is_quarantined("agent-7")
        qm.release("agent-7")
        assert not qm.is_quarantined("agent-7")
    """

    def __init__(self) -> None:
        self._registry: dict[str, QuarantineEntry] = {}
        self._history: list[QuarantineEntry] = []
        self._release_callbacks: list[Callable[[QuarantineEntry], Any]] = []
        self._quarantine_callbacks: list[Callable[[QuarantineEntry], Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def quarantine(
        self,
        agent_id: str,
        reason: str = "Unspecified",
        *,
        quarantined_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Isolate an agent by adding it to the quarantine registry.

        Args:
            agent_id:       Identifier of the agent to quarantine.
            reason:         Human-readable reason for isolation.
            quarantined_by: Who/What initiated the quarantine.
            metadata:       Optional arbitrary metadata.

        Returns:
            True if the agent was newly quarantined, False if already quarantined.
        """
        if not agent_id:
            _log.warning("quarantine: empty agent_id, refusing")
            return False

        if agent_id in self._registry:
            _log.debug("Agent %s already quarantined", agent_id)
            return False

        entry = QuarantineEntry(
            agent_id=agent_id,
            reason=reason,
            quarantined_by=quarantined_by,
            metadata=metadata or {},
        )
        self._registry[agent_id] = entry
        self._history.append(entry)

        _log.warning(
            "Agent %s QUARANTINED. Reason: %s (by: %s)",
            agent_id, reason, quarantined_by or "system",
        )

        for cb in self._quarantine_callbacks:
            try:
                cb(entry)
            except Exception as exc:
                _log.error("Quarantine callback error: %s", exc)

        return True

    def release(self, agent_id: str) -> bool:
        """Release an agent from quarantine.

        Returns:
            True if the agent was quarantined and is now released, False otherwise.
        """
        if not agent_id or agent_id not in self._registry:
            return False

        entry = self._registry.pop(agent_id)
        _log.info("Agent %s RELEASED from quarantine (was: %s)", agent_id, entry.reason)

        for cb in self._release_callbacks:
            try:
                cb(entry)
            except Exception as exc:
                _log.error("Release callback error: %s", exc)

        return True

    def is_quarantined(self, agent_id: str) -> bool:
        """Check whether an agent is currently quarantined."""
        return agent_id in self._registry

    def active_quarantines(self) -> list[dict[str, Any]]:
        """Return list of all currently quarantined agents."""
        return [entry.to_dict() for entry in self._registry.values()]

    def get_entry(self, agent_id: str) -> dict[str, Any] | None:
        """Get details for a quarantined agent, or None."""
        entry = self._registry.get(agent_id)
        return entry.to_dict() if entry else None

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent quarantine history (including released agents)."""
        return [e.to_dict() for e in self._history[-limit:]]

    def release_all(self) -> int:
        """Release all quarantined agents. Returns count released."""
        count = len(self._registry)
        for agent_id in list(self._registry.keys()):
            self.release(agent_id)
        return count

    def on_quarantine(self, callback: callable) -> None:  # type: ignore[valid-type]
        """Register a callback invoked when an agent is quarantined.
        Callback receives a QuarantineEntry.
        """
        self._quarantine_callbacks.append(callback)

    def on_release(self, callback: callable) -> None:  # type: ignore[valid-type]
        """Register a callback invoked when an agent is released.
        Callback receives a QuarantineEntry.
        """
        self._release_callbacks.append(callback)


__all__ = [
    "QuarantineEntry",
    "QuarantineManager",
]
