from forge.http_api import build_asset_stats, load_graph, load_registry, query_assets, query_graph


def search_tools(query: str, capabilities: list[str] | None = None, limit: int = 10):
    results, _ = query_assets(query=query, capabilities=capabilities, limit=limit)
    return results


def get_tool_info(tool_id: str):
    results, _ = query_assets(query=tool_id, limit=100)
    for tool in results:
        if tool.get("id") == tool_id:
            return tool
    return None


def list_tools(limit: int = 50):
    results, _ = query_assets(limit=limit)
    return results


def get_project_status():
    reg = load_registry()
    stats = build_asset_stats()
    return {"schema": reg.get("schema_version", "?"), "tools": stats.get("total", 0), "active": stats.get("by_status", {}).get("active", 0)}


def capture_tool(*_args, **_kwargs):
    return {"status": "captured_stub"}
