"""Tests for Agent Runtime Tools (tools.py).

Covers: path sandbox, terminal_run, file_read, file_write, http_get, http_post,
sqlite_query, send_message, mcp_call, degrade state management.
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agent_runtime.tools import (
    Tools,
    _check_path_sandbox,
    _enter_agora_direct_mode,
    _is_agora_direct_mode,
    _record_agora_failure,
    _record_agora_success,
    reset_agora_degrade_state,
)

# ── Path sandbox tests ──────────────────────────────────────────────────────


class TestCheckPathSandbox:
    def test_allowed_workspace_path(self, monkeypatch):
        """Path under WORKSPACE should be allowed."""
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [Path(tmp)])
            test_path = Path(tmp) / "test_file.txt"
            test_path.touch()
            result = _check_path_sandbox(test_path)
            assert result == test_path.resolve()

    def test_allowed_nested_path(self, monkeypatch):
        """Path nested inside an allowed directory should pass."""
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "subdir" / "nested"
            nested.mkdir(parents=True)
            monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [Path(tmp)])
            result = _check_path_sandbox(nested)
            assert result == nested.resolve()

    def test_denied_path_raises(self, monkeypatch):
        """Path outside allowed dirs should raise PermissionError."""
        monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [Path("/tmp/allowed")])
        with pytest.raises(PermissionError):
            _check_path_sandbox(Path("/etc/passwd"))


# ── Tools class tests ─────────────────────────────────────────────────────


class TestToolsFileRead:
    def test_file_read_success(self, monkeypatch, tmp_path):
        """Read an existing file within allowed paths."""
        test_file = tmp_path / "test_read.txt"
        test_file.write_text("Hello, World!")
        monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [tmp_path])

        result = Tools.file_read(str(test_file))
        assert "error" not in result
        assert result["content"] == "Hello, World!"

    def test_file_read_not_found(self, monkeypatch, tmp_path):
        """Reading a nonexistent file should return error."""
        monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [tmp_path])
        result = Tools.file_read(str(tmp_path / "nonexistent.txt"))
        assert "error" in result

    def test_file_read_denied(self, monkeypatch):
        """Reading a file outside sandbox should return error."""
        monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [Path("/nonexistent")])
        result = Tools.file_read("/etc/passwd")
        assert "error" in result


class TestToolsFileWrite:
    def test_file_write_success(self, monkeypatch, tmp_path):
        """Write to a file within allowed paths."""
        test_file = tmp_path / "test_write.txt"
        monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [tmp_path])

        result = Tools.file_write(str(test_file), "test content")
        assert result.get("success") is True
        assert test_file.read_text() == "test content"

    def test_file_write_denied(self, monkeypatch):
        """Writing outside sandbox should return error."""
        monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [Path("/nonexistent")])
        result = Tools.file_write("/etc/denied.txt", "hack")
        assert "error" in result

    def test_file_write_creates_parent_dirs(self, monkeypatch, tmp_path):
        """Writing should create parent directories."""
        nested = tmp_path / "a" / "b" / "c" / "nested.txt"
        monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [tmp_path])
        result = Tools.file_write(str(nested), "content")
        assert result.get("success") is True
        assert nested.exists()


class TestToolsTerminalRun:
    def test_terminal_run_success(self, monkeypatch, tmp_path):
        """Successful command execution."""
        monkeypatch.setattr("agent_runtime.tools.ECOS_DIR", tmp_path)
        result = Tools.terminal_run("echo hello", _confirmed=True)
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    def test_terminal_run_failure(self, monkeypatch, tmp_path):
        """Command that fails should return non-zero exit code."""
        import sys

        monkeypatch.setattr("agent_runtime.tools.ECOS_DIR", tmp_path)
        result = Tools.terminal_run(f'"{sys.executable}" -c "import sys; sys.exit(42)"', _confirmed=True)
        assert result["exit_code"] == 42

    def test_terminal_run_timeout(self, monkeypatch, tmp_path):
        """Long-running command should timeout."""
        import sys

        monkeypatch.setattr("agent_runtime.tools.ECOS_DIR", tmp_path)
        result = Tools.terminal_run(f'"{sys.executable}" -c "import time; time.sleep(10)"', timeout=1, _confirmed=True)
        assert "Timed out" in result["stderr"]


class TestToolsHttpGet:
    @patch("urllib.request.urlopen")
    def test_http_get_success(self, mock_urlopen):
        """Successful HTTP GET request."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = Tools.http_get("http://example.com/api")
        assert result["status"] == 200
        assert "ok" in result["body"]

    @patch("urllib.request.urlopen")
    def test_http_get_error(self, mock_urlopen):
        """HTTP GET with connection error."""
        mock_urlopen.side_effect = Exception("Connection refused")
        result = Tools.http_get("http://example.com/nonexistent")
        assert "error" in result


class TestToolsHttpPost:
    @patch("urllib.request.urlopen")
    def test_http_post_success(self, mock_urlopen):
        """Successful HTTP POST request."""
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.read.return_value = b'{"id": 1}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = Tools.http_post("http://example.com/api", data={"key": "value"})
        assert result["status"] == 201

    @patch("urllib.request.urlopen")
    def test_http_post_error(self, mock_urlopen):
        """HTTP POST with error."""
        mock_urlopen.side_effect = Exception("Timeout")
        result = Tools.http_post("http://example.com/api")
        assert "error" in result


class TestToolsSqliteQuery:
    def test_sqlite_query_success(self, monkeypatch, tmp_path):
        """Query a real SQLite database."""
        import sqlite3

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'Alice')")
        conn.execute("INSERT INTO test VALUES (2, 'Bob')")
        conn.commit()
        conn.close()

        monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [tmp_path])
        result = Tools.sqlite_query(str(db_path), "SELECT * FROM test")
        assert "error" not in result
        assert result["count"] == 2

    def test_sqlite_query_not_found(self, monkeypatch, tmp_path):
        """Query a nonexistent database."""
        monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [tmp_path])
        result = Tools.sqlite_query(str(tmp_path / "nonexistent.db"), "SELECT 1")
        assert "error" in result

    def test_sqlite_query_denied(self, monkeypatch):
        """Query a database outside sandbox."""
        monkeypatch.setattr("agent_runtime.tools.ALLOWED_PATHS", [Path("/nonexistent")])
        result = Tools.sqlite_query("/etc/passwd", "SELECT 1")
        assert "error" in result


class TestToolsSendMessage:
    @patch("urllib.request.urlopen")
    def test_send_message_success(self, mock_urlopen, monkeypatch):
        """Successful message sending."""
        monkeypatch.setattr("agent_runtime.tools.ILINK_SEND_URL", "http://localhost:9999/send")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"ok": true}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = Tools.send_message(platform="weixin", text="Hello")
        assert result["status"] == 200

    def test_send_message_empty_text(self):
        """Sending empty text should return error."""
        result = Tools.send_message(text="")
        assert "error" in result

    @patch("urllib.request.urlopen")
    def test_send_message_error(self, mock_urlopen):
        """Message sending with network error."""
        mock_urlopen.side_effect = Exception("Network error")
        result = Tools.send_message(text="Hello")
        assert "error" in result


class TestToolsMcpCall:
    @patch("urllib.request.urlopen")
    def test_mcp_call_no_agora_fallback(self, mock_urlopen, monkeypatch):
        """When Agora is not configured, it falls back to direct mode."""
        monkeypatch.setattr("agent_runtime.tools.MCP_ENDPOINTS", {"kos": "http://localhost:7420/mcp"})
        reset_agora_degrade_state()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "result": {"content": [{"type": "text", "text": "direct result"}]},
            }
        ).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = Tools.mcp_call("kos", "run_indexer", {})
        assert "error" not in result
        assert result.get("direct") is True

    @patch("urllib.request.urlopen")
    def test_mcp_call_direct_mode_active(self, mock_urlopen, monkeypatch):
        """When in direct mode, skip Agora."""
        monkeypatch.setattr("agent_runtime.tools.MCP_ENDPOINTS", {"kos": "http://localhost:7420/mcp"})
        monkeypatch.setattr("agent_runtime.tools._agora_direct_mode_until", time.monotonic() + 300)

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "result": {"content": [{"type": "text", "text": "direct result"}]},
            }
        ).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = Tools.mcp_call("kos", "run_indexer")
        assert result.get("direct") is True


class TestToolsBuildRegistry:
    def test_build_tool_registry_has_keys(self):
        """build_tool_registry should return all expected tools."""
        tools = Tools()
        registry = tools.build_tool_registry()
        expected = ["terminal_run", "file_read", "file_write", "sqlite_query", "http_get", "http_post", "send_message"]
        for name in expected:
            assert name in registry, f"Missing tool: {name}"

    def test_build_tool_schemas(self):
        """build_tool_schemas should return OpenAI-format tool schemas."""
        tools = Tools()
        schemas = tools.build_tool_schemas()
        assert len(schemas) > 0
        for s in schemas:
            assert s["type"] == "function"
            assert "name" in s["function"]
            assert "description" in s["function"]
            assert "parameters" in s["function"]


# ── Agora degrade state tests ───────────────────────────────────────────────


class TestAgoraDegradeState:
    def setup_method(self):
        reset_agora_degrade_state()

    def test_initial_state_not_direct(self):
        assert not _is_agora_direct_mode()

    def test_enter_direct_mode(self):
        _enter_agora_direct_mode()
        assert _is_agora_direct_mode()

    def test_reset_state(self):
        _enter_agora_direct_mode()
        reset_agora_degrade_state()
        assert not _is_agora_direct_mode()

    def test_failure_counter_increments(self):
        assert not _is_agora_direct_mode()
        _record_agora_failure()
        assert not _is_agora_direct_mode()  # 1 failure < 2

    def test_failure_threshold_triggers_direct(self):
        _record_agora_failure()
        _record_agora_failure()  # 2 failures = threshold
        assert _is_agora_direct_mode()

    def test_success_resets_counter(self):
        _record_agora_failure()
        _record_agora_success()  # resets to 0
        _record_agora_failure()  # 1 failure < 2
        assert not _is_agora_direct_mode()
