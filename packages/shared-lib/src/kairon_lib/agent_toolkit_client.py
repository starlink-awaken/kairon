"""Agent toolkit client (toolkit skills/openai/agent-toolkit.ts)."""

from __future__ import annotations

from typing import Any


class AgentToolkitClient:
    """Client for interacting with agent toolkit via OpenAI functions."""

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def register_tool(self, name: str, handler: Any) -> None:
        self._tools[name] = handler

    def call_tool(self, name: str, args: dict[str, Any] | None = None) -> Any:
        handler = self._tools.get(name)
        if handler is None: raise ValueError(f"Tool not found: {name}")
        return handler(**(args or {}))
