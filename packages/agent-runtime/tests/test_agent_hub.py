"""Tests for agent_hub module (merged from agent-hub package)."""

from __future__ import annotations

from agent_runtime.agent_hub import AgentHub, AgentInfo


class TestAgentHub:
    """Unit tests for AgentHub registration, discovery, and lifecycle."""

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _register_sample(hub: AgentHub) -> str:
        return hub.register_agent("test-agent", ["llm", "chat"], "http://localhost:8000")

    # -- registration -----------------------------------------------------

    def test_register_returns_id(self):
        hub = AgentHub()
        agent_id = self._register_sample(hub)
        assert isinstance(agent_id, str)
        assert len(agent_id) == 32  # uuid4 hex

    def test_register_stores_agent(self):
        hub = AgentHub()
        agent_id = self._register_sample(hub)
        info = hub.list_all()
        assert len(info) == 1
        assert info[0].id == agent_id

    def test_register_preserves_fields(self):
        hub = AgentHub()
        agent_id = hub.register_agent("vision-svc", ["vision", "ocr"], "http://localhost:9000")
        info = hub.list_all()[0]
        assert info.id == agent_id
        assert info.name == "vision-svc"
        assert info.capabilities == ["vision", "ocr"]
        assert info.endpoint == "http://localhost:9000"
        assert info.status == "active"

    def test_register_multiple_agents_unique_ids(self):
        hub = AgentHub()
        id1 = hub.register_agent("a", ["x"], "http://localhost:1")
        id2 = hub.register_agent("b", ["y"], "http://localhost:2")
        assert id1 != id2
        assert len(hub.list_all()) == 2

    def test_register_copies_capabilities(self):
        """Mutating the caller's list must not affect the stored AgentInfo."""
        hub = AgentHub()
        caps = ["a", "b"]
        hub.register_agent("test", caps, "http://localhost:1")
        caps.append("c")
        info = hub.list_all()[0]
        assert info.capabilities == ["a", "b"]

    # -- discovery --------------------------------------------------------

    def test_discover_all(self):
        hub = AgentHub()
        hub.register_agent("a", ["x"], "http://localhost:1")
        hub.register_agent("b", ["y"], "http://localhost:2")
        results = hub.discover_agents()
        assert len(results) == 2

    def test_discover_by_capability_match(self):
        hub = AgentHub()
        hub.register_agent("a", ["x", "z"], "http://localhost:1")
        hub.register_agent("b", ["y"], "http://localhost:2")
        results = hub.discover_agents(capability="x")
        assert len(results) == 1
        assert results[0].name == "a"

    def test_discover_by_capability_no_match(self):
        hub = AgentHub()
        hub.register_agent("a", ["x"], "http://localhost:1")
        results = hub.discover_agents(capability="zzz")
        assert results == []

    def test_discover_empty_registry(self):
        hub = AgentHub()
        assert hub.discover_agents() == []
        assert hub.discover_agents(capability="x") == []

    # -- deregistration ---------------------------------------------------

    def test_deregister_existing_returns_true(self):
        hub = AgentHub()
        agent_id = self._register_sample(hub)
        assert hub.deregister_agent(agent_id) is True

    def test_deregister_removes_agent(self):
        hub = AgentHub()
        agent_id = self._register_sample(hub)
        hub.deregister_agent(agent_id)
        assert hub.list_all() == []

    def test_deregister_unknown_returns_false(self):
        hub = AgentHub()
        assert hub.deregister_agent("nonexistent-id") is False

    def test_double_deregister_second_fails(self):
        hub = AgentHub()
        agent_id = self._register_sample(hub)
        assert hub.deregister_agent(agent_id) is True
        assert hub.deregister_agent(agent_id) is False

    # -- list_all ---------------------------------------------------------

    def test_list_all_empty_initially(self):
        assert AgentHub().list_all() == []

    # -- AgentInfo dataclass ----------------------------------------------

    def test_agent_info_fields_match_spec(self):
        info = AgentInfo(
            id="abc",
            name="demo",
            capabilities=["c1"],
            endpoint="http://localhost:8000",
        )
        assert info.id == "abc"
        assert info.name == "demo"
        assert info.capabilities == ["c1"]
        assert info.endpoint == "http://localhost:8000"
        assert info.status == "active"
        assert info.registered_at is not None
