"""Forge server/mcp_server.py 单元测试（旧 API — 跳过）

测试覆盖（已由 server/mcp_server.py 替代）:
"""

import json
import sys
from pathlib import Path

import pytest

pytest.skip("src/mcp_server 已合并到 server/mcp_server.py，API 变更", allow_module_level=True)

SRC = Path(__file__).resolve().parent.parent / "src"
SERVER = Path(__file__).resolve().parent.parent / "server"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SERVER))


SAMPLE_TOOLS = [
    {
        "id": "claude-code",
        "name": "Claude Code",
        "type": "tool",
        "status": "active",
        "category": ["MCP", "AI"],
        "capabilities": ["code", "chat", "analysis"],
        "notes": "Anthropic's coding assistant",
        "source": {"provider": "Anthropic"},
    },
    {
        "id": "ollama-local",
        "name": "Ollama",
        "type": "tool",
        "status": "active",
        "category": ["Local"],
        "capabilities": ["chat", "code"],
        "notes": "Local LLM runner",
        "source": {"provider": "开源工具"},
    },
    {
        "id": "candidate-tool",
        "name": "Not Ready",
        "type": "tool",
        "status": "candidate",
        "category": [],
        "capabilities": ["vision"],
        "notes": "Still in evaluation",
    },
]

SAMPLE_REGISTRY = {
    "schema_version": "1.2",
    "tools": SAMPLE_TOOLS,
    "event_log": [],
    "gap_analysis": {"gaps": []},
}

SAMPLE_GRAPH = {
    "stats": {"total_nodes": 5, "total_edges": 3},
    "nodes": [
        {"id": "claude-code", "type": "Tool", "label": "Claude Code"},
        {"id": "ollama-local", "type": "Tool", "label": "Ollama"},
        {"id": "cap-code", "type": "Capability", "label": "code"},
        {"id": "cap-chat", "type": "Capability", "label": "chat"},
        {"id": "MCP", "type": "Category", "label": "MCP"},
    ],
    "edges": [
        {"source": "claude-code", "target": "cap-code", "relation": "HAS_CAPABILITY"},
        {"source": "claude-code", "target": "cap-chat", "relation": "HAS_CAPABILITY"},
        {"source": "ollama-local", "target": "cap-chat", "relation": "HAS_CAPABILITY"},
    ],
}


@pytest.fixture
def setup_registry(monkeypatch, tmp_path):
    """Patch REGISTRY and GRAPH paths to temp files."""
    import mcp_server

    reg_file = tmp_path / "tools-registry.json"
    reg_file.write_text(json.dumps(SAMPLE_REGISTRY))
    monkeypatch.setattr(mcp_server, "REGISTRY", reg_file)

    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()
    graph_file = graph_dir / "graph.json"
    graph_file.write_text(json.dumps(SAMPLE_GRAPH))
    monkeypatch.setattr(mcp_server, "GRAPH", graph_file)

    # Reset the save debounce timer so each test can write immediately
    monkeypatch.setattr(mcp_server, "_last_save", 0.0)

    return mcp_server


# ═══════════════════════════════════════════════════
# 1. 模块导入与结构
# ═══════════════════════════════════════════════════


class TestImports:
    def test_module_imports(self):
        import mcp_server

        assert hasattr(mcp_server, "search_tools")
        assert hasattr(mcp_server, "get_tool")
        assert hasattr(mcp_server, "health_check")
        assert hasattr(mcp_server, "get_status")
        assert hasattr(mcp_server, "capture_tool")
        assert hasattr(mcp_server, "list_candidates")
        assert hasattr(mcp_server, "list_by_category")
        assert hasattr(mcp_server, "query_graph")
        assert hasattr(mcp_server, "recommend_tools")
        assert hasattr(mcp_server, "get_graph_stats")
        assert hasattr(mcp_server, "run_self_test")
        assert hasattr(mcp_server, "load_registry")
        assert hasattr(mcp_server, "save_registry")
        assert hasattr(mcp_server, "main")

    def test_constants_defined(self):
        import mcp_server

        assert hasattr(mcp_server, "TOOLBOX_DIR")


# ═══════════════════════════════════════════════════
# 2. search_tools
# ═══════════════════════════════════════════════════


class TestSearchTools:
    def test_search_by_query(self, setup_registry):
        mcp = setup_registry
        result = mcp.search_tools("claude", limit=10)
        assert isinstance(result, list)
        # Should match claude-code by id
        assert any(t["id"] == "claude-code" for t in result)

    def test_search_with_capability_filter(self, setup_registry):
        mcp = setup_registry
        result = mcp.search_tools("", capabilities=["vision"], limit=5)
        assert isinstance(result, list)
        # candidate-tool has 'vision' but is filtered out by status
        for t in result:
            caps = [c.lower() for c in t.get("capabilities", [])]
            assert any("vision" in c for c in caps)

    def test_search_excludes_candidates(self, setup_registry):
        mcp = setup_registry
        result = mcp.search_tools("candidate", limit=10)
        # candidate-tool status is 'candidate', should be excluded
        assert all(t.get("id") != "candidate-tool" for t in result)

    def test_search_empty_query_returns_top(self, setup_registry):
        mcp = setup_registry
        result = mcp.search_tools("", limit=2)
        assert len(result) <= 2
        # No candidates in results
        assert all(t.get("status") != "candidate" for t in result)

    def test_search_no_match(self, setup_registry):
        mcp = setup_registry
        result = mcp.search_tools("zzz_nonexistent_999", limit=10)
        assert result == []


# ═══════════════════════════════════════════════════
# 3. get_tool
# ═══════════════════════════════════════════════════


class TestGetTool:
    def test_get_existing_tool(self, setup_registry):
        mcp = setup_registry
        result = mcp.get_tool("claude-code")
        assert result is not None
        assert result["id"] == "claude-code"
        assert result["name"] == "Claude Code"

    def test_get_nonexistent_tool(self, setup_registry):
        mcp = setup_registry
        result = mcp.get_tool("nonexistent-tool")
        assert result is None


# ═══════════════════════════════════════════════════
# 4. list_candidates / list_by_category
# ═══════════════════════════════════════════════════


class TestListCandidates:
    def test_list_candidates(self, setup_registry):
        mcp = setup_registry
        result = mcp.list_candidates()
        assert isinstance(result, list)
        assert any(t["id"] == "candidate-tool" for t in result)
        assert all(t.get("status") == "candidate" for t in result)


class TestListByCategory:
    def test_list_by_existing_category(self, setup_registry):
        mcp = setup_registry
        result = mcp.list_by_category("MCP")
        assert isinstance(result, list)
        assert all("MCP" in t.get("category", []) for t in result)

    def test_list_by_nonexistent_category(self, setup_registry):
        mcp = setup_registry
        result = mcp.list_by_category("NonExistent")
        assert result == []


# ═══════════════════════════════════════════════════
# 5. health_check / get_status
# ═══════════════════════════════════════════════════


class TestHealthCheck:
    def test_health_check_shape(self, setup_registry):
        mcp = setup_registry
        result = mcp.health_check()
        assert isinstance(result, dict)
        assert "schema" in result
        assert "tools" in result
        assert "active" in result
        assert "graph_nodes" in result
        assert "graph_edges" in result
        assert result["tools"] == 3
        assert result["active"] == 2
        assert result["graph_nodes"] == 5


class TestGetStatus:
    def test_get_status_shape(self, setup_registry):
        mcp = setup_registry
        result = mcp.get_status()
        assert isinstance(result, dict)
        assert "schema" in result
        assert "tools" in result
        assert "active" in result
        assert "candidates" in result
        assert result["tools"] == 3
        assert result["active"] == 2
        assert result["candidates"] == 1
        assert result["graph_nodes"] == 5


# ═══════════════════════════════════════════════════
# 6. query_graph / recommend_tools
# ═══════════════════════════════════════════════════


class TestQueryGraph:
    def test_query_graph_found(self, setup_registry):
        mcp = setup_registry
        result = mcp.query_graph("Claude")
        assert isinstance(result, list)
        assert any(n["id"] == "claude-code" for n in result)

    def test_query_graph_not_found(self, setup_registry):
        mcp = setup_registry
        result = mcp.query_graph("ZZZZZ")
        assert result == []


class TestRecommendTools:
    def test_recommend_existing(self, setup_registry):
        mcp = setup_registry
        result = mcp.recommend_tools("claude-code")
        assert isinstance(result, dict)
        # claude-code connects to cap-code and cap-chat
        assert len(result) > 0

    def test_recommend_nonexistent(self, setup_registry):
        mcp = setup_registry
        result = mcp.recommend_tools("nonexistent")
        assert result == {}


# ═══════════════════════════════════════════════════
# 7. get_graph_stats
# ═══════════════════════════════════════════════════


class TestGetGraphStats:
    def test_graph_stats(self, setup_registry):
        mcp = setup_registry
        result = mcp.get_graph_stats()
        assert isinstance(result, dict)
        assert result["total_nodes"] == 5
        assert result["total_edges"] == 3


# ═══════════════════════════════════════════════════
# 8. capture_tool
# ═══════════════════════════════════════════════════


class TestCaptureTool:
    def test_capture_creates_skill_dir_and_entry(self, setup_registry, monkeypatch, tmp_path):
        mcp = setup_registry
        toolbox_dir = tmp_path / "toolbox"
        monkeypatch.setattr(mcp, "TOOLBOX_DIR", toolbox_dir)

        result = mcp.capture_tool("my-skill", "A test skill", ["step1", "step2"])
        assert result["status"] == "ok"
        assert result["id"] == "my-skill"

        skill_file = toolbox_dir / "skills" / "my-skill" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text()
        assert "A test skill" in content
        assert "step1" in content

    def test_capture_registers_in_registry(self, setup_registry, monkeypatch, tmp_path):
        mcp = setup_registry
        toolbox_dir = tmp_path / "toolbox2"
        monkeypatch.setattr(mcp, "TOOLBOX_DIR", toolbox_dir)

        mcp.capture_tool("captured-tool", "A captured tool", ["do it"])
        registry = mcp.load_registry()
        ids = [t["id"] for t in registry["tools"]]
        assert "captured-tool" in ids


# ═══════════════════════════════════════════════════
# 9. run_self_test
# ═══════════════════════════════════════════════════


class TestRunSelfTest:
    def test_self_test_returns_true(self, setup_registry):
        mcp = setup_registry
        # run_self_test calls print, shouldn't crash
        result = mcp.run_self_test()
        assert result is True


# ═══════════════════════════════════════════════════
# 10. _record_usage
# ═══════════════════════════════════════════════════


class TestRecordUsage:
    def test_record_usage_updates_telemetry(self, setup_registry):
        mcp = setup_registry
        # Call _record_usage directly and verify the state is saved
        mcp._record_usage("claude-code", "test")
        tool = mcp.get_tool("claude-code")
        assert tool is not None
        telemetry = tool.get("telemetry", {})
        assert telemetry.get("use_count", 0) >= 1

    def test_record_usage_unknown_tool_does_not_crash(self, setup_registry):
        mcp = setup_registry
        # Direct call to _record_usage with non-existent id
        mcp._record_usage("nonexistent-tool", "test")
        # Should not raise
        assert True
