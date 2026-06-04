from __future__ import annotations

"""RBAC + PermissionGuard - Unified permission checking and audit for kairon.

Based on D_Immunity: permission_guard.py + rbac.py.
Matrix: 4 roles (admin/developer/reviewer/executor) x 4 resources
(file/memory/workspace/audit) x 4 actions (read/write/execute/delete).
"""

import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

_log = logging.getLogger(__name__)

ROLES: set[str] = {"admin", "developer", "reviewer", "executor"}
RESOURCES: set[str] = {"file", "memory", "workspace", "audit"}
ACTIONS: set[str] = {"read", "write", "execute", "delete"}


def _build_default_policy() -> dict[str, dict[str, set[str]]]:
    admin: dict[str, set[str]] = {r: set(ACTIONS) for r in RESOURCES}
    return {
        "admin": admin,
        "developer": {
            "file": {"read", "write", "execute"},
            "memory": {"read", "write"},
            "workspace": {"read", "write", "execute"},
            "audit": {"read", "execute"},
        },
        "reviewer": {
            "file": {"read"},
            "memory": {"read"},
            "workspace": {"read"},
            "audit": {"read", "execute"},
        },
        "executor": {
            "file": {"read"},
            "memory": {"write", "read"},
            "workspace": {"execute", "read", "write"},
            "audit": {"read"},
        },
    }


DEFAULT_POLICY: dict[str, dict[str, set[str]]] = _build_default_policy()


class PermissionResult(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"


@dataclass
class AuditEvent:
    """Immutable audit record for a permission check."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    principal: str = ""
    action: str = ""
    resource: str = ""
    result: str = ""
    reason: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id, "timestamp": self.timestamp,
            "principal": self.principal, "action": self.action,
            "resource": self.resource, "result": self.result,
            "reason": self.reason, "context": self.context,
        }


class PermissionGuard:
    """Unified RBAC permission guard with audit logging.

        guard = PermissionGuard()
        result, reason = guard.check_permission("developer", "write", "file")
        if result != PermissionResult.ALLOWED:
            raise PermissionError(reason)
    """

    _MAX_AUDIT_EVENTS: int = 10_000
    _CACHE_TTL: float = 300.0

    def __init__(self, policy: dict[str, dict[str, set[str]]] | None = None) -> None:
        self._policy = policy or DEFAULT_POLICY
        self._audit_events: deque[AuditEvent] = deque(maxlen=self._MAX_AUDIT_EVENTS)
        self._cache: dict[str, tuple[dict[str, set[str]], float]] = {}

    def check_permission(
        self, principal: str, action: str, resource: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[PermissionResult, str]:
        """Check if *principal* may perform *action* on *resource*.

        Returns (result, reason) tuple. *reason* is empty on ALLOWED.
        """
        role = (principal or "").strip().lower()
        act = (action or "").strip().lower()
        res = (resource or "").strip().lower()

        if not role or not act or not res:
            return self._deny(role, act, res, "invalid input", context)
        if role not in ROLES:
            return self._deny(role, act, res, f"unknown role: {role}", context)
        if res not in RESOURCES:
            return self._deny(role, act, res, f"unknown resource: {res}", context)
        if act not in ACTIONS:
            return self._deny(role, act, res, f"unknown action: {act}", context)

        allowed = self._get_allowed_actions(role, res)
        if act not in allowed:
            return self._deny(role, act, res, "denied by policy", context)

        return self._allow(role, act, res, context)

    def get_audit_log(self, principal: str | None = None, limit: int = 100) -> list[AuditEvent]:
        events = self._audit_events
        if principal:
            p = principal.strip().lower()
            events = [e for e in events if e.principal.lower() == p]  # type: ignore[assignment]
        return list(events)[-limit:]

    def _get_allowed_actions(self, role: str, resource: str) -> set[str]:
        if role in self._cache:
            cached, expire_at = self._cache[role]
            if time.monotonic() < expire_at:
                return cached.get(resource, set())
            del self._cache[role]
        perms = self._policy.get(role, {})
        self._cache[role] = (perms, time.monotonic() + self._CACHE_TTL)
        return perms.get(resource, set())

    def _allow(self, role: str, act: str, res: str, ctx: dict[str, Any] | None) -> tuple[PermissionResult, str]:
        self._audit_events.append(AuditEvent(
            principal=role, action=act, resource=res,
            result="allowed", context=ctx or {},
        ))
        return PermissionResult.ALLOWED, ""

    def _deny(self, role: str, act: str, res: str, reason: str, ctx: dict[str, Any] | None) -> tuple[PermissionResult, str]:
        _log.warning("Access denied: principal=%s action=%s resource=%s reason=%s", role, act, res, reason)
        self._audit_events.append(AuditEvent(
            principal=role, action=act, resource=res,
            result="denied", reason=reason, context=ctx or {},
        ))
        return PermissionResult.DENIED, reason


def create_permission_guard(policy: dict[str, dict[str, set[str]]] | None = None) -> PermissionGuard:
    return PermissionGuard(policy=policy)


__all__ = [
    "ACTIONS", "AuditEvent", "DEFAULT_POLICY", "PermissionGuard",
    "PermissionResult", "RESOURCES", "ROLES", "create_permission_guard",
]
