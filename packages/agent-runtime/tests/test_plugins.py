"""Tests for plugin_manager — PluginManager lifecycle, sandbox, permissions."""

from agent_runtime.plugins import PluginDef, PluginManager, PluginSandboxConfig


class TestPluginDefinition:
    """PluginDef dataclass defaults."""

    def test_default_construction(self):
        p = PluginDef(name="test-plugin")
        assert p.name == "test-plugin"
        assert p.version == "1.0.0"
        assert p.capabilities == []
        assert p.permissions == []
        assert p.state == "registered"

    def test_custom_values(self):
        p = PluginDef(
            name="analytics",
            version="2.1.0",
            description="Analytics plugin",
            capabilities=["reporting", "charting"],
            permissions=["read:data"],
        )
        assert p.capabilities == ["reporting", "charting"]
        assert "read:data" in p.permissions


class TestPluginManagerLifecycle:
    """PluginManager register/load/activate/disable lifecycle."""

    def test_register_and_status(self):
        mgr = PluginManager()
        mgr.register("echo", version="0.1.0")
        status = mgr.get_status()
        assert status["total"] == 1
        assert status["by_state"]["registered"] == 1

    def test_register_then_load(self):
        mgr = PluginManager()
        mgr.register("echo")
        assert mgr.load("echo") is True

    def test_load_nonexistent_returns_false(self):
        mgr = PluginManager()
        assert mgr.load("ghost") is False

    def test_full_lifecycle(self):
        mgr = PluginManager()
        mgr.register("worker", version="1.0.0")
        assert mgr.load("worker") is True
        assert mgr.activate("worker") is True
        assert mgr.disable("worker") is True

    def test_activate_without_load_returns_false(self):
        mgr = PluginManager()
        mgr.register("novice")
        assert mgr.activate("novice") is False

    def test_list_active(self):
        mgr = PluginManager()
        mgr.register("p1")
        mgr.register("p2")
        mgr.load("p1")
        mgr.activate("p1")
        active = mgr.list_active()
        assert len(active) == 1
        assert active[0].name == "p1"

    def test_disable(self):
        mgr = PluginManager()
        mgr.register("p")
        mgr.load("p")
        mgr.activate("p")
        mgr.disable("p")
        assert mgr.list_active() == []

    def test_get_status_with_multiple_states(self):
        mgr = PluginManager()
        mgr.register("a")
        mgr.register("b")
        mgr.register("c")
        mgr.load("a")
        mgr.load("b")
        mgr.activate("a")
        status = mgr.get_status()
        assert status["total"] == 3
        assert status["by_state"]["registered"] == 1
        assert status["by_state"]["loaded"] == 1
        assert status["by_state"]["active"] == 1


class TestPluginManagerSandbox:
    """PluginManager sandbox configuration."""

    def test_default_sandbox_restrictive(self):
        mgr = PluginManager()
        sandbox = mgr.get_sandbox("unknown")
        assert sandbox.allow_filesystem is False
        assert sandbox.allow_network is False
        assert sandbox.allow_subprocess is False
        assert sandbox.max_memory_mb == 128

    def test_configure_sandbox(self):
        mgr = PluginManager()
        config = PluginSandboxConfig(
            allow_filesystem=True,
            allow_network=True,
            max_memory_mb=256,
        )
        mgr.configure_sandbox("data-plugin", config)
        retrieved = mgr.get_sandbox("data-plugin")
        assert retrieved.allow_filesystem is True
        assert retrieved.allow_network is True
        assert retrieved.max_memory_mb == 256


class TestPluginManagerPermissions:
    """PluginManager permission checking."""

    def test_check_permission_present(self):
        mgr = PluginManager()
        mgr.register("safe", permissions=["read:fs", "write:fs"])
        assert mgr.check_permission("safe", "read:fs") is True

    def test_check_permission_missing(self):
        mgr = PluginManager()
        mgr.register("restricted", permissions=["read:fs"])
        assert mgr.check_permission("restricted", "write:fs") is False

    def test_check_permission_nonexistent_plugin(self):
        mgr = PluginManager()
        assert mgr.check_permission("phantom", "any") is False
