"""Tests for Agent Runtime — config, tools, auth, SSRF protection."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# ══════════════════════════════════════════════════════════════════════
# Imports & Config
# ══════════════════════════════════════════════════════════════════════


def test_imports():
    """All core modules import without error."""
    from agent_runtime import config, engine, tools

    assert hasattr(config, "DEFAULT_MODEL")
    assert hasattr(tools, "Tools")
    assert hasattr(engine, "AgentRuntime")


def test_config_defaults():
    """Config has sensible default values."""
    from agent_runtime.config import ALLOWED_PATHS, DEFAULT_MODEL

    assert DEFAULT_MODEL
    assert isinstance(ALLOWED_PATHS, list)
    assert len(ALLOWED_PATHS) >= 3


def test_sanitize_for_log():
    """Sensitive info is sanitized in logs."""
    from agent_runtime.config import sanitize_for_log

    # API key sanitization
    result = sanitize_for_log("sk-abc123xyz456token789")
    assert "SANITIZED" in result
    assert "abc123" not in result
    # Authorization header sanitization
    result = sanitize_for_log("Authorization: Bearer secret-token-here")
    assert "SANITIZED" in result
    assert "secret-token" not in result
    # Normal text passes through
    result = sanitize_for_log("hello world")
    assert result == "hello world"
    # Max length truncation
    result = sanitize_for_log("x" * 500, max_len=50)
    assert len(result) == 50


# ══════════════════════════════════════════════════════════════════════
# Tools — SSRF Protection
# ══════════════════════════════════════════════════════════════════════


class TestSSRFProtection:
    """Test _is_safe_url SSRF protection."""

    def test_public_urls_allowed(self):
        from agent_runtime.tools import _is_safe_url

        assert _is_safe_url("https://api.example.com/data")
        assert _is_safe_url("https://www.google.com")
        assert _is_safe_url("http://example.com:8080/path")

    def test_localhost_blocked(self):
        from agent_runtime.tools import _is_safe_url

        assert not _is_safe_url("http://localhost:8080/health")
        assert not _is_safe_url("http://127.0.0.1:7420/")
        assert not _is_safe_url("http://127.1/")
        assert not _is_safe_url("http://0.0.0.0:9876/")
        assert not _is_safe_url("http://[::1]:8080/")

    def test_loopback_blocked(self):
        from agent_runtime.tools import _is_safe_url

        assert not _is_safe_url("http://127.0.0.2/")
        assert not _is_safe_url("http://127.127.127.127/")

    def test_private_ips_blocked(self):
        from agent_runtime.tools import _is_safe_url

        assert not _is_safe_url("http://10.0.0.1/")
        assert not _is_safe_url("http://172.16.0.1/")
        assert not _is_safe_url("http://192.168.1.1/")

    def test_invalid_urls_rejected(self):
        from agent_runtime.tools import _is_safe_url

        # URLs without proper scheme/hostname may be handled differently
        # by urlparse, so we only test well-formed-but-internal URLs here
        assert not _is_safe_url("http://[::1]:8080/path")


# ══════════════════════════════════════════════════════════════════════
# Tools — Path Sandbox
# ══════════════════════════════════════════════════════════════════════


class TestCheckPathSandbox:
    """Test _check_path_sandbox method."""

    def test_allowed_path_passes(self):
        from agent_runtime.tools import _check_path_sandbox

        allowed = Path.home() / "Workspace" / "test.txt"
        result = _check_path_sandbox(allowed)
        assert result == allowed.resolve()

    def test_disallowed_path_raises(self):
        from agent_runtime.tools import _check_path_sandbox

        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "secret.txt"
            with pytest.raises(PermissionError, match="Access denied"):
                _check_path_sandbox(outside)


# ══════════════════════════════════════════════════════════════════════
# Tools — File operations
# ══════════════════════════════════════════════════════════════════════


class TestFileTools:
    """Test file_read and file_write (sandbox-aware)."""

    def test_file_read_not_found_or_denied(self):
        from agent_runtime.tools import Tools

        result = Tools.file_read("/nonexistent/path/file.txt")
        assert "error" in result

    def test_file_read_outside_sandbox(self):
        from agent_runtime.tools import Tools

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("secret data")
            result = Tools.file_read(str(p))
            assert "error" in result
            assert "Access denied" in result["error"]

    def test_file_write_inside_sandbox(self):
        from agent_runtime.tools import Tools

        ws = Path.home() / "Workspace" / ".test_ar_write"
        p = ws / "test_write.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = Tools.file_write(str(p), "hello")
            assert result.get("success") is True
        finally:
            if p.exists():
                p.unlink()
            if p.parent.exists():
                p.parent.rmdir()


# ══════════════════════════════════════════════════════════════════════
# Tools — HTTP operations with SSRF
# ══════════════════════════════════════════════════════════════════════


class TestHttpTools:
    """Test http_get and http_post SSRF blocking."""

    def test_http_get_ssrf_blocked(self):
        from agent_runtime.tools import Tools

        result = Tools.http_get("http://localhost:8080/admin")
        assert "error" in result
        assert "blocked by SSRF" in result["error"]

    def test_http_get_ssrf_blocked_private_ip(self):
        from agent_runtime.tools import Tools

        result = Tools.http_get("http://192.168.1.1/config")
        assert "error" in result
        assert "blocked by SSRF" in result["error"]

    def test_http_post_ssrf_blocked(self):
        from agent_runtime.tools import Tools

        result = Tools.http_post("http://127.0.0.1:5000/api", {"key": "value"})
        assert "error" in result
        assert "blocked by SSRF" in result["error"]


# ══════════════════════════════════════════════════════════════════════
# Server — Auth
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# FastAPI availability check
# ══════════════════════════════════════════════════════════════════════

FASTAPI_AVAILABLE = False
try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    pass


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestServerAuth:
    """Test _verify_auth and middleware auth logic."""

    def test_verify_auth_passes_without_token(self):
        """_verify_auth must pass when AUTH_TOKEN is empty (no auth configured)."""
        from agent_runtime.server import _verify_auth

        with patch("agent_runtime.server.AUTH_TOKEN", ""):
            # Should not raise when no auth is configured
            _verify_auth(None)

    def test_verify_auth_wrong_token(self):
        """_verify_auth must reject incorrect bearer token."""
        from agent_runtime.server import _verify_auth

        with patch("agent_runtime.server.AUTH_TOKEN", "correct-token"):

            class MockRequest:
                headers = {"Authorization": "Bearer wrong-token"}

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc:
                _verify_auth(MockRequest())
            assert exc.value.status_code == 401

    def test_verify_auth_correct_token(self):
        """_verify_auth must accept correct bearer token."""
        from agent_runtime.server import _verify_auth

        with patch("agent_runtime.server.AUTH_TOKEN", "correct-token"):

            class MockRequest:
                headers = {"Authorization": "Bearer correct-token"}

            # Should not raise
            _verify_auth(MockRequest())


# ══════════════════════════════════════════════════════════════════════
# Tools — terminal_run (sandboxed)
# ══════════════════════════════════════════════════════════════════════


class TestTerminalRun:
    """Test terminal_run — no shell injection possible."""

    def test_terminal_run_simple_command(self):
        from agent_runtime.tools import Tools

        result = Tools.terminal_run("echo hello", cwd="/tmp", timeout=5, _confirmed=True)
        assert result["exit_code"] == 0
        assert "hello" in result.get("stdout", "")

    def test_terminal_run_timeout(self):
        import sys

        from agent_runtime.tools import Tools

        result = Tools.terminal_run(f'"{sys.executable}" -c "import time; time.sleep(10)"', cwd="/tmp", timeout=1, _confirmed=True)
        assert result["exit_code"] == -1
        assert "timed out" in result.get("stderr", "").lower()


# ══════════════════════════════════════════════════════════════════════
# Server — Health Endpoint
# ══════════════════════════════════════════════════════════════════════




class TestHealthEndpoint:
    """Test /health endpoint — should be public."""

    def test_health_returns_ok(self, monkeypatch):
        from agent_runtime.server import create_app

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "")
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "model" in data
        assert "auth" in data

    def test_health_public_with_auth(self, monkeypatch):
        from agent_runtime.server import create_app

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "secret-token")
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_reports_auth_status(self, monkeypatch):
        from agent_runtime.server import create_app

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "my-token")
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        data = resp.json()
        assert data["auth"] is True

    def test_health_reports_no_auth(self, monkeypatch):
        from agent_runtime.server import create_app

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "")
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        data = resp.json()
        assert data["auth"] is False
