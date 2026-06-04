"""Tests for kairon_lib.dynamic_role_assigner — DynamicRoleAssigner."""


import pytest

try:
    from kairon_lib.dynamic_role_assigner import DynamicRoleAssigner
except ImportError:
    pytestmark = pytest.mark.skip(reason="test requires archived kairon_lib module")  # type: ignore[name-defined]


class TestDynamicRoleAssigner:
    def test_assign_role(self):
        assigner = DynamicRoleAssigner()
        assignment = assigner.assign_role("agent-1", "reviewer", duration_seconds=3600)
        assert assignment.agent_id == "agent-1"
        assert assignment.role_id == "reviewer"
        assert assignment.expires_at is not None

    def test_assign_role_no_expiry(self):
        assigner = DynamicRoleAssigner()
        assignment = assigner.assign_role("agent-1", "admin")
        assert assignment.expires_at is None

    def test_has_role(self):
        assigner = DynamicRoleAssigner()
        assigner.assign_role("agent-1", "reviewer")
        assert assigner.has_role("agent-1", "reviewer") is True
        assert assigner.has_role("agent-1", "admin") is False

    def test_revoke_role(self):
        assigner = DynamicRoleAssigner()
        assigner.assign_role("agent-1", "reviewer")
        assigner.revoke_role("agent-1", "reviewer")
        assert assigner.has_role("agent-1", "reviewer") is False

    def test_get_roles(self):
        assigner = DynamicRoleAssigner()
        assigner.assign_role("agent-1", "reviewer")
        assigner.assign_role("agent-1", "admin")
        roles = assigner.get_roles("agent-1")
        assert sorted(roles) == ["admin", "reviewer"]

    def test_get_agents_with_role(self):
        assigner = DynamicRoleAssigner()
        assigner.assign_role("agent-1", "reviewer")
        assigner.assign_role("agent-2", "reviewer")
        assigner.assign_role("agent-2", "admin")
        agents = assigner.get_agents_with_role("reviewer")
        assert sorted(agents) == ["agent-1", "agent-2"]

    def test_expired_role_not_active(self):
        assigner = DynamicRoleAssigner()
        assigner.assign_role("agent-1", "temp-role", duration_seconds=-1)
        assert assigner.has_role("agent-1", "temp-role") is False

    def test_gc_expired(self):
        assigner = DynamicRoleAssigner()
        assigner.assign_role("agent-1", "perm")
        assigner.assign_role("agent-2", "temp", duration_seconds=-1)
        removed = assigner.gc_expired()
        assert removed == 1
        assert assigner.has_role("agent-1", "perm") is True

    def test_gc_expired_none(self):
        assigner = DynamicRoleAssigner()
        assigner.assign_role("agent-1", "perm")
        assert assigner.gc_expired() == 0

    def test_get_role_stats(self):
        assigner = DynamicRoleAssigner()
        assigner.assign_role("agent-1", "editor")
        assigner.assign_role("agent-2", "editor")
        assigner.assign_role("agent-1", "viewer")
        stats = assigner.get_role_stats()
        assert stats["total_assignments"] == 3
        assert stats["assignments_per_role"]["editor"] == 2
        assert stats["assignments_per_role"]["viewer"] == 1

    def test_list_assignments(self):
        assigner = DynamicRoleAssigner()
        assigner.assign_role("agent-1", "role1")
        assigner.assign_role("agent-2", "role2", duration_seconds=-1)  # expired
        assignments = assigner.list_assignments()
        assert len(assignments) == 1
        assert assignments[0].agent_id == "agent-1"

    def test_revoke_nonexistent_role(self):
        assigner = DynamicRoleAssigner()
        assigner.revoke_role("agent-1", "nonexistent")  # should not raise

    def test_assign_replaces_existing(self):
        assigner = DynamicRoleAssigner()
        a1 = assigner.assign_role("agent-1", "reviewer", scope="global")
        a2 = assigner.assign_role("agent-1", "reviewer", scope="global")
        # Second assignment replaces the first, but there should still be 1 active
        assert len(assigner._assignments) == 1
        assert a2 is not a1
