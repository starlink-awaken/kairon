"""Tests for Agent Runtime engine.

Covers: AgentRuntime, _call_llm, _execute_tool, run_task, _log_execution,
_build_alert_message, _resolve_api_key.
"""

import json

from agent_runtime.engine import (
    AgentRuntime,
    _build_alert_message,
    _log_execution,
    _resolve_api_key,
)


class TestAgentRuntime:
    def test_init_default_model(self):
        rt = AgentRuntime()
        assert rt.model == "deepseek-v4-flash"

    def test_init_custom_model(self):
        rt = AgentRuntime(model="gpt-4")
        assert rt.model == "gpt-4"

    def test_init_has_tools(self):
        rt = AgentRuntime()
        assert hasattr(rt, "tools")
        assert hasattr(rt, "_tool_registry")

    def test_execute_tool_unknown(self):
        rt = AgentRuntime()
        result = rt._execute_tool(
            {
                "id": "call-1",
                "function": {"name": "nonexistent_tool", "arguments": "{}"},
            }
        )
        assert "Unknown tool" in result["content"]


class TestResolveApiKey:
    def test_env_var_direct(self, monkeypatch):
        """AGENT_RUNTIME_API_KEY should be returned first."""
        monkeypatch.setenv("AGENT_RUNTIME_API_KEY", "sk-direct-key")
        result = _resolve_api_key()
        assert result == "sk-direct-key"

    def test_deepseek_api_key(self, monkeypatch):
        """DEEPSEEK_API_KEY should be used if AGENT_RUNTIME_API_KEY is not set."""
        monkeypatch.delenv("AGENT_RUNTIME_API_KEY", raising=False)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-key")
        result = _resolve_api_key()
        assert result == "sk-deepseek-key"

    def test_openai_api_key(self, monkeypatch):
        """OPENAI_API_KEY should be used as fallback."""
        monkeypatch.delenv("AGENT_RUNTIME_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-key")
        result = _resolve_api_key()
        assert result == "sk-openai-key"

    def test_no_key_found(self, monkeypatch, tmp_path):
        """When no keys are set, returns empty string."""
        monkeypatch.delenv("AGENT_RUNTIME_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Mock Path.home() to a temp dir so file fallbacks don't interfere
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        result = _resolve_api_key()
        assert result == ""


class TestBuildAlertMessage:
    def test_with_result(self):
        result = {"error": "API timeout", "turns": 5, "usage": {"total_tokens": 100}, "result": "partial output"}
        msg = _build_alert_message("task-001", result)
        assert "task-001" in msg
        assert "API timeout" in msg
        assert "5" in msg
        assert "100" in msg

    def test_with_empty_result(self):
        result = {"error": "unknown error"}
        msg = _build_alert_message("task-002", result)
        assert "task-002" in msg


class TestLogExecution:
    def test_log_execution(self, monkeypatch, tmp_path):
        """_log_execution writes a JSONL entry."""
        log_file = tmp_path / "execution_log.jsonl"
        monkeypatch.setattr("agent_runtime.engine.EXEC_LOG_FILE", log_file)

        _log_execution(
            task_id="test-task",
            status="ok",
            summary="Task completed",
            result={"turns": 3, "usage": {"total_tokens": 50}},
            duration_sec=1.5,
        )

        assert log_file.exists()
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["task_id"] == "test-task"
        assert entry["status"] == "ok"
        assert entry["turns"] == 3
        assert entry["tokens_used"] == 50
        assert entry["duration_sec"] == 1.5

    def test_log_execution_no_usage(self, monkeypatch, tmp_path):
        """Log entry handles missing usage data."""
        log_file = tmp_path / "execution_log.jsonl"
        monkeypatch.setattr("agent_runtime.engine.EXEC_LOG_FILE", log_file)

        _log_execution(
            task_id="test-task-2",
            status="error",
            summary="Failed",
            result={},
            duration_sec=0.5,
        )

        entry = json.loads(log_file.read_text())
        assert entry["tokens_used"] == 0
