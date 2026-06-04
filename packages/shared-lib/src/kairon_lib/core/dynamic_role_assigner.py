from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Dynamic Role Assigner ≡ Module
# 内涵 ≝ {Dynamic, Role, Assigner}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, DynamicRoleAssigner)}
# 功能 ⊢ {Dynamic_Role, Role_Assigner, Assigner_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

"""Dynamic Role Assigner — runtime role assignment and lifecycle for agents.

Manages temporary and permanent role assignments with expiration, scoping,
and garbage collection of stale bindings.

Usage:
    assigner = DynamicRoleAssigner()
    assignment = assigner.assign_role("agent-1", "reviewer", duration_seconds=3600)
    assert assigner.has_role("agent-1", "reviewer")
    assigner.revoke_role("agent-1", "reviewer")
"""

import time
from dataclasses import dataclass


@dataclass
class RoleAssignment:
    """A single role binding between an agent and a role."""

    agent_id: str
    role_id: str
    assigned_at: float
    expires_at: float | None = None
    scope: str = "global"


class DynamicRoleAssigner:
    """Runtime role assignment manager with expiration and scoping."""

    def __init__(self) -> None:
        super().__init__()
        self._assignments: list[RoleAssignment] = []

    def assign_role(
        self,
        agent_id: str,
        role_id: str,
        scope: str = "global",
        duration_seconds: float | None = None,
    ) -> RoleAssignment:
        """Assign a role to an agent, optionally with a TTL."""
        now = time.time()
        expires_at = now + duration_seconds if duration_seconds is not None else None
        assignment = RoleAssignment(
            agent_id=agent_id,
            role_id=role_id,
            assigned_at=now,
            expires_at=expires_at,
            scope=scope,
        )
        # Replace existing identical binding if present
        self._assignments = [
            a for a in self._assignments if not (a.agent_id == agent_id and a.role_id == role_id and a.scope == scope)
        ]
        self._assignments.append(assignment)
        return assignment

    def revoke_role(self, agent_id: str, role_id: str) -> None:
        """Remove all assignments of *role_id* from *agent_id*."""
        self._assignments = [a for a in self._assignments if not (a.agent_id == agent_id and a.role_id == role_id)]

    def _active_assignments(self) -> list[RoleAssignment]:
        now = time.time()
        return [a for a in self._assignments if a.expires_at is None or a.expires_at > now]

    def get_roles(self, agent_id: str) -> list[str]:
        """Return current (non-expired) role IDs for *agent_id*."""
        return list({a.role_id for a in self._active_assignments() if a.agent_id == agent_id})

    def get_agents_with_role(self, role_id: str) -> list[str]:
        """Return agent IDs currently holding *role_id*."""
        return list({a.agent_id for a in self._active_assignments() if a.role_id == role_id})

    def has_role(self, agent_id: str, role_id: str) -> bool:
        """Check whether *agent_id* currently holds *role_id*."""
        return any(a.agent_id == agent_id and a.role_id == role_id for a in self._active_assignments())

    def gc_expired(self) -> int:
        """Remove expired assignments. Returns count of removed entries."""
        before = len(self._assignments)
        now = time.time()
        self._assignments = [a for a in self._assignments if a.expires_at is None or a.expires_at > now]
        return before - len(self._assignments)

    def get_role_stats(self) -> dict:
        """Return aggregated statistics about current assignments."""
        active = self._active_assignments()
        roles: dict[str, set[str]] = {}
        for a in active:
            roles.setdefault(a.role_id, set()).add(a.agent_id)
        return {
            "total_assignments": len(active),
            "assignments_per_role": {r: len(agents) for r, agents in roles.items()},
            "agents_per_role": {r: sorted(agents) for r, agents in roles.items()},
        }

    def list_assignments(self) -> list[RoleAssignment]:
        """Return all active assignments."""
        return list(self._active_assignments())
