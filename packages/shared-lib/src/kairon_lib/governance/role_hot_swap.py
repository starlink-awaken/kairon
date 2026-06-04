from __future__ import annotations

import logging

_log = logging.getLogger(__name__)
"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Role Hot Swap ≡ Module
# 内涵 ≝ {Role, Hot, Swap}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, RoleHotSwap)}
# 功能 ⊢ {Role_Hot, Hot_Swap, Swap_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BindingResult:
    success: bool
    agent_id: str
    new_role: str | None = None
    old_role: str | None = None
    reason: str = ""


@dataclass(slots=True)
class BindingRecord:
    agent_id: str
    role_id: str
    bound_at: float = field(default_factory=time.time)
    expires_at: float | None = None

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and time.time() >= self.expires_at


@dataclass(slots=True)
class HistoryEntry:
    action: str
    agent_id: str
    old_role: str | None
    new_role: str | None
    timestamp: float = field(default_factory=time.time)


class RoleHotSwap:
    """Manage dynamic agent-role bindings with TTL-aware hot swapping."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._roles: dict[str, dict[str, Any]] = {}
        self._bindings: dict[str, BindingRecord] = {}
        self._history: list[HistoryEntry] = []

    def register_role(self, role_id: str, metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._roles[role_id] = dict(metadata or {})

    def unregister_role(self, role_id: str) -> bool:
        with self._lock:
            removed = self._roles.pop(role_id, None)
            if removed is None:
                return False
            agents_to_unbind = [
                agent_id
                for agent_id, binding in self._bindings.items()
                if not binding.is_expired and binding.role_id == role_id
            ]
            for agent_id in agents_to_unbind:
                self._bindings.pop(agent_id, None)
                self._history.append(
                    HistoryEntry(
                        action="role_unregistered",
                        agent_id=agent_id,
                        old_role=role_id,
                        new_role=None,
                    )
                )
            return True

    def list_roles(self) -> list[str]:
        with self._lock:
            return sorted(self._roles)

    def bind(self, agent_id: str, role_id: str, ttl: float | None = None) -> BindingResult:
        with self._lock:
            if role_id not in self._roles:
                return BindingResult(
                    success=False,
                    agent_id=agent_id,
                    reason=f"Role {role_id!r} is not registered",
                )

            old_role = self.get_role(agent_id)
            expires_at = None if ttl is None else time.time() + ttl
            self._bindings[agent_id] = BindingRecord(
                agent_id=agent_id,
                role_id=role_id,
                expires_at=expires_at,
            )
            self._history.append(
                HistoryEntry(
                    action="bind" if old_role is None else "swap",
                    agent_id=agent_id,
                    old_role=old_role,
                    new_role=role_id,
                )
            )
            return BindingResult(
                success=True,
                agent_id=agent_id,
                old_role=old_role,
                new_role=role_id,
            )

    def swap(self, agent_id: str, new_role: str, ttl: float | None = None) -> BindingResult:
        return self.bind(agent_id, new_role, ttl=ttl)

    def unbind(self, agent_id: str) -> BindingResult:
        with self._lock:
            current_role = self.get_role(agent_id)
            if current_role is None:
                return BindingResult(
                    success=False,
                    agent_id=agent_id,
                    reason=f"Agent {agent_id!r} is not bound",
                )
            self._bindings.pop(agent_id, None)
            self._history.append(
                HistoryEntry(
                    action="unbind",
                    agent_id=agent_id,
                    old_role=current_role,
                    new_role=None,
                )
            )
            return BindingResult(
                success=True,
                agent_id=agent_id,
                old_role=current_role,
                new_role=None,
            )

    def get_role(self, agent_id: str) -> str | None:
        with self._lock:
            binding = self._bindings.get(agent_id)
            if binding is None:
                return None
            if binding.is_expired:
                self._bindings.pop(agent_id, None)
                return None
            return binding.role_id

    def get_agents_by_role(self, role_id: str) -> list[str]:
        with self._lock:
            expired_agents: list[str] = []
            agents: list[str] = []
            for agent_id, binding in self._bindings.items():
                if binding.is_expired:
                    expired_agents.append(agent_id)
                    continue
                if binding.role_id == role_id:
                    agents.append(agent_id)
            for agent_id in expired_agents:
                self._bindings.pop(agent_id, None)
            return sorted(agents)

    def get_history(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self._history)

    def cleanup_expired(self) -> int:
        with self._lock:
            expired_agents = [agent_id for agent_id, binding in self._bindings.items() if binding.is_expired]
            for agent_id in expired_agents:
                self._bindings.pop(agent_id, None)
            if expired_agents:
                _log.debug("Cleaned up %d expired role bindings", len(expired_agents))
            return len(expired_agents)
