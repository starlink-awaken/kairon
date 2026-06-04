"""OpenAI function converter (toolkit skills/openai/converter.ts)."""

from __future__ import annotations

from typing import Any


def convert_to_openai_tool(fn_def: dict[str, Any]) -> dict[str, Any]:
    """Convert a function definition to OpenAI tool format."""
    return {
        "type": "function",
        "function": {
            "name": fn_def.get("name", ""),
            "description": fn_def.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": {p["name"]: {"type": p.get("type", "string"), "description": p.get("description", "")} for p in fn_def.get("parameters", [])},
                "required": [p["name"] for p in fn_def.get("parameters", []) if p.get("required", False)],
            },
        },
    }


def convert_from_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI tool definition back to internal format."""
    fn = tool.get("function", {})
    return {"name": fn.get("name", ""), "description": fn.get("description", "")}
