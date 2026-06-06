"""Tests for Sophia MCP server — module import and tool registration."""

import asyncio


def _tool_names():
    from sophia.server.mcp_server import mcp

    tools = asyncio.run(mcp.list_tools())
    return [t.name for t in tools]


def test_module_importable():
    from sophia.server import mcp_server

    assert mcp_server is not None


def test_mcp_runnable():
    from sophia.server.mcp_server import mcp

    assert callable(mcp.tool)


def test_list_states_tool():
    names = _tool_names()
    assert "list_states" in names


def test_list_operations_tool():
    names = _tool_names()
    assert "list_operations" in names


def test_suggest_ops_tool():
    names = _tool_names()
    assert "suggest_ops" in names


def test_compile_paradigm_tool():
    names = _tool_names()
    assert "compile_paradigm" in names


def test_tool_count():
    names = _tool_names()
    assert len(names) >= 5
