"""Tests for Agent Runtime HTTP Server (server.py).

Covers: create_app, health endpoint, auth middleware, chat, run-task, logs.
"""

import json
from unittest.mock import MagicMock

import pytest

# ── FastAPI app creation (requires FastAPI) ─────────────────────────────────

FASTAPI_AVAILABLE = False
try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    pass


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI/TestClient not available")
class TestServerApp:
    def test_create_app(self):
        """App can be created without error."""
        from agent_runtime.server import create_app

        app = create_app()
        assert app.title == "Agent Runtime"

    def test_health_endpoint(self, monkeypatch):
        """Health endpoint returns status ok."""
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

    def test_health_endpoint_with_auth(self, monkeypatch):
        """Health endpoint is public even with auth enabled."""
        from agent_runtime.server import create_app

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "secret-token")
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_auth_middleware_blocks_unauthorized(self, monkeypatch):
        """Requests without auth token should be rejected."""
        from agent_runtime.server import create_app

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "secret-token")
        app = create_app()
        client = TestClient(app)
        resp = client.post("/chat", json={"message": "hello"})
        assert resp.status_code == 401

    def test_chat_endpoint_no_auth(self, monkeypatch):
        """Chat endpoint works when auth is disabled."""
        from agent_runtime.server import create_app

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "")
        app = create_app()
        client = TestClient(app)
        resp = client.post("/chat", json={"message": "hello"})
        # Should return 200 (even if LLM call fails)
        assert resp.status_code in (200, 500)

    def test_run_task_without_auth(self, monkeypatch):
        """run-task endpoint works when auth is disabled."""
        from agent_runtime.server import create_app

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "")
        app = create_app()
        client = TestClient(app)
        resp = client.post("/run-task", json={"prompt": "do something"})
        # LLM will fail (no API key), but the endpoint should respond
        assert resp.status_code in (200, 400, 500)

    def test_run_task_no_prompt(self, monkeypatch):
        """run-task without prompt should return 400."""
        from agent_runtime.server import create_app

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "")
        app = create_app()
        client = TestClient(app)
        resp = client.post("/run-task", json={})
        assert resp.status_code == 400

    def test_logs_endpoint(self, monkeypatch, tmp_path):
        """Logs endpoint returns execution logs."""
        from agent_runtime.server import create_app

        # Create a mock log file
        log_file = tmp_path / "execution_log.jsonl"
        log_file.write_text(json.dumps({"task_id": "test-001", "status": "ok", "summary": "done"}) + "\n")
        monkeypatch.setattr("agent_runtime.server.EXEC_LOG_FILE", log_file)
        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "")

        app = create_app()
        client = TestClient(app)
        resp = client.get("/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data
        assert data["total"] == 1

    def test_logs_endpoint_no_file(self, monkeypatch, tmp_path):
        """Logs endpoint with no log file returns empty list."""
        from agent_runtime.server import create_app

        log_file = tmp_path / "nonexistent.jsonl"
        monkeypatch.setattr("agent_runtime.server.EXEC_LOG_FILE", log_file)
        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "")

        app = create_app()
        client = TestClient(app)
        resp = client.get("/logs")
        assert resp.status_code == 200
        assert resp.json()["logs"] == []


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI/TestClient not available")
class TestServerAuth:
    def test_verify_auth_no_token(self, monkeypatch):
        """verify_auth with no AUTH_TOKEN configured skips auth."""
        from agent_runtime.server import _verify_auth

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "")
        # Should not raise
        mock_request = MagicMock()
        _verify_auth(mock_request)

    def test_verify_auth_missing_header(self, monkeypatch):
        """verify_auth with token configured but missing header raises."""
        from agent_runtime.server import _verify_auth
        from fastapi import HTTPException

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "secret")
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "invalid"
        with pytest.raises(HTTPException) as exc:
            _verify_auth(mock_request)
        assert exc.value.status_code == 401

    def test_verify_auth_valid(self, monkeypatch):
        """verify_auth with correct token should pass."""
        from agent_runtime.server import _verify_auth

        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "secret")
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer secret"
        # Should not raise
        _verify_auth(mock_request)


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI/TestClient not available")
class TestServerEndpoints:
    def test_task_history_endpoint(self, monkeypatch, tmp_path):
        """task-history endpoint returns filtered logs."""
        from agent_runtime.server import create_app

        log_file = tmp_path / "execution_log.jsonl"
        log_file.write_text(
            json.dumps({"task_id": "task-A", "status": "ok"})
            + "\n"
            + json.dumps({"task_id": "task-B", "status": "ok"})
            + "\n"
        )
        monkeypatch.setattr("agent_runtime.server.EXEC_LOG_FILE", log_file)
        monkeypatch.setattr("agent_runtime.server.AUTH_TOKEN", "")

        app = create_app()
        client = TestClient(app)
        resp = client.get("/task-history/task-A")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["logs"]) == 1
        assert data["logs"][0]["task_id"] == "task-A"
