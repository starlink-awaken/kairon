from __future__ import annotations

"""
---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Updated: 2026-03-17
Authority: 4
Keywords: [permission, matrix, role, inheritance, rbac, access, control, sqlite]
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# PermissionMatrix ≡ Organ
# 内涵 ≝ {role_id, permission_id, resource, action, effect, inherited_from}
# 外延 ≝ {p | p ∈ D-Governance ∧ permission_entry(p)}
# 功能 ⊢ {CheckPermission, GrantPermission, RevokePermission, InheritRole,
#          DetectConflicts, GetRolePermissions, GetEffectivePermissions}
# =============================================================================

import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


# Local permission types (adapted from Z-Core law layer via facade pattern)
class PermissionAction(StrEnum):
    """Canonical set of permission actions."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


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


from kairon_lib.utils.sqlite_utils import managed_connection

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Effect enum
# ---------------------------------------------------------------------------


class Effect(StrEnum):
    """Effect of a permission rule."""

    ALLOW = "allow"
    DENY = "deny"


# ---------------------------------------------------------------------------
# ActionType enum
# ---------------------------------------------------------------------------


class ActionType(StrEnum):
    """Type of action on a resource."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Permission dataclass
# ---------------------------------------------------------------------------


@dataclass
class Permission:
    """Represents a single permission entry."""

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


# ---------------------------------------------------------------------------
# RoleInheritance dataclass
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# PermissionConflict dataclass
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# PermissionMatrix
# ---------------------------------------------------------------------------


class PermissionMatrix:
    """Role-based access control (RBAC) with inheritance support.

    Implements :class:`IPermissionChecker` from Z-Core/L2-Law.

    Manages permissions for roles with support for role inheritance and conflict detection.
    Deny permissions always override allow permissions.

    SQLite at ``data/db/organs/governance/permission_matrix.db``.
    Thread-safe; uses a per-instance Lock.

    BOS-URI endpoints
    -----------------
    ``bos://governance/permissions/check``   — check if permission is granted
    ``bos://governance/permissions/grant``   — grant a permission
    ``bos://governance/permissions/revoke``  — revoke a permission
    ``bos://governance/permissions/inherit``  — inherit from parent role
    ``bos://governance/permissions/conflicts`` — detect permission conflicts
    """

    _DEFAULT_DB: str = "data/db/organs/governance/permission_matrix.db"
    _lock: threading.Lock

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        _log.debug("[PermissionMatrix] db=%s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> Any:
        """Get database connection context manager."""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return managed_connection(conn)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS permissions (
                    id              TEXT PRIMARY KEY,
                    role_id         TEXT NOT NULL,
                    resource        TEXT NOT NULL,
                    action          TEXT NOT NULL,
                    effect          TEXT NOT NULL,
                    granted_at      TEXT NOT NULL,
                    granted_by      TEXT NOT NULL,
                    inherited_from  TEXT,
                    conditions_json TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_perm_role ON permissions(role_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_perm_resource ON permissions(resource)")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_perm_unique
                ON permissions(role_id, resource, action, inherited_from)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS role_inheritance (
                    id              TEXT PRIMARY KEY,
                    child_role_id   TEXT NOT NULL,
                    parent_role_id  TEXT NOT NULL,
                    created_at      TEXT NOT NULL,
                    created_by      TEXT NOT NULL,
                    UNIQUE(child_role_id, parent_role_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inherit_child ON role_inheritance(child_role_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inherit_parent ON role_inheritance(parent_role_id)")
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _row_to_permission(self, row: sqlite3.Row) -> Permission:
        import json

        return Permission(
            id=row["id"],
            role_id=row["role_id"],
            resource=row["resource"],
            action=ActionType(row["action"]),
            effect=Effect(row["effect"]),
            granted_at=row["granted_at"],
            granted_by=row["granted_by"],
            inherited_from=row["inherited_from"],
            conditions=json.loads(row["conditions_json"]) if row["conditions_json"] else None,
        )

    def _row_to_inheritance(self, row: sqlite3.Row) -> RoleInheritance:
        return RoleInheritance(
            id=row["id"],
            child_role_id=row["child_role_id"],
            parent_role_id=row["parent_role_id"],
            created_at=row["created_at"],
            created_by=row["created_by"],
        )

    # ------------------------------------------------------------------
    # Public API: Permission Management
    # ------------------------------------------------------------------

    def grant_permission(
        self,
        role_id: str,
        resource: str,
        action: ActionType,
        effect: Effect,
        granted_by: str,
        conditions: dict[str, Any] | None = None,
    ) -> Permission:
        """Grant a permission to a role."""
        perm_id = str(uuid.uuid4())
        now = self._now()

        import json

        permission = Permission(
            id=perm_id,
            role_id=role_id,
            resource=resource,
            action=action,
            effect=effect,
            granted_at=now,
            granted_by=granted_by,
            inherited_from=None,
            conditions=conditions,
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO permissions
                    (id, role_id, resource, action, effect, granted_at, granted_by, inherited_from, conditions_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    permission.id,
                    permission.role_id,
                    permission.resource,
                    permission.action.value,
                    permission.effect.value,
                    permission.granted_at,
                    permission.granted_by,
                    permission.inherited_from,
                    json.dumps(permission.conditions) if permission.conditions else None,
                ),
            )
            conn.commit()

        _log.debug(
            "[PermissionMatrix] granted %s on %s to role %s",
            action.value,
            resource,
            role_id,
        )
        return permission

    def revoke_permission(self, role_id: str, resource: str, action: ActionType) -> bool:
        """Revoke a permission from a role (including inherited)."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM permissions
                WHERE role_id = ? AND resource = ? AND action = ?
                """,
                (role_id, resource, action.value),
            )
            conn.commit()

        revoked = cursor.rowcount > 0
        if revoked:
            _log.debug(
                "[PermissionMatrix] revoked %s on %s from role %s",
                action.value,
                resource,
                role_id,
            )
        return revoked

    def get_role_permissions(self, role_id: str) -> list[Permission]:
        """Get all direct permissions for a role (excluding inherited)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM permissions WHERE role_id = ? AND inherited_from IS NULL",
                (role_id,),
            ).fetchall()

        return [self._row_to_permission(r) for r in rows]

    def get_effective_permissions(self, role_id: str) -> list[Permission]:
        """Get all effective permissions for a role including inherited ones."""
        # Get direct permissions
        permissions = {p.id: p for p in self.get_role_permissions(role_id)}

        # Get inherited permissions recursively
        visited: set[str] = set()
        to_visit: list[str] = [role_id]

        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue
            visited.add(current)

            # Get parent roles
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT parent_role_id FROM role_inheritance WHERE child_role_id = ?",
                    (current,),
                ).fetchall()

            for row in rows:
                parent_id = row["parent_role_id"]
                to_visit.append(parent_id)

                # Get parent's permissions as inherited
                with self._connect() as conn:
                    perm_rows = conn.execute(
                        "SELECT * FROM permissions WHERE role_id = ? AND inherited_from IS NULL",
                        (parent_id,),
                    ).fetchall()

                for perm_row in perm_rows:
                    parent_perm = self._row_to_permission(perm_row)
                    # Create inherited version
                    inherited = Permission(
                        id=str(uuid.uuid4()),
                        role_id=role_id,
                        resource=parent_perm.resource,
                        action=parent_perm.action,
                        effect=parent_perm.effect,
                        granted_at=parent_perm.granted_at,
                        granted_by=parent_perm.granted_by,
                        inherited_from=parent_id,
                        conditions=parent_perm.conditions,
                    )
                    permissions[inherited.id] = inherited

        return list(permissions.values())

    def check_permission(self, role_id: str, resource: str, action: ActionType) -> bool:
        """Check if a role has permission for an action on a resource.

        Deny always overrides allow. Returns True if allowed, False otherwise.
        """
        permissions = self.get_effective_permissions(role_id)

        # Check for explicit deny first (highest priority)
        for perm in permissions:
            if perm.resource == resource and perm.action == action:
                if perm.effect == Effect.DENY:
                    return False

        # Check for allow
        for perm in permissions:
            if perm.resource == resource and perm.action == action:
                if perm.effect == Effect.ALLOW:
                    return True

        # Check for wildcard permissions
        for perm in permissions:
            if perm.resource == "*" or perm.action == ActionType.ADMIN:
                if perm.effect == Effect.DENY:
                    return False
                elif perm.effect == Effect.ALLOW:
                    return True

        # Default: deny
        return False

    # ------------------------------------------------------------------
    # Public API: Role Inheritance
    # ------------------------------------------------------------------

    def inherit_role(self, child_role_id: str, parent_role_id: str, created_by: str) -> RoleInheritance:
        """Create an inheritance relationship: child inherits from parent."""
        inheritance_id = str(uuid.uuid4())
        now = self._now()

        inheritance = RoleInheritance(
            id=inheritance_id,
            child_role_id=child_role_id,
            parent_role_id=parent_role_id,
            created_at=now,
            created_by=created_by,
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO role_inheritance (id, child_role_id, parent_role_id, created_at, created_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    inheritance.id,
                    inheritance.child_role_id,
                    inheritance.parent_role_id,
                    inheritance.created_at,
                    inheritance.created_by,
                ),
            )
            conn.commit()

        _log.debug(
            "[PermissionMatrix] role %s now inherits from %s",
            child_role_id,
            parent_role_id,
        )
        return inheritance

    def remove_inheritance(self, child_role_id: str, parent_role_id: str) -> bool:
        """Remove an inheritance relationship."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM role_inheritance WHERE child_role_id = ? AND parent_role_id = ?",
                (child_role_id, parent_role_id),
            )
            conn.commit()

        removed = cursor.rowcount > 0
        if removed:
            _log.debug(
                "[PermissionMatrix] removed inheritance %s -> %s",
                child_role_id,
                parent_role_id,
            )
        return removed

    # ------------------------------------------------------------------
    # Public API: Conflict Detection
    # ------------------------------------------------------------------

    def detect_conflicts(self, role_id: str | None = None) -> list[PermissionConflict]:
        """Detect permission conflicts.

        Types of conflicts:
        - 'allow_deny': Both allow and deny for same resource/action
        - 'inheritance_cycle': Circular inheritance detected
        """
        conflicts: list[PermissionConflict] = []

        # Detect allow/deny conflicts
        permissions = self.get_effective_permissions(role_id) if role_id else []

        # Group by role, resource, action
        from collections import defaultdict

        grouped: dict[tuple[str, str, ActionType], list[Permission]] = defaultdict(list)
        for perm in permissions:
            key = (perm.role_id, perm.resource, perm.action)
            grouped[key].append(perm)

        for key, perms in grouped.items():
            if len(perms) > 1:
                has_allow = any(p.effect == Effect.ALLOW for p in perms)
                has_deny = any(p.effect == Effect.DENY for p in perms)

                if has_allow and has_deny:
                    conflict = PermissionConflict(
                        conflict_id=str(uuid.uuid4()),
                        role_id=key[0],
                        resource=key[1],
                        action=key[2],
                        conflicting_permissions=perms,
                        conflict_type="allow_deny",
                        detected_at=self._now(),
                    )
                    conflicts.append(conflict)

        # Detect inheritance cycles (using DFS)
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def _detect_cycle(role: str, path: list[str]) -> list[str] | None:
            visited.add(role)
            rec_stack.add(role)
            path.append(role)

            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT parent_role_id FROM role_inheritance WHERE child_role_id = ?",
                    (role,),
                ).fetchall()

            for row in rows:
                parent = row["parent_role_id"]
                if parent not in visited:
                    cycle = _detect_cycle(parent, path.copy())
                    if cycle:
                        return cycle
                elif parent in rec_stack:
                    # Found cycle
                    cycle_start = path.index(parent)
                    return path[cycle_start:] + [parent]

            rec_stack.remove(role)
            return None

        # Check for cycles starting from each role
        with self._connect() as conn:
            all_roles = conn.execute("SELECT DISTINCT child_role_id FROM role_inheritance").fetchall()

        for row in all_roles:
            start_role = row["child_role_id"]
            if start_role not in visited:
                cycle_path = _detect_cycle(start_role, [])
                if cycle_path:
                    # Create conflict for the cycle
                    conflict = PermissionConflict(
                        conflict_id=str(uuid.uuid4()),
                        role_id=cycle_path[0],
                        resource="*",
                        action=ActionType.CUSTOM,
                        conflicting_permissions=[],
                        conflict_type=f"inheritance_cycle: {' -> '.join(cycle_path)}",
                        detected_at=self._now(),
                    )
                    conflicts.append(conflict)

        return conflicts

    # ------------------------------------------------------------------
    # IPermissionChecker adapter methods
    # ------------------------------------------------------------------

    _ACTION_MAP: dict[PermissionAction, ActionType] = {
        PermissionAction.READ: ActionType.READ,
        PermissionAction.WRITE: ActionType.WRITE,
        PermissionAction.EXECUTE: ActionType.EXECUTE,
        PermissionAction.ADMIN: ActionType.ADMIN,
    }

    def check(self, role: str, resource: str, action: PermissionAction) -> bool:
        """Return True if the given role may perform *action* on *resource*.

        Satisfies :meth:`IPermissionChecker.check`.
        """
        at = self._ACTION_MAP.get(action, ActionType.CUSTOM)
        return self.check_permission(role, resource, at)

    def list_roles(self) -> list[RoleDefinition]:
        """Return all known role definitions.

        Satisfies :meth:`IPermissionChecker.list_roles`.
        """
        with self._connect() as conn:
            role_rows = conn.execute("SELECT DISTINCT role_id FROM permissions").fetchall()

        definitions: list[RoleDefinition] = []
        for row in role_rows:
            rid = row["role_id"]
            perms = self.get_role_permissions(rid)

            rules: list[PermissionRule] = []
            for p in perms:
                pa = next(
                    (k for k, v in self._ACTION_MAP.items() if v == p.action),
                    PermissionAction.EXECUTE,
                )
                rules.append(
                    PermissionRule(
                        role=rid,
                        resource_pattern=p.resource,
                        actions=[pa],
                        effect=p.effect.value,
                    )
                )

            # Resolve parent
            with self._connect() as conn:
                parent_row = conn.execute(
                    "SELECT parent_role_id FROM role_inheritance WHERE child_role_id = ? LIMIT 1",
                    (rid,),
                ).fetchone()
            parent = parent_row["parent_role_id"] if parent_row else None

            definitions.append(
                RoleDefinition(
                    role_id=rid,
                    name=rid,
                    permissions=rules,
                    parent_role=parent,
                )
            )
        return definitions
