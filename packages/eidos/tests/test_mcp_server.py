"""Tests for Eidos MCP server."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TestMCPServer:
    def test_handle_list(self):
        from eidos.mcp_server import handle_list

        r = handle_list({})
        assert "schemas" in r
        assert "count" in r

    def test_handle_meta(self):
        from eidos.mcp_server import handle_meta

        r = handle_meta({})
        assert "meta_types" in r
        assert len(r["meta_types"]) == 8

    def test_handle_validate_fail(self):
        from eidos.mcp_server import handle_validate

        r = handle_validate({"data": "not json", "schema_type": "KnowledgeCard"})
        assert r["is_valid"] is False

    def test_handle_validate_empty(self):
        from eidos.mcp_server import handle_validate

        r = handle_validate({"data": "{}", "schema_type": "KnowledgeCard"})
        assert r["is_valid"] is False

    def test_handle_define(self):
        from eidos.mcp_server import handle_define

        r = handle_define({"name": "TestS", "fields": [{"name": "id", "type": "string"}]})
        assert r["status"] == "registered"

    def test_handle_request_list_tools(self):
        from eidos.mcp_server import handle_mcp_request as handle_request

        r = handle_request({"id": 1, "method": "list_tools"})
        assert "tools" in r["result"]

    def test_handle_request_unknown_tool(self):
        from eidos.mcp_server import handle_mcp_request as handle_request

        r = handle_request({"id": 1, "method": "call_tool/nonexistent"})
        assert "error" in r
