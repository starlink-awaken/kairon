"""Basic tests for sharedbrain-bridge package."""

from __future__ import annotations

from sharedbrain_bridge import cli, eu, gbrain_client, immune, sync
from sharedbrain_bridge.eu import DEFAULT_AGORA, DEFAULT_SB, EUBridge
from sharedbrain_bridge.immune import ImmuneBridge
from sharedbrain_bridge.sync import SyncBridge


class TestSharedBrainBridgeBasic:
    """Core functionality and edge case tests."""

    def test_imports(self):
        """All expected modules are importable."""
        assert EUBridge is not None
        assert ImmuneBridge is not None
        assert SyncBridge is not None

    def test_eu_bridge_defaults(self):
        """EUBridge with default endpoints."""
        eb = EUBridge()
        assert eb.agora == DEFAULT_AGORA
        assert eb.sb == DEFAULT_SB

    def test_eu_bridge_custom(self):
        """EUBridge with custom endpoints."""
        eb = EUBridge(agora="http://custom:1111", sharedbrain="http://custom:2222")
        assert eb.agora == "http://custom:1111"
        assert eb.sb == "http://custom:2222"

    def test_immune_bridge_init(self):
        """ImmuneBridge initializes."""
        ib = ImmuneBridge()
        assert ib is not None

    def test_sync_bridge_init(self):
        """SyncBridge initializes."""
        sb = SyncBridge()
        assert sb is not None

    def test_cli_module(self):
        """CLI module is importable."""
        assert cli is not None

    def test_gbrain_client_module(self):
        """gbrain_client module is importable."""
        assert gbrain_client is not None

    def test_eu_module_functions(self):
        """EU module has key functions."""
        assert hasattr(eu, "EUBridge")

    def test_immune_module_functions(self):
        """Immune module has key functions."""
        assert hasattr(immune, "ImmuneBridge")

    def test_sync_module_functions(self):
        """Sync module has key functions."""
        assert hasattr(sync, "SyncBridge")
