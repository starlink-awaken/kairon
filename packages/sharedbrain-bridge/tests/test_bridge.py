"""Tests for sharedbrain-bridge — DEPRECATED stub behavior.

SharedBrain has been decommissioned (Phase 31, 2026-06-06).
These tests verify that all bridge classes function as safe no-op stubs.

Resolved debts: BYPASS-003, BYPASS-004, BYPASS-005
"""

import sys
from unittest.mock import patch

from sharedbrain_bridge.eu import PRICING, EUBridge
from sharedbrain_bridge.immune import ImmuneBridge
from sharedbrain_bridge.sync import SyncBridge

# ── EUBridge stub tests ───────────────────────────────────────


class TestEUBridgeInit:
    """EUBridge.__init__: no hardcoded default endpoints (BYPASS-004/005 resolved)"""

    def test_default_endpoints_empty(self):
        """Default endpoints are empty strings — no localhost hardcoding."""
        eb = EUBridge()
        assert eb.agora == ""
        assert eb.sb == ""

    def test_custom_endpoints_stored(self):
        """Custom endpoints are stored as-is."""
        eb = EUBridge(agora="http://custom:9999", sharedbrain="http://custom:8888")
        assert eb.agora == "http://custom:9999"
        assert eb.sb == "http://custom:8888"


class TestEUBridgeCheckBalance:
    """EUBridge.check_balance: always returns stub response (SharedBrain decommissioned)"""

    def test_returns_stub_response(self):
        """Returns safe stub with ok=False and error message."""
        eb = EUBridge()
        result = eb.check_balance("test-caller")
        assert result["ok"] is False
        assert "decommissioned" in result["error"].lower()
        assert result["balance"] == 1000
        assert result["limit"] == 1000

    def test_no_network_calls(self):
        """No network calls are made — stub is local-only."""
        eb = EUBridge(sharedbrain="http://test-sb:7421")
        # No need to mock urlopen — it should never be called
        result = eb.check_balance("test-caller")
        assert result["ok"] is False


class TestEUBridgeConsume:
    """EUBridge.consume: always returns failure (SharedBrain decommissioned)"""

    def test_consume_returns_failure(self):
        """consume always returns success=False."""
        eb = EUBridge()
        result = eb.consume("caller1", "minerva_research")
        assert result["success"] is False
        assert "decommissioned" in result["error"].lower()
        assert result["cost"] == PRICING["minerva_research"]

    def test_unknown_operation_uses_default_cost(self):
        """Unknown operation → cost=1 (default pricing fallback)."""
        eb = EUBridge()
        result = eb.consume("caller1", "unknown_op")
        assert result["cost"] == 1
        assert result["success"] is False


# ── ImmuneBridge stub tests ───────────────────────────────────


class TestImmuneBridgeInit:
    """ImmuneBridge.__init__: no hardcoded default endpoint (BYPASS-005 resolved)"""

    def test_default_endpoint_empty(self):
        """Default sb is empty string — no localhost:7421 hardcoding."""
        ib = ImmuneBridge()
        assert ib.sb == ""

    def test_custom_endpoint_stored(self):
        """Custom endpoint is stored."""
        ib = ImmuneBridge(sharedbrain="http://custom:9999")
        assert ib.sb == "http://custom:9999"


class TestImmuneBridgeAudit:
    """ImmuneBridge.audit: always returns stub response (SharedBrain decommissioned)"""

    def test_returns_unknown_risk(self):
        """Returns UNKNOWN risk with decommissioned error."""
        ib = ImmuneBridge()
        result = ib.audit("some content", title="test", source="unit-test")
        assert result["risk"] == "UNKNOWN"
        assert "decommissioned" in result["error"].lower()

    def test_no_network_calls(self):
        """No network calls are made."""
        ib = ImmuneBridge(sharedbrain="http://test-sb:7421")
        result = ib.audit("test content")
        assert result["risk"] == "UNKNOWN"


# ── SyncBridge stub tests ─────────────────────────────────────


class TestSyncBridgeInit:
    """SyncBridge.__init__: no hardcoded default endpoint (BYPASS-003/005 resolved)"""

    def test_default_endpoint_empty(self):
        """Default sb is empty string — no localhost:7421 hardcoding."""
        sb = SyncBridge()
        assert sb.sb == ""

    def test_custom_endpoint_stored(self):
        """Custom endpoint is stored."""
        sb = SyncBridge(sharedbrain="http://custom:9999")
        assert sb.sb == "http://custom:9999"


class TestSyncBridgeGetActiveOrgans:
    """SyncBridge.get_active_organs: always returns empty list (no organs path dependency)"""

    def test_returns_empty_list(self):
        """get_active_organs returns [] — organs directory no longer exists."""
        sb = SyncBridge()
        organs = sb.get_active_organs()
        assert organs == []

    def test_no_filesystem_dependency(self):
        """No SHAREDBRAIN_ORGANS path is referenced — BYPASS-003 resolved."""
        sb = SyncBridge()
        # Should not raise even if the old organs path doesn't exist
        organs = sb.get_active_organs()
        assert isinstance(organs, list)


class TestSyncBridgeBatchSync:
    """SyncBridge.batch_sync_to_memory: always returns failure (SharedBrain decommissioned)"""

    def test_sync_returns_failure(self):
        """batch_sync_to_memory returns synced=False."""
        sb = SyncBridge()
        organs = [{"name": "D_Memory", "status": "active"}]
        result = sb.batch_sync_to_memory(organs)
        assert result["synced"] is False
        assert "decommissioned" in result["error"].lower()
        assert result["count"] == 1
        assert result["fp"] == ""

    def test_sync_no_organs(self):
        """Empty organ list → count=0."""
        sb = SyncBridge()
        result = sb.batch_sync_to_memory([])
        assert result["synced"] is False
        assert result["count"] == 0

    def test_sync_none_organs_calls_get_active(self):
        """When organs=None, calls get_active_organs (returns [])."""
        sb = SyncBridge()
        result = sb.batch_sync_to_memory(None)
        assert result["synced"] is False
        assert result["count"] == 0


# ── CLI stub tests ────────────────────────────────────────────


class TestCLIMain:
    """sb-bridge CLI: dispatches subcommands (stub responses)"""

    def test_status_command(self, capsys):
        """status: prints active organ count (0 since SharedBrain decommissioned)."""
        from sharedbrain_bridge.cli import main

        with patch.object(sys, "argv", ["sb-bridge", "status"]):
            main()
        captured = capsys.readouterr()
        assert "Active organs" in captured.out

    def test_sync_command(self, capsys):
        """sync: prints stub JSON result."""
        from sharedbrain_bridge.cli import main

        with patch.object(sys, "argv", ["sb-bridge", "sync"]):
            main()
        captured = capsys.readouterr()
        assert "synced" in captured.out

    def test_eu_command(self, capsys):
        """eu: prints stub EU balance JSON."""
        from sharedbrain_bridge.cli import main

        with patch.object(sys, "argv", ["sb-bridge", "eu", "caller1"]):
            main()
        captured = capsys.readouterr()
        assert "balance" in captured.out

    def test_audit_command(self, capsys):
        """audit: prints stub audit JSON result."""
        from sharedbrain_bridge.cli import main

        with patch.object(sys, "argv", ["sb-bridge", "audit", "test content"]):
            main()
        captured = capsys.readouterr()
        assert "risk" in captured.out

    def test_unknown_command(self, capsys):
        """unknown command → prints usage."""
        from sharedbrain_bridge.cli import main

        with patch.object(sys, "argv", ["sb-bridge", "unknown-command"]):
            main()
        captured = capsys.readouterr()
        assert "Usage" in captured.out

    def test_no_args_defaults_to_status(self, capsys):
        """no args → cmd defaults to 'status'."""
        from sharedbrain_bridge.cli import main

        with patch.object(sys, "argv", ["sb-bridge"]):
            main()
        captured = capsys.readouterr()
        assert "Active organs" in captured.out
