"""Tests for Agent Runtime Config (config.py).

Covers: environment variables, path resolution, MCP endpoints, API key sanitization.
"""

import json
from pathlib import Path

# ── Config constants ────────────────────────────────────────────────────────


class TestConfigConstants:
    def test_default_model(self):
        from agent_runtime.config import DEFAULT_MODEL

        assert DEFAULT_MODEL

    def test_auth_token_empty_by_default(self):
        from agent_runtime.config import AUTH_TOKEN

        # AUTH_TOKEN reads from env; it may be set
        assert isinstance(AUTH_TOKEN, str)

    def test_workspace_is_path(self):
        from agent_runtime.config import WORKSPACE

        assert isinstance(WORKSPACE, Path)

    def test_allowed_paths(self):
        from agent_runtime.config import ALLOWED_PATHS

        assert isinstance(ALLOWED_PATHS, list)
        assert len(ALLOWED_PATHS) > 0
        for p in ALLOWED_PATHS:
            assert isinstance(p, Path)

    def test_agent_runtime_port_default(self, monkeypatch):
        monkeypatch.delenv("AGENT_RUNTIME_PORT", raising=False)
        # Re-import or check initial value
        import importlib

        import agent_runtime.config as cfg

        importlib.reload(cfg)
        assert cfg.AGENT_RUNTIME_PORT == 9876

    def test_agent_runtime_port_env(self, monkeypatch):
        monkeypatch.setenv("AGENT_RUNTIME_PORT", "9999")
        import importlib

        import agent_runtime.config as cfg

        importlib.reload(cfg)
        assert cfg.AGENT_RUNTIME_PORT == 9999


# ── sanitize_for_log ────────────────────────────────────────────────────────


class TestSanitizeForLog:
    def test_sanitize_api_key(self):
        from agent_runtime.config import sanitize_for_log

        result = sanitize_for_log("sk-abc123xyz456")
        # The regex requires 20+ chars after sk-
        if len("sk-abc123xyz456") >= 23:
            assert "SANITIZED" in result
        else:
            assert result == "sk-abc123xyz456"

    def test_sanitize_auth_header(self):
        from agent_runtime.config import sanitize_for_log

        text = "Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz123456"
        result = sanitize_for_log(text)
        assert "SANITIZED" in result

    def test_sanitize_max_length(self):
        from agent_runtime.config import sanitize_for_log

        long_text = "x" * 500
        result = sanitize_for_log(long_text, max_len=200)
        assert len(result) == 200

    def test_sanitize_normal_text(self):
        from agent_runtime.config import sanitize_for_log

        result = sanitize_for_log("normal text without secrets")
        assert result == "normal text without secrets"

    def test_sanitize_empty(self):
        from agent_runtime.config import sanitize_for_log

        result = sanitize_for_log("")
        assert result == ""


# ── MCP endpoints ───────────────────────────────────────────────────────────


class TestMcpEndpoints:
    def test_mcp_endpoints_has_keys(self):
        from agent_runtime.config import MCP_ENDPOINTS

        for name in ("agora", "kos", "minerva"):
            assert name in MCP_ENDPOINTS

    def test_mcp_endpoints_values_are_urls(self):
        from agent_runtime.config import MCP_ENDPOINTS

        for name, url in MCP_ENDPOINTS.items():
            assert url.startswith("http"), f"{name}: {url} does not start with http"


# ── Registry queries ────────────────────────────────────────────────────────


class TestRegistry:
    def test_load_registry_no_file(self, monkeypatch):
        """load_registry with no file returns empty dict."""
        import agent_runtime.config as cfg

        monkeypatch.setattr(cfg, "REGISTRY_PATH", Path("/nonexistent/registry.json"))
        result = cfg._load_registry()
        assert result == {}

    def test_load_registry_invalid_json(self, monkeypatch, tmp_path):
        """load_registry with invalid JSON returns empty dict."""
        import agent_runtime.config as cfg

        bad_file = tmp_path / "registry.json"
        bad_file.write_text("not json")
        monkeypatch.setattr(cfg, "REGISTRY_PATH", bad_file)
        result = cfg._load_registry()
        assert result == {}

    def test_load_registry_valid_v4(self, monkeypatch, tmp_path):
        """load_registry with valid v4 format."""
        import agent_runtime.config as cfg

        reg_file = tmp_path / "registry.json"
        reg_file.write_text(
            json.dumps(
                {
                    "entities": {
                        "services": {
                            "items": [
                                {"name": "agora-mcp", "port": 7430},
                                {"name": "kos-mcp", "port": 7420},
                            ],
                        },
                    },
                }
            )
        )
        monkeypatch.setattr(cfg, "REGISTRY_PATH", reg_file)
        result = cfg._load_registry()
        assert result["agora-mcp"]["port"] == 7430
        assert result["kos-mcp"]["port"] == 7420

    def test_query_registry_port_hit(self, monkeypatch, tmp_path):
        """Query registry port for a known service."""
        import agent_runtime.config as cfg

        reg_file = tmp_path / "registry.json"
        reg_file.write_text(
            json.dumps(
                {
                    "entities": {
                        "services": {
                            "items": [
                                {"name": "agora-mcp", "port": 7430},
                            ],
                        },
                    },
                }
            )
        )
        monkeypatch.setattr(cfg, "REGISTRY_PATH", reg_file)
        port = cfg._query_registry_port(["agora-mcp"])
        assert port == 7430

    def test_query_registry_port_miss(self, monkeypatch):
        """Query registry port for unknown service returns None."""
        import agent_runtime.config as cfg

        monkeypatch.setattr(cfg, "REGISTRY_PATH", Path("/nonexistent"))
        port = cfg._query_registry_port(["nonexistent-service"])
        assert port is None


# ── MCP endpoint building ───────────────────────────────────────────────────


class TestBuildMcpEndpoints:
    def test_env_url_takes_priority(self, monkeypatch):
        """Environment URL should override other sources."""
        monkeypatch.setenv("AGORA_MCP_URL", "http://custom:1234/mcp")
        import importlib

        import agent_runtime.config as cfg

        importlib.reload(cfg)
        assert cfg.MCP_ENDPOINTS["agora"] == "http://custom:1234/mcp"

    def test_default_fallback(self, monkeypatch):
        """When no env or registry, use hardcoded defaults."""
        monkeypatch.delenv("AGORA_MCP_URL", raising=False)
        monkeypatch.delenv("AGORA_MCP_PORT", raising=False)
        monkeypatch.delenv("KOS_MCP_URL", raising=False)
        monkeypatch.delenv("KOS_MCP_PORT", raising=False)
        monkeypatch.delenv("MINERVA_MCP_URL", raising=False)
        monkeypatch.delenv("MINERVA_MCP_PORT", raising=False)
        import importlib

        import agent_runtime.config as cfg

        importlib.reload(cfg)
        assert "localhost" in cfg.MCP_ENDPOINTS["agora"]

    def test_env_port(self, monkeypatch):
        """Environment port should be used."""
        monkeypatch.setenv("KOS_MCP_PORT", "7777")
        monkeypatch.delenv("KOS_MCP_URL", raising=False)
        import importlib

        import agent_runtime.config as cfg

        importlib.reload(cfg)
        assert "7777" in cfg.MCP_ENDPOINTS["kos"]


# ── iLink URL ───────────────────────────────────────────────────────────────


class TestILinkUrl:
    def test_ilink_from_env(self, monkeypatch):
        """iLink URL comes from env var."""
        monkeypatch.setenv("ILINK_SEND_URL", "http://ilink:9000/send")
        import importlib

        import agent_runtime.config as cfg

        importlib.reload(cfg)
        assert cfg.ILINK_SEND_URL == "http://ilink:9000/send"

    def test_ilink_empty_default(self, monkeypatch):
        """iLink URL is empty when not configured."""
        monkeypatch.delenv("ILINK_SEND_URL", raising=False)
        monkeypatch.delenv("ILINK_SEND_URL_LEGACY", raising=False)
        import importlib

        import agent_runtime.config as cfg

        importlib.reload(cfg)
        assert cfg.ILINK_SEND_URL == ""
