from __future__ import annotations

import json

from fastmcp import FastMCP
from forge.http_api import build_asset_stats, load_graph, load_registry, query_assets

mcp = FastMCP("forge", mask_error_details=True)


@mcp.tool()
def search_tools(query: str, capabilities: list[str] | None = None, limit: int = 10):
    """Search tools in the Forge registry."""
    results, _ = query_assets(query=query, capabilities=capabilities, limit=limit)
    return results


@mcp.tool()
def get_tool_info(tool_id: str):
    """Get detailed info about a specific tool."""
    results, _ = query_assets(query=tool_id, limit=100)
    for tool in results:
        if tool.get("id") == tool_id:
            return tool
    return None


@mcp.tool()
def list_tools(limit: int = 50):
    """List tools in the Forge registry."""
    results, _ = query_assets(limit=limit)
    return results


@mcp.tool()
def get_project_status():
    """Get Forge project stats."""
    reg = load_registry()
    stats = build_asset_stats()
    return {
        "schema": reg.get("schema_version", "?"),
        "tools": stats.get("total", 0),
        "active": stats.get("by_status", {}).get("active", 0),
    }


@mcp.resource("bos://forge/market/list")
def read_market_list() -> str:
    """Return the market list from Forge."""
    results, _ = query_assets(limit=9999)
    # We map forge assets to the structure expected by Agora market
    market = {}
    for tool in results:
        repo = tool.get("repository", "")
        # Filter only tools with github repos for market
        if "github.com" in repo:
            repo_short = repo.replace("https://github.com/", "").rstrip("/")
            market[tool["id"]] = {
                "name": tool["id"],
                "description": tool.get("description", ""),
                "repo": repo_short,
                "type": "python",  # default assumption
                "entry": tool.get("entrypoint", "mcp_server.py"),
                "tags": tool.get("categories", []),
                "port": tool.get("port", 0),
            }
    return json.dumps(market, ensure_ascii=False)


def get_graph_stats():
    return load_graph().get("stats", {})

def capture_tool(*_args, **_kwargs):
    return {"status": "captured_stub"}

def main():
    mcp.run()


if __name__ == "__main__":
    main()
