"""P57-W0 forge do_default — 真业务 (调 forge.cmd_* CLI command)."""
from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P57-W0 forge do_default: 真调 forge.cmd_list / cmd_health / cmd_market."""
    try:
        from forge.forge import cmd_health, cmd_list, cmd_market, cmd_status
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list")
    try:
        if action == "list":
            tools = cmd_list([])
            return {
                "_method": "do_default", "_action": "list",
                "tools_count": len(tools) if isinstance(tools, (list, dict)) else None,
                "tools": tools if isinstance(tools, (list, dict)) else str(tools)[:500],
            }
        if action == "health":
            health = cmd_health([])
            return {"_method": "do_default", "_action": "health", "health": str(health)[:500]}
        if action == "status":
            status = cmd_status()
            return {"_method": "do_default", "_action": "status", "status": str(status)[:500]}
        if action == "market":
            market = cmd_market([])
            return {"_method": "do_default", "_action": "market", "market": str(market)[:500]}
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
