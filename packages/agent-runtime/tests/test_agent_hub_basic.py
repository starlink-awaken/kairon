"""Basic tests for agent_hub module (merged from agent-hub package)."""

from __future__ import annotations

from agent_runtime.agent_hub import AgentHub, AgentInfo


class TestAgentHubBasic:
    """Core functionality and edge case tests."""

    def test_import(self):
        """Package imports correctly."""
        assert AgentHub is not None
        assert AgentInfo is not None

    def test_register_with_empty_capabilities(self):
        """Register agent with empty capabilities list."""
        hub = AgentHub()
        hub.register_agent("empty-cap", [], "http://localhost:1")
        info = hub.list_all()[0]
        assert info.capabilities == []

    def test_discover_with_empty_registry_all(self):
        """Discover all agents on empty registry returns empty list."""
        hub = AgentHub()
        assert hub.discover_agents() == []
        assert hub.discover_agents(capability="anything") == []

    def test_register_and_deregister_stress(self):
        """Multiple register/deregister cycles."""
        hub = AgentHub()
        ids = []
        for i in range(10):
            ids.append(hub.register_agent(f"a{i}", [f"cap{i}"], f"http://localhost:{i}"))
        assert len(hub.list_all()) == 10
        for aid in ids:
            assert hub.deregister_agent(aid) is True
        assert hub.list_all() == []

    def test_agent_info_immutability(self):
        """AgentInfo fields are typed correctly."""
        info = AgentInfo(
            id="test-id",
            name="test-name",
            capabilities=["a", "b"],
            endpoint="http://test",
        )
        assert isinstance(info.id, str)
        assert isinstance(info.name, str)
        assert isinstance(info.capabilities, list)
        assert info.status == "active"
        assert info.registered_at is not None
