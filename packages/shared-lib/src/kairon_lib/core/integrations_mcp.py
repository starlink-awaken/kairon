"""MCP integration client for agent toolkit (agentmesh toolkit/integrations migration)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPServerInfo:
    """MCP server descriptor."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)


class MCPServers:
    """MCP server registry and discovery."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerInfo] = {}

    def register(self, info: MCPServerInfo) -> None:
        self._servers[info.name] = info

    def get(self, name: str) -> MCPServerInfo | None:
        return self._servers.get(name)

    def unregister(self, name: str) -> bool:
        return self._servers.pop(name, None) is not None

    def list_servers(self) -> list[MCPServerInfo]:
        return list(self._servers.values())

    def discover_by_tool(self, tool_name: str) -> list[MCPServerInfo]:
        return [s for s in self._servers.values() if any(t.get("name") == tool_name for t in s.tools)]

    def call_tool(self, server_name: str, tool_name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a tool on an MCP server via stdio."""
        server = self._servers.get(server_name)
        if server is None:
            return {"error": f"Server not found: {server_name}"}
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args or {}},
        })
        try:
            result = subprocess.run(
                [server.command, *server.args],
                input=request,
                capture_output=True,
                text=True,
                timeout=30,
                env=dict(server.env) if server.env else None,
            )
            return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
        except subprocess.TimeoutExpired:
            return {"error": "Tool call timed out"}
        except FileNotFoundError:
            return {"error": f"Server command not found: {server.command}"}

    @property
    def server_count(self) -> int:
        return len(self._servers)
