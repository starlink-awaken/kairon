"""Tests for sharedbrain-bridge — EUBridge, ImmuneBridge, SyncBridge, and CLI."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sharedbrain_bridge.eu import DEFAULT_AGORA, DEFAULT_SB, PRICING, EUBridge
from sharedbrain_bridge.immune import ImmuneBridge
from sharedbrain_bridge.sync import SHAREDBRAIN_ORGANS, SyncBridge


# ── EUBridge tests ───────────────────────────────────────────

class TestEUBridgeInit:
    """EUBridge.__init__: stores server URLs"""

    def test_default_endpoints(self):
        eb = EUBridge()
        assert eb.agora == DEFAULT_AGORA
        assert eb.sb == DEFAULT_SB

    def test_custom_endpoints(self):
        eb = EUBridge(agora="http://custom:9999", sharedbrain="http://custom:8888")
        assert eb.agora == "http://custom:9999"
        assert eb.sb == "http://custom:8888"


class TestEUBridgeCheckBalance:
    """EUBridge.check_balance: queries SharedBrain for EU balance"""

    def test_success_response(self):
        """200 OK with balance data → returns balance with ok=True"""
        eb = EUBridge(sharedbrain="http://test-sb:7421")
        fake_resp = MagicMock()
        fake_resp.read.return_value = json.dumps({"balance": 500, "limit": 2000}).encode()
        fake_resp.__enter__.return_value = fake_resp

        with patch("sharedbrain_bridge.eu.urlopen", return_value=fake_resp):
            result = eb.check_balance("test-caller")

        assert result["balance"] == 500
        assert result["limit"] == 2000
        assert result["ok"] is True

    def test_server_error_fallback(self):
        """Connection error → fallback with ok=False"""
        eb = EUBridge(sharedbrain="http://test-sb:7421")

        with patch("sharedbrain_bridge.eu.urlopen", side_effect=ConnectionError("refused")):
            result = eb.check_balance("test-caller")

        assert result["balance"] == 100
        assert result["ok"] is False
        assert "refused" in result["error"]

    def test_timeout_fallback(self):
        """Timeout → fallback with ok=False"""
        eb = EUBridge(sharedbrain="http://test-sb:7421")

        with patch("sharedbrain_bridge.eu.urlopen", side_effect=TimeoutError("timed out")):
            result = eb.check_balance("test-caller")

        assert result["ok"] is False

    def test_caller_url_includes_param(self):
        """URL is constructed with caller parameter"""
        eb = EUBridge(sharedbrain="http://test-sb:7421")

        with patch("sharedbrain_bridge.eu.urlopen") as mock_urlopen:
            fake_resp = MagicMock()
            fake_resp.read.return_value = json.dumps({"balance": 100, "limit": 1000}).encode()
            fake_url = MagicMock()
            fake_url.__enter__.return_value = fake_resp
            mock_urlopen.return_value = fake_url

            eb.check_balance("my-agent")

            call_args = mock_urlopen.call_args[0][0].full_url
            assert "caller=my-agent" in call_args


class TestEUBridgeConsume:
    """EUBridge.consume: deducts EU for an operation"""

    def _mock_urlopen_ok(self, data: dict, status: int = 200):
        """Helper: create a mock urlopen that returns a JSON response."""
        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode()
        resp.status = status
        resp.__enter__.return_value = resp
        return resp

    def test_sufficient_balance(self):
        """Balance >= cost → consumes and returns success"""
        eb = EUBridge(sharedbrain="http://test-sb:7421")

        with patch("sharedbrain_bridge.eu.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                self._mock_urlopen_ok({"balance": 100, "limit": 1000}),
                self._mock_urlopen_ok({"balance": 90, "limit": 1000}, status=200),
            ]
            result = eb.consume("caller1", "minerva_research")

        assert result["success"] is True
        assert result["cost"] == PRICING["minerva_research"]

    def test_insufficient_balance(self):
        """Balance < cost → returns success=False"""
        eb = EUBridge(sharedbrain="http://test-sb:7421")

        with patch("sharedbrain_bridge.eu.urlopen", return_value=self._mock_urlopen_ok({"balance": 3, "limit": 1000})):
            result = eb.consume("caller1", "minerva_research")

        assert result["success"] is False
        assert "Insufficient" in result["error"]

    def test_unknown_operation_uses_default_cost(self):
        """Operation not in PRICING → cost=1"""
        eb = EUBridge(sharedbrain="http://test-sb:7421")

        with patch("sharedbrain_bridge.eu.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                self._mock_urlopen_ok({"balance": 100, "limit": 1000}),
                self._mock_urlopen_ok({}, status=200),
            ]
            result = eb.consume("caller1", "unknown_op")

        assert result["cost"] == 1

    def test_consume_http_error(self):
        """Consume endpoint fails → success=False"""
        eb = EUBridge(sharedbrain="http://test-sb:7421")

        with patch("sharedbrain_bridge.eu.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                self._mock_urlopen_ok({"balance": 100, "limit": 1000}),
                ConnectionError("consume endpoint down"),
            ]
            result = eb.consume("caller1", "minerva_research")

        assert result["success"] is False
        assert "down" in result["error"]


# ── ImmuneBridge tests ───────────────────────────────────────

class TestImmuneBridgeInit:
    """ImmuneBridge.__init__: stores SharedBrain URL"""

    def test_default_endpoint(self):
        ib = ImmuneBridge()
        assert ib.sb == "http://localhost:7421"

    def test_custom_endpoint(self):
        ib = ImmuneBridge(sharedbrain="http://custom:7421")
        assert ib.sb == "http://custom:7421"


class TestImmuneBridgeAudit:
    """ImmuneBridge.audit: sends content for risk audit"""

    def test_successful_audit(self):
        """200 OK → returns parsed response"""
        ib = ImmuneBridge(sharedbrain="http://test-sb:7421")
        fake_resp = MagicMock()
        fake_resp.read.return_value = json.dumps({"risk": "LOW", "score": 0.1}).encode()
        fake_resp.__enter__.return_value = fake_resp

        with patch("sharedbrain_bridge.immune.urlopen", return_value=fake_resp):
            result = ib.audit("safe content", title="test", source="unit-test")

        assert result["risk"] == "LOW"
        assert result["score"] == 0.1

    def test_error_fallback(self):
        """Connection error → UNKNOWN risk with error"""
        ib = ImmuneBridge(sharedbrain="http://test-sb:7421")

        with patch("sharedbrain_bridge.immune.urlopen", side_effect=ConnectionError("server down")):
            result = ib.audit("test content")

        assert result["risk"] == "UNKNOWN"
        assert "server down" in result["error"]

    def test_empty_content_still_sent(self):
        """Empty content is still sent in the payload"""
        ib = ImmuneBridge(sharedbrain="http://test-sb:7421")

        with patch("sharedbrain_bridge.immune.urlopen") as mock_urlopen:
            fake_resp = MagicMock()
            fake_resp.read.return_value = json.dumps({"risk": "UNKNOWN"}).encode()
            fake_url = MagicMock()
            fake_url.__enter__.return_value = fake_resp
            mock_urlopen.return_value = fake_url

            ib.audit("")

            sent_data = json.loads(mock_urlopen.call_args[0][0].data)
            assert sent_data["content"] == ""
            assert sent_data["title"] == ""


# ── SyncBridge tests ─────────────────────────────────────────

class TestSyncBridgeInit:
    """SyncBridge.__init__: stores SharedBrain URL"""

    def test_default_endpoint(self):
        sb = SyncBridge()
        assert sb.sb == "http://localhost:7421"


class TestSyncBridgeGetActiveOrgans:
    """SyncBridge.get_active_organs: lists D_* directories as organs"""

    def test_organs_dir_not_exists(self, tmp_path):
        """When SHAREDBRAIN_ORGANS doesn't exist → empty list"""
        fake_path = tmp_path / "nonexistent"
        sb = SyncBridge()
        with patch("sharedbrain_bridge.sync.SHAREDBRAIN_ORGANS", fake_path):
            organs = sb.get_active_organs()
        assert organs == []

    def test_returns_d_only_directories(self, tmp_path):
        """Only D_* dirs are returned, not other dirs"""
        organs_dir = tmp_path / "SharedBrain" / "organs"
        organs_dir.mkdir(parents=True)
        (organs_dir / "D_Memory").mkdir()
        (organs_dir / "D_Economy").mkdir()
        (organs_dir / "tools").mkdir()  # should be excluded
        (organs_dir / "config.yaml").write_text("")  # file, excluded

        sb = SyncBridge()
        with patch("sharedbrain_bridge.sync.SHAREDBRAIN_ORGANS", organs_dir):
            organs = sb.get_active_organs()

        names = {o["name"] for o in organs}
        assert "D_Memory" in names
        assert "D_Economy" in names
        assert "tools" not in names

    def test_status_from_organ_status_file(self, tmp_path):
        """.organ_status content is read as status; 'active' if absent"""
        organs_dir = tmp_path / "SharedBrain" / "organs"
        organs_dir.mkdir(parents=True)

        (organs_dir / "D_Active").mkdir()
        (organs_dir / "D_Standby").mkdir()
        (organs_dir / "D_Standby" / ".organ_status").write_text("standby")

        sb = SyncBridge()
        with patch("sharedbrain_bridge.sync.SHAREDBRAIN_ORGANS", organs_dir):
            organs = sb.get_active_organs()

        status_map = {o["name"]: o["status"] for o in organs}
        assert status_map["D_Active"] == "active"
        assert status_map["D_Standby"] == "standby"


class TestSyncBridgeBatchSync:
    """SyncBridge.batch_sync_to_memory: syncs organs to SharedBrain"""

    def test_sync_with_explicit_organs(self):
        """Explicit organ list → sends with fingerprint"""
        sb = SyncBridge(sharedbrain="http://test-sb:7421")
        fake_resp = MagicMock()
        fake_resp.status = 200
        fake_resp.__enter__.return_value = fake_resp

        organs = [{"name": "D_Memory", "status": "active"}]
        with patch("sharedbrain_bridge.sync.urlopen", return_value=fake_resp):
            result = sb.batch_sync_to_memory(organs)

        assert result["synced"] is True
        assert result["count"] == 1
        assert "fp" in result

    def test_sync_no_organs(self):
        """No organs → still syncs with count=0"""
        sb = SyncBridge(sharedbrain="http://test-sb:7421")
        result = sb.batch_sync_to_memory([])
        assert result["synced"] in (True, False)
        assert result["count"] == 0

    def test_sync_http_error(self):
        """Connection error → synced=False"""
        sb = SyncBridge(sharedbrain="http://test-sb:7421")
        organs = [{"name": "D_Memory", "status": "active"}]

        with patch("sharedbrain_bridge.sync.urlopen", side_effect=ConnectionError("sync down")):
            result = sb.batch_sync_to_memory(organs)

        assert result["synced"] is False
        assert result["count"] == 1
        assert "sync down" in result["error"]

    def test_fingerprint_changes_with_data(self):
        """Different organ data → different fingerprints"""
        sb = SyncBridge(sharedbrain="http://test-sb:7421")
        fake_resp = MagicMock()
        fake_resp.status = 200
        fake_resp.__enter__.return_value = fake_resp

        organs_a = [{"name": "D_Memory", "status": "active"}]
        organs_b = [{"name": "D_Economy", "status": "active"}]

        with patch("sharedbrain_bridge.sync.urlopen", return_value=fake_resp):
            result_a = sb.batch_sync_to_memory(organs_a)
            result_b = sb.batch_sync_to_memory(organs_b)

        assert result_a["fp"] != result_b["fp"]

    def test_sync_calls_get_active_organs_when_none(self):
        """When organs=None, falls back to get_active_organs()"""
        sb = SyncBridge(sharedbrain="http://test-sb:7421")

        fake_resp = MagicMock()
        fake_resp.status = 200
        fake_resp.__enter__.return_value = fake_resp

        with (
            patch("sharedbrain_bridge.sync.urlopen", return_value=fake_resp),
            patch.object(sb, "get_active_organs", return_value=[{"name": "D_Memory", "status": "active"}]) as mock_get,
        ):
            sb.batch_sync_to_memory()
            mock_get.assert_called_once()


# ── CLI tests ────────────────────────────────────────────────

class TestCLIMain:
    """sb-bridge CLI: dispatches subcommands"""

    def test_status_command(self, capsys):
        """status: prints active organ count"""
        sb = SyncBridge()
        with patch("sharedbrain_bridge.cli.SyncBridge.get_active_organs", return_value=[]):
            with patch("sharedbrain_bridge.cli.SyncBridge", return_value=sb):
                from sharedbrain_bridge.cli import main
                with patch.object(sys, "argv", ["sb-bridge", "status"]):
                    main()
        captured = capsys.readouterr()
        assert "Active organs" in captured.out

    def test_sync_command(self, capsys):
        """sync: prints JSON result"""
        sb = SyncBridge()
        with patch("sharedbrain_bridge.cli.SyncBridge", return_value=sb):
            with patch.object(sb, "batch_sync_to_memory", return_value={"synced": True, "count": 0, "fp": "abc"}):
                from sharedbrain_bridge.cli import main
                with patch.object(sys, "argv", ["sb-bridge", "sync"]):
                    main()
        captured = capsys.readouterr()
        assert "synced" in captured.out

    def test_eu_command(self, capsys):
        """eu: prints EU balance JSON"""
        eb = EUBridge()
        with patch("sharedbrain_bridge.cli.EUBridge", return_value=eb):
            with patch.object(eb, "check_balance", return_value={"balance": 100, "ok": True}):
                from sharedbrain_bridge.cli import main
                with patch.object(sys, "argv", ["sb-bridge", "eu", "caller1"]):
                    main()
        captured = capsys.readouterr()
        assert "balance" in captured.out

    def test_eu_command_default_caller(self, capsys):
        """eu without caller arg → uses 'kairon' as default"""
        eb = EUBridge()
        with patch("sharedbrain_bridge.cli.EUBridge", return_value=eb):
            with patch.object(eb, "check_balance", return_value={"balance": 100, "ok": True}) as mock_check:
                from sharedbrain_bridge.cli import main
                with patch.object(sys, "argv", ["sb-bridge", "eu"]):
                    main()
                mock_check.assert_called_with("kairon")

    def test_audit_command(self, capsys):
        """audit: prints audit JSON result"""
        ib = ImmuneBridge()
        with patch("sharedbrain_bridge.cli.ImmuneBridge", return_value=ib):
            with patch.object(ib, "audit", return_value={"risk": "LOW"}):
                from sharedbrain_bridge.cli import main
                with patch.object(sys, "argv", ["sb-bridge", "audit", "test content"]):
                    main()
        captured = capsys.readouterr()
        assert "risk" in captured.out

    def test_unknown_command(self, capsys):
        """unknown command → prints usage"""
        from sharedbrain_bridge.cli import main
        with patch.object(sys, "argv", ["sb-bridge", "unknown-command"]):
            main()
        captured = capsys.readouterr()
        assert "Usage" in captured.out

    def test_no_args_defaults_to_status(self, capsys):
        """no args → cmd defaults to 'status'"""
        sb = SyncBridge()
        with patch("sharedbrain_bridge.cli.SyncBridge", return_value=sb):
            from sharedbrain_bridge.cli import main
            with patch.object(sys, "argv", ["sb-bridge"]):
                main()
        captured = capsys.readouterr()
        assert "Active organs" in captured.out
