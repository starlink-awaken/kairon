"""Tests for SSOT MCP Server (mcp_server.py).

Covers: handle_message, TOOLS definitions, HANDLERS map.

Note: mcp_server.py is at package root (ssot/mcp_server.py), not in src/ssot_kernel/.
"""

import sys
from pathlib import Path

# ── Import mcp_server from package root ──────────────────────────────────────

_SSOT_ROOT = Path(__file__).resolve().parent.parent
if str(_SSOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SSOT_ROOT))

import mcp_server  # type: ignore

handle_message = mcp_server.handle_message
TOOLS = mcp_server.TOOLS
HANDLERS = mcp_server.HANDLERS


class TestToolDefinitions:
    def test_tools_list_not_empty(self):
        """MCP server should expose tool definitions."""
        assert len(TOOLS) >= 6

    def test_tools_have_required_fields(self):
        """Each tool definition should have name, description, inputSchema."""
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    def test_tools_names(self):
        """Check expected tool names."""
        names = [t["name"] for t in TOOLS]
        for expected in ("check", "derive", "compile", "evolve", "stats", "sync", "extract_from_file"):
            assert expected in names


class TestHandleMessage:
    def test_tools_list(self):
        """Handle tools/list request."""
        response = handle_message({"method": "tools/list", "id": "1"})
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "1"
        assert "result" in response
        assert "tools" in response["result"]

    def test_initialize(self):
        """Handle initialize request."""
        response = handle_message({"method": "initialize", "id": "1"})
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "1"
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert response["result"]["serverInfo"]["name"] == "ssot-kernel"

    def test_notifications_initialized(self):
        """Handle notifications/initialized returns None."""
        response = handle_message({"method": "notifications/initialized"})
        assert response is None

    def test_unknown_method(self):
        """Handle unknown method returns error."""
        response = handle_message({"method": "unknown", "id": "1"})
        assert response["error"]["code"] == -32601

    def test_tools_call_unknown_tool(self):
        """Calling unknown tool returns error."""
        response = handle_message(
            {
                "method": "tools/call",
                "id": "1",
                "params": {"name": "nonexistent_tool", "arguments": {}},
            }
        )
        assert "error" in response


class TestHandlers:
    def test_handlers_map(self):
        """HANDLERS should contain expected keys."""
        assert "check" in HANDLERS
        assert "derive" in HANDLERS
        assert "compile" in HANDLERS
        assert "evolve" in HANDLERS
        assert "stats" in HANDLERS
        assert "sync" in HANDLERS
        assert "extract_from_file" in HANDLERS
