"""Agent Hub — agent registration, discovery, and lifecycle management.

Provides an in-memory registry for agents with capability-based discovery.
No external dependencies beyond the Python 3.10+ standard library.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class AgentInfo:
    """Immutable record describing a registered agent."""

    id: str
    name: str
    capabilities: list[str]
    endpoint: str
    status: str = "active"
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AgentHub:
    """In-memory agent registry with capability-based discovery."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}

    def register_agent(self, name: str, capabilities: list[str], endpoint: str) -> str:
        """Register a new agent and return its generated agent_id.

        Args:
            name: Human-readable agent name.
            capabilities: List of capability tags (e.g. ``["llm", "vision"]``).
            endpoint: Network endpoint the agent serves on.

        Returns:
            A unique agent identifier string (UUID4).
        """
        agent_id = uuid.uuid4().hex
        info = AgentInfo(
            id=agent_id,
            name=name,
            capabilities=list(capabilities),
            endpoint=endpoint,
        )
        self._agents[agent_id] = info
        return agent_id

    def discover_agents(self, capability: str | None = None) -> list[AgentInfo]:
        """Return agents matching the optional capability filter.

        Args:
            capability: If provided, only agents whose ``capabilities`` list
                contains this tag are returned.  When *None* (the default),
                all registered agents are returned.

        Returns:
            A (possibly empty) list of :class:`AgentInfo` records.
        """
        if capability is None:
            return list(self._agents.values())
        return [a for a in self._agents.values() if capability in a.capabilities]

    def deregister_agent(self, agent_id: str) -> bool:
        """Remove an agent by its id.

        Args:
            agent_id: The identifier returned by :meth:`register_agent`.

        Returns:
            ``True`` if the agent was found and removed, ``False`` otherwise.
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def list_all(self) -> list[AgentInfo]:
        """Return every registered agent.

        Returns:
            A list of :class:`AgentInfo` records (may be empty).
        """
        return list(self._agents.values())
