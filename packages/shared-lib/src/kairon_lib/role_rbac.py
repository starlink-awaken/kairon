from __future__ import annotations

import fnmatch
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class Permission:
    resource: str
    actions: list[str]


@dataclass(slots=True)
class RolePermissionSet:
    role_id: str
    permissions: list[Permission]
    max_eu_budget: float = float("inf")
    time_window: tuple[int, int] | None = None
    spent_eu: float = 0.0


@dataclass(slots=True)
class AccessDecision:
    allowed: bool
    reason: str


@dataclass(slots=True)
class AuditEntry:
    role_id: str
    resource: str
    action: str
    allowed: bool
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class RoleRBAC:
    """Minimal role-based access control with budget and audit tracking."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._lock = threading.RLock()
        self._role_permissions: dict[str, RolePermissionSet] = {}
        self._audit_log: list[AuditEntry] = []
        self._db_path = str(db_path) if db_path is not None else ":memory:"
        self._conn = sqlite3.connect(self._db_path)
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS role_rbac_meta (
                role_id TEXT PRIMARY KEY,
                max_eu_budget REAL NOT NULL,
                spent_eu REAL NOT NULL,
                window_start INTEGER,
                window_end INTEGER
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id TEXT NOT NULL,
                resource TEXT NOT NULL,
                action TEXT NOT NULL,
                allowed INTEGER NOT NULL,
                reason TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_role ON audit_events(role_id)")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def define_permissions(
        self,
        role_id: str,
        permissions: list[Permission],
        max_eu: float = float("inf"),
        time_window: tuple[int, int] | None = None,
    ) -> RolePermissionSet:
        permission_set = RolePermissionSet(
            role_id=role_id,
            permissions=list(permissions),
            max_eu_budget=max_eu,
            time_window=time_window,
        )
        with self._lock:
            self._role_permissions[role_id] = permission_set
            window_start = None if time_window is None else time_window[0]
            window_end = None if time_window is None else time_window[1]
            self._conn.execute(
                """
                INSERT INTO role_rbac_meta(role_id, max_eu_budget, spent_eu, window_start, window_end)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(role_id) DO UPDATE SET
                    max_eu_budget=excluded.max_eu_budget,
                    spent_eu=excluded.spent_eu,
                    window_start=excluded.window_start,
                    window_end=excluded.window_end
                """,
                (role_id, max_eu, 0.0, window_start, window_end),
            )
            self._conn.commit()
        return permission_set

    def get_permissions(self, role_id: str) -> RolePermissionSet | None:
        with self._lock:
            return self._role_permissions.get(role_id)

    def remove_permissions(self, role_id: str) -> bool:
        with self._lock:
            removed = self._role_permissions.pop(role_id, None)
            self._conn.execute("DELETE FROM role_rbac_meta WHERE role_id = ?", (role_id,))
            self._conn.commit()
            return removed is not None

    def list_roles(self) -> list[str]:
        with self._lock:
            return sorted(self._role_permissions)

    def check_access(self, role_id: str, resource: str, action: str) -> AccessDecision:
        with self._lock:
            permission_set = self._role_permissions.get(role_id)
            if permission_set is None:
                decision = AccessDecision(False, f"Role {role_id!r} is not defined")
            else:
                matched = any(
                    fnmatch.fnmatch(resource, permission.resource) and action in permission.actions
                    for permission in permission_set.permissions
                )
                decision = AccessDecision(
                    matched,
                    "Access granted" if matched else "No matching permission rule",
                )
            entry = AuditEntry(
                role_id=role_id,
                resource=resource,
                action=action,
                allowed=decision.allowed,
                reason=decision.reason,
            )
            self._audit_log.append(entry)
            self._conn.execute(
                """
                INSERT INTO audit_events(role_id, resource, action, allowed, reason, timestamp)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (entry.role_id, entry.resource, entry.action, entry.allowed, entry.reason, entry.timestamp),
            )
            self._conn.commit()
            return decision

    def check_budget(self, role_id: str, amount: float) -> AccessDecision:
        with self._lock:
            permission_set = self._role_permissions.get(role_id)
            if permission_set is None:
                return AccessDecision(False, f"Role {role_id!r} is not defined")
            remaining = permission_set.max_eu_budget - permission_set.spent_eu
            if amount <= remaining:
                return AccessDecision(True, f"Budget available: {remaining:.2f} EU remaining")
            return AccessDecision(False, f"EU budget exceeded by {amount - remaining:.2f}")

    def record_spending(self, role_id: str, amount: float) -> float:
        with self._lock:
            permission_set = self._role_permissions.get(role_id)
            if permission_set is None:
                return 0.0
            permission_set.spent_eu += amount
            self._conn.execute(
                "UPDATE role_rbac_meta SET spent_eu = ? WHERE role_id = ?",
                (permission_set.spent_eu, role_id),
            )
            self._conn.commit()
            return self.get_remaining_budget(role_id)

    def get_remaining_budget(self, role_id: str) -> float:
        with self._lock:
            permission_set = self._role_permissions.get(role_id)
            if permission_set is None:
                return 0.0
            return max(permission_set.max_eu_budget - permission_set.spent_eu, 0.0)

    def reset_budget(self, role_id: str) -> None:
        with self._lock:
            permission_set = self._role_permissions.get(role_id)
            if permission_set is None:
                return
            permission_set.spent_eu = 0.0
            self._conn.execute(
                "UPDATE role_rbac_meta SET spent_eu = 0.0 WHERE role_id = ?",
                (role_id,),
            )
            self._conn.commit()

    def check_time_window(self, role_id: str) -> AccessDecision:
        with self._lock:
            permission_set = self._role_permissions.get(role_id)
            if permission_set is None:
                return AccessDecision(False, f"Role {role_id!r} is not defined")
            if permission_set.time_window is None:
                return AccessDecision(True, "No time restriction configured")
            start, end = permission_set.time_window
            current_hour = datetime.now(UTC).hour
            if start == end:
                allowed = True
            elif start < end:
                allowed = start <= current_hour < end
            else:
                allowed = current_hour >= start or current_hour < end
            if allowed:
                return AccessDecision(True, f"Current UTC hour {current_hour} is within allowed window")
            return AccessDecision(False, f"Current UTC hour {current_hour} is outside allowed window")

    def get_audit_log(self, role_id: str | None = None) -> list[AuditEntry]:
        with self._lock:
            if role_id is None:
                return list(self._audit_log)
            return [entry for entry in self._audit_log if entry.role_id == role_id]

    def get_stats(self) -> dict[str, int]:
        with self._lock:
            allowed_count = sum(1 for entry in self._audit_log if entry.allowed)
            denied_count = sum(1 for entry in self._audit_log if not entry.allowed)
            return {
                "total_audit_entries": len(self._audit_log),
                "allowed_count": allowed_count,
                "denied_count": denied_count,
            }
