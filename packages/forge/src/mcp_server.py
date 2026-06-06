from __future__ import annotations

from forge.http_api import build_asset_stats, load_graph, load_registry, query_assets


def search_tools(query: str, capabilities: list[str] | None = None, limit: int = 10):
    results, _ = query_assets(query=query, capabilities=capabilities, limit=limit)
    return results


def get_tool_info(tool_id: str):
    results, _ = query_assets(query=tool_id, limit=100)
    for tool in results:
        if tool.get("id") == tool_id:
            return tool
    return None


def get_tool(tool_id: str):
    return get_tool_info(tool_id)


def list_tools(limit: int = 50):
    results, _ = query_assets(limit=limit)
    return results


def list_by_category(category: str | None = None):
    results, _ = query_assets(category=category or "", limit=99999)
    return results


def get_project_status():
    reg = load_registry()
    stats = build_asset_stats()
    return {"schema": reg.get("schema_version", "?"), "tools": stats.get("total", 0), "active": stats.get("by_status", {}).get("active", 0)}


def health_check():
    return get_project_status()


def get_status():
    return get_project_status()


def get_graph_stats():
    return load_graph().get("stats", {})


def capture_tool(*_args, **_kwargs):
    return {"status": "captured_stub"}
