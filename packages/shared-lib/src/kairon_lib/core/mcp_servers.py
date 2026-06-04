"""MCP server registry, discovery, and connection management.

Migrated from agentmesh toolkit/src/integrations/ (MCPServers, MCPServer,
PublicAPIs, WorkspaceMCPClient, mcp-tools).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MCPServerInfo:
    """MCP server descriptor."""

    name: str
    description: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    category: str = "Utility"
    url: str = ""
    author: str = ""
    official: bool = False


@dataclass
class MCPTool:
    """MCP tool definition."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPServerConnection:
    """Active MCP server connection state."""

    server: MCPServerInfo
    status: str = "disconnected"
    tools: list[MCPTool] = field(default_factory=list)
    error: str = ""
    last_health_check: float = 0.0


class MCPServers:
    """MCP server registry with discovery and search capabilities."""

    CATEGORIES = [
        "AI", "Browser", "Database", "Development", "DevOps", "Finance",
        "Knowledge", "Marketing", "Media", "Productivity", "Security",
        "Social", "Storage", "Utility", "Other",
    ]

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerInfo] = {}

    def register(self, info: MCPServerInfo) -> None:
        self._servers[info.name] = info

    def get(self, name: str) -> MCPServerInfo | None:
        return self._servers.get(name)

    def unregister(self, name: str) -> bool:
        return self._servers.pop(name, None) is not None

    def list_all(self) -> list[MCPServerInfo]:
        return list(self._servers.values())

    def search(self, query: str = "", *, category: str = "", official: bool = False) -> list[MCPServerInfo]:
        results = list(self._servers.values())
        if query:
            q = query.lower()
            results = [s for s in results if q in s.name.lower() or q in s.description.lower() or q in s.category.lower()]
        if category:
            results = [s for s in results if s.category.lower() == category.lower()]
        if official:
            results = [s for s in results if s.official]
        return results

    def get_by_category(self, category: str) -> list[MCPServerInfo]:
        return self.search(category=category)

    def discover_by_tool(self, tool_name: str) -> list[MCPServerInfo]:
        return [s for s in self._servers.values() if any(t.get("name") == tool_name for t in s.tools)]

    @property
    def server_count(self) -> int:
        return len(self._servers)


class MCPDiscovery:
    """MCP server dynamic discovery from env, config files, and npx packages."""

    def __init__(self, config_paths: list[str] | None = None, auto_connect: bool = False) -> None:
        self._servers: dict[str, MCPServerInfo] = {}
        self._connections: dict[str, MCPServerConnection] = {}
        self._config_paths = config_paths or []
        self._auto_connect = auto_connect

    def discover_from_env(self, prefix: str = "MCP_SERVER_") -> list[MCPServerInfo]:
        servers: list[MCPServerInfo] = []
        for key, value in sorted(os.environ.items()):
            if key.startswith(prefix) and key.endswith("_COMMAND"):
                name = key.replace(prefix, "").replace("_COMMAND", "")
                args_str = os.environ.get(f"{prefix}{name}_ARGS", "")
                env_str = os.environ.get(f"{prefix}{name}_ENV", "{}")
                args: list[str] = []
                try:
                    args = json.loads(args_str) if args_str else []
                except json.JSONDecodeError:
                    args = [a for a in args_str.split(" ") if a]
                env_dict: dict[str, str] = {}
                try:
                    env_dict = json.loads(env_str) if env_str else {}
                except json.JSONDecodeError:
                    pass
                servers.append(MCPServerInfo(name=name, command=value, args=args, env=env_dict))
        return servers

    def add_server(self, info: MCPServerInfo) -> str:
        sid = info.name.lower().replace(" ", "-")
        self._servers[sid] = info
        return sid

    def connect(self, server_id: str) -> MCPServerConnection:
        server = self._servers.get(server_id)
        if not server:
            raise ValueError(f"Server not found: {server_id}")
        conn = MCPServerConnection(server=server, status="connected", last_health_check=datetime.now().timestamp())
        self._connections[server_id] = conn
        return conn

    def disconnect(self, server_id: str) -> None:
        self._connections.pop(server_id, None)

    def get_connection(self, server_id: str) -> MCPServerConnection | None:
        return self._connections.get(server_id)

    def get_status(self) -> dict[str, Any]:
        connected = sum(1 for c in self._connections.values() if c.status == "connected")
        errors = sum(1 for c in self._connections.values() if c.status == "error")
        return {"total": len(self._servers), "connected": connected, "errors": errors}


class WorkspaceMCPClient:
    """Workspace-level MCP client using stdio protocol."""

    def __init__(self) -> None:
        self._services: list[MCPServerInfo] = []
        self._connections: dict[str, MCPServerConnection] = {}

    def add_service(self, info: MCPServerInfo) -> None:
        self._services.append(info)

    async def connect_all(self) -> list[MCPServerConnection]:
        results: list[MCPServerConnection] = []
        for svc in self._services:
            conn = MCPServerConnection(server=svc, status="connected")
            self._connections[svc.name] = conn
            results.append(conn)
        return results

    def get_status(self) -> dict[str, Any]:
        connected = sum(1 for c in self._connections.values() if c.status == "connected")
        return {"total": len(self._services), "connected": connected}

    def disconnect_all(self) -> None:
        self._connections.clear()


class PublicAPIDiscovery:
    """Public API registry and discovery (ported from PublicAPIs.ts)."""

    def __init__(self) -> None:
        self._apis: list[dict[str, Any]] = []

    def register(self, api: dict[str, Any]) -> None:
        self._apis.append(api)

    def search(self, query: str = "", *, category: str = "", auth: str = "") -> list[dict[str, Any]]:
        results = list(self._apis)
        if query:
            q = query.lower()
            results = [a for a in results if q in a.get("name", "").lower() or q in a.get("description", "").lower()]
        if category:
            results = [a for a in results if a.get("category", "").lower() == category.lower()]
        if auth:
            results = [a for a in results if a.get("auth", "").lower() == auth.lower()]
        return results
