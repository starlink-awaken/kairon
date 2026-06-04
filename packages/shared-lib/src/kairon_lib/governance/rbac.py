"""RBAC model — permission matrix, role definitions, access control, and audit types.

Extracted from SharedBrain D_Governance:
- organs/compliance/permission_matrix.py (dataclasses/enums only, SQLite orchestration skipped)
- organs/role/role_rbac.py (dataclasses only, SQLite orchestration skipped)

Zero external dependencies — pure dataclasses and enums.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# ─────────────────────────────────────────────────────────────────
# From permission_matrix.py — canonical permission types
# ─────────────────────────────────────────────────────────────────


class PermissionAction(StrEnum):
    """Canonical set of permission actions."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class Effect(StrEnum):
    """Effect of a permission rule."""

    ALLOW = "allow"
    DENY = "deny"


class ActionType(StrEnum):
    """Type of action on a resource (superset of PermissionAction)."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"
    CUSTOM = "custom"


@dataclass
class PermissionRule:
    """A single permission entry binding a role to a resource pattern."""

    role: str
    resource_pattern: str
    actions: list[PermissionAction]
    effect: str = "allow"  # "allow" | "deny"


@dataclass
class RoleDefinition:
    """Definition of a role and its associated permissions."""

    role_id: str
    name: str
    permissions: list[PermissionRule]
    parent_role: str | None = None


@dataclass
class Permission:
    """Represents a single granted permission entry with audit trail."""

    id: str
    role_id: str
    resource: str  # Resource identifier (e.g., "bos://governance/policies")
    action: ActionType
    effect: Effect
    granted_at: str
    granted_by: str
    inherited_from: str | None = None  # If inherited from parent role
    conditions: dict[str, Any] | None = None  # Optional conditions

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role_id": self.role_id,
            "resource": self.resource,
            "action": self.action.value,
            "effect": self.effect.value,
            "granted_at": self.granted_at,
            "granted_by": self.granted_by,
            "inherited_from": self.inherited_from,
            "conditions": self.conditions,
        }


@dataclass
class RoleInheritance:
    """Represents an inheritance relationship between roles."""

    id: str
    child_role_id: str
    parent_role_id: str
    created_at: str
    created_by: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "child_role_id": self.child_role_id,
            "parent_role_id": self.parent_role_id,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }


@dataclass
class PermissionConflict:
    """Represents a detected conflict in permissions."""

    conflict_id: str
    role_id: str
    resource: str
    action: ActionType
    conflicting_permissions: list[Permission]
    conflict_type: str  # "allow_deny", "inheritance_cycle"
    detected_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "role_id": self.role_id,
            "resource": self.resource,
            "action": self.action.value,
            "conflicting_permissions": [p.to_dict() for p in self.conflicting_permissions],
            "conflict_type": self.conflict_type,
            "detected_at": self.detected_at,
        }


# Mapping between PermissionAction and ActionType
PERMISSION_ACTION_TO_ACTION_TYPE: dict[PermissionAction, ActionType] = {
    PermissionAction.READ: ActionType.READ,
    PermissionAction.WRITE: ActionType.WRITE,
    PermissionAction.EXECUTE: ActionType.EXECUTE,
    PermissionAction.ADMIN: ActionType.ADMIN,
}


# ─────────────────────────────────────────────────────────────────
# From role_rbac.py — access rule, decision, and audit types
# ─────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class AccessRule:
    """A simple resource-to-actions permission rule (from role_rbac)."""

    resource: str
    actions: list[str]


@dataclass(slots=True)
class RolePermissionSet:
    """A role's set of access rules with budget and time-window constraints."""

    role_id: str
    permissions: list[AccessRule]
    max_eu_budget: float = float("inf")
    time_window: tuple[int, int] | None = None
    spent_eu: float = 0.0


@dataclass(slots=True)
class AccessDecision:
    """Result of an access check."""

    allowed: bool
    reason: str


@dataclass(slots=True)
class AuditEntry:
    """An audit record of an access check."""

    role_id: str
    resource: str
    action: str
    allowed: bool
    reason: str
    timestamp: str = ""


__all__ = [
    "AccessDecision",
    "AccessRule",
    "ActionType",
    "AuditEntry",
    "Effect",
    "PERMISSION_ACTION_TO_ACTION_TYPE",
    "Permission",
    "PermissionAction",
    "PermissionConflict",
    "PermissionRule",
    "RoleDefinition",
    "RoleInheritance",
    "RolePermissionSet",
]
