"""Tests for kairon_lib.rbac — RBAC permission model types."""

from kairon_lib.rbac import (
    PERMISSION_ACTION_TO_ACTION_TYPE,
    AccessDecision,
    AccessRule,
    ActionType,
    AuditEntry,
    Effect,
    Permission,
    PermissionAction,
    PermissionConflict,
    PermissionRule,
    RoleDefinition,
    RoleInheritance,
    RolePermissionSet,
)


class TestPermissionAction:
    """Tests for PermissionAction enum."""

    def test_all_actions(self):
        assert PermissionAction.READ == "read"
        assert PermissionAction.WRITE == "write"
        assert PermissionAction.EXECUTE == "execute"
        assert PermissionAction.ADMIN == "admin"
        assert len(PermissionAction) == 4

    def test_str_enum(self):
        assert isinstance(PermissionAction.READ, str)


class TestEffect:
    """Tests for Effect enum."""

    def test_values(self):
        assert Effect.ALLOW == "allow"
        assert Effect.DENY == "deny"
        assert len(Effect) == 2


class TestActionType:
    """Tests for ActionType enum (superset of PermissionAction)."""

    def test_all_types(self):
        assert len(ActionType) == 6
        assert ActionType.DELETE == "delete"
        assert ActionType.CUSTOM == "custom"

    def test_is_superset_of_permission_action(self):
        for pa in PermissionAction:
            assert ActionType(pa.value) == ActionType[pa.name]

    def test_mapping_table(self):
        assert len(PERMISSION_ACTION_TO_ACTION_TYPE) == 4
        assert PERMISSION_ACTION_TO_ACTION_TYPE[PermissionAction.READ] == ActionType.READ
        assert PERMISSION_ACTION_TO_ACTION_TYPE[PermissionAction.ADMIN] == ActionType.ADMIN


class TestPermissionRule:
    """Tests for PermissionRule dataclass."""

    def test_default_effect(self):
        rule = PermissionRule(role="admin", resource_pattern="/", actions=[PermissionAction.READ])
        assert rule.effect == "allow"

    def test_explicit_deny(self):
        rule = PermissionRule(
            role="guest", resource_pattern="/admin/*", actions=[PermissionAction.WRITE], effect="deny"
        )
        assert rule.effect == "deny"
        assert rule.role == "guest"
        assert rule.resource_pattern == "/admin/*"
        assert rule.actions == [PermissionAction.WRITE]


class TestRoleDefinition:
    """Tests for RoleDefinition dataclass."""

    def test_basic_definition(self):
        role = RoleDefinition(role_id="admin", name="Administrator", permissions=[])
        assert role.role_id == "admin"
        assert role.name == "Administrator"
        assert role.parent_role is None

    def test_with_parent(self):
        role = RoleDefinition(
            role_id="editor",
            name="Editor",
            permissions=[],
            parent_role="admin",
        )
        assert role.parent_role == "admin"


class TestPermission:
    """Tests for Permission dataclass."""

    def test_basic_permission(self):
        p = Permission(
            id="p1",
            role_id="admin",
            resource="/api/",
            action=ActionType.READ,
            effect=Effect.ALLOW,
            granted_at="2026-01-01T00:00:00Z",
            granted_by="system",
        )
        assert p.id == "p1"
        assert p.inherited_from is None
        assert p.conditions is None

    def test_to_dict(self):
        p = Permission(
            id="p1",
            role_id="admin",
            resource="/api/",
            action=ActionType.READ,
            effect=Effect.ALLOW,
            granted_at="now",
            granted_by="sys",
            inherited_from="parent_role",
            conditions={"ip_whitelist": ["10.0.0.0/8"]},
        )
        d = p.to_dict()
        assert d["id"] == "p1"
        assert d["action"] == "read"
        assert d["effect"] == "allow"
        assert d["inherited_from"] == "parent_role"
        assert d["conditions"] == {"ip_whitelist": ["10.0.0.0/8"]}

    def test_inherited_permission(self):
        p = Permission(
            id="p2",
            role_id="viewer",
            resource="/public/",
            action=ActionType.READ,
            effect=Effect.ALLOW,
            granted_at="now",
            granted_by="sys",
            inherited_from="reader",
        )
        assert p.inherited_from == "reader"

    def test_custom_action_type(self):
        p = Permission(
            id="p3",
            role_id="admin",
            resource="/custom/",
            action=ActionType.CUSTOM,
            effect=Effect.ALLOW,
            granted_at="now",
            granted_by="sys",
        )
        assert p.action == ActionType.CUSTOM


class TestRoleInheritance:
    """Tests for RoleInheritance dataclass."""

    def test_basic_inheritance(self):
        ri = RoleInheritance(
            id="inh1",
            child_role_id="editor",
            parent_role_id="admin",
            created_at="2026-01-01T00:00:00Z",
            created_by="system",
        )
        assert ri.child_role_id == "editor"
        assert ri.parent_role_id == "admin"

    def test_to_dict(self):
        ri = RoleInheritance(
            id="inh1",
            child_role_id="editor",
            parent_role_id="admin",
            created_at="now",
            created_by="sys",
        )
        d = ri.to_dict()
        assert d["child_role_id"] == "editor"
        assert d["parent_role_id"] == "admin"


class TestPermissionConflict:
    """Tests for PermissionConflict dataclass."""

    def test_allow_deny_conflict(self):
        p1 = Permission(
            id="p1",
            role_id="admin",
            resource="/api/",
            action=ActionType.WRITE,
            effect=Effect.ALLOW,
            granted_at="now",
            granted_by="sys",
        )
        p2 = Permission(
            id="p2",
            role_id="admin",
            resource="/api/",
            action=ActionType.WRITE,
            effect=Effect.DENY,
            granted_at="now",
            granted_by="sys",
        )
        conflict = PermissionConflict(
            conflict_id="c1",
            role_id="admin",
            resource="/api/",
            action=ActionType.WRITE,
            conflicting_permissions=[p1, p2],
            conflict_type="allow_deny",
            detected_at="now",
        )
        assert conflict.conflict_type == "allow_deny"
        assert len(conflict.conflicting_permissions) == 2

    def test_to_dict(self):
        p = Permission(
            id="p1",
            role_id="admin",
            resource="/api/",
            action=ActionType.READ,
            effect=Effect.ALLOW,
            granted_at="now",
            granted_by="sys",
        )
        conflict = PermissionConflict(
            conflict_id="c1",
            role_id="admin",
            resource="/api/",
            action=ActionType.READ,
            conflicting_permissions=[p],
            conflict_type="inheritance_cycle: admin -> editor -> admin",
            detected_at="now",
        )
        d = conflict.to_dict()
        assert d["conflict_type"].startswith("inheritance_cycle")
        assert len(d["conflicting_permissions"]) == 1


class TestAccessRule:
    """Tests for AccessRule dataclass (from role_rbac)."""

    def test_basic_rule(self):
        rule = AccessRule(resource="/api/*", actions=["read", "write"])
        assert rule.resource == "/api/*"
        assert rule.actions == ["read", "write"]

    def test_slots_enabled(self):
        rule = AccessRule(resource="/", actions=["read"])
        # slots=True means no __dict__
        assert not hasattr(rule, "__dict__")


class TestRolePermissionSet:
    """Tests for RolePermissionSet dataclass."""

    def test_default_values(self):
        rps = RolePermissionSet(role_id="admin", permissions=[])
        assert rps.role_id == "admin"
        assert rps.max_eu_budget == float("inf")
        assert rps.time_window is None
        assert rps.spent_eu == 0.0

    def test_with_budget(self):
        rps = RolePermissionSet(
            role_id="analyst",
            permissions=[AccessRule(resource="/data/*", actions=["read"])],
            max_eu_budget=100.0,
            time_window=(9, 17),
        )
        assert rps.max_eu_budget == 100.0
        assert rps.time_window == (9, 17)


class TestAccessDecision:
    """Tests for AccessDecision dataclass."""

    def test_allow(self):
        d = AccessDecision(allowed=True, reason="Access granted")
        assert d.allowed is True
        assert d.reason == "Access granted"

    def test_deny(self):
        d = AccessDecision(allowed=False, reason="No matching permission rule")
        assert d.allowed is False

    def test_slots_enabled(self):
        d = AccessDecision(allowed=True, reason="ok")
        assert not hasattr(d, "__dict__")


class TestAuditEntry:
    """Tests for AuditEntry dataclass."""

    def test_basic_entry(self):
        entry = AuditEntry(
            role_id="admin",
            resource="/api/users",
            action="read",
            allowed=True,
            reason="Access granted",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert entry.role_id == "admin"
        assert entry.action == "read"
        assert entry.allowed is True

    def test_slots_enabled(self):
        entry = AuditEntry(
            role_id="admin",
            resource="/",
            action="read",
            allowed=True,
            reason="ok",
        )
        assert not hasattr(entry, "__dict__")
