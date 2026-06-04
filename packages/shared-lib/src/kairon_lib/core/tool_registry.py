"""Tool registry -- migrated from agentmesh toolkit/tools/ToolRegistry.ts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class AgentTool:
    def __init__(
        self,
        tool_id: str,
        name: str,
        description: str,
        category: str = "",
        version: str = "1.0.0",
        tags: list[str] | None = None,
        parameters: Any = None,
        handler: Callable | None = None,
    ) -> None:
        self.id = tool_id
        self.name = name
        self.description = description
        self.category = category
        self.version = version
        self.tags = tags or []
        self.parameters = parameters or _empty_param_def()
        self.handler = handler


def _empty_param_def() -> dict:
    return {"type": "object", "required": [], "properties": {}}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Central registry for agent tools with search, execution, and stats."""

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._categories: dict[str, set[str]] = {}
        self._usage: dict[str, int] = {}

    # Registration ---------------------------------------------------------

    def register(self, tool: AgentTool) -> None:
        if tool.id in self._tools:
            import warnings
            warnings.warn(f"Tool {tool.id} already registered, overwriting...")
        self._tools[tool.id] = tool
        if tool.category not in self._categories:
            self._categories[tool.category] = set()
        self._categories[tool.category].add(tool.id)

    def register_many(self, tools: list[AgentTool]) -> None:
        for t in tools:
            self.register(t)

    def unregister(self, tool_id: str) -> bool:
        tool = self._tools.pop(tool_id, None)
        if tool is None:
            return False
        cat_set = self._categories.get(tool.category)
        if cat_set is not None:
            cat_set.discard(tool_id)
        return True

    # Lookup ---------------------------------------------------------------

    def get(self, tool_id: str) -> AgentTool | None:
        return self._tools.get(tool_id)

    def get_by_category(self, category: str) -> list[AgentTool]:
        ids = self._categories.get(category, set())
        return [self._tools[tid] for tid in ids if tid in self._tools]

    def search(self, query: str) -> list[AgentTool]:
        low = query.lower()
        scored: list[tuple[int, AgentTool]] = []
        for tool in self._tools.values():
            score = 0
            if low in tool.name.lower():
                score += 10
            if low in tool.description.lower():
                score += 5
            for tag in tool.tags:
                if low in tag.lower():
                    score += 3
            if low in tool.category.lower():
                score += 2
            if score > 0:
                scored.append((score, tool))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored]

    # Execution ------------------------------------------------------------

    async def execute(
        self,
        tool_id: str,
        params: Any,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool = self._tools.get(tool_id)
        if tool is None:
            return {"success": False, "error": f"Tool {tool_id} not found"}

        validation = _validate_params(params, tool.parameters)
        if not validation["valid"]:
            return {"success": False, "error": f"Invalid params: {', '.join(validation['errors'])}"}

        try:
            self._usage[tool_id] = self._usage.get(tool_id, 0) + 1
            if tool.handler:
                result = await tool.handler(params, context)
                return result
            return {"success": True, "data": params}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def get_all(self) -> list[AgentTool]:
        return list(self._tools.values())

    def get_stats(self) -> dict[str, Any]:
        cat_count: dict[str, int] = {
            cat: len(ids) for cat, ids in self._categories.items()
        }
        most_used = sorted(self._usage.items(), key=lambda x: x[1], reverse=True)[:10]
        return {
            "totalTools": len(self._tools),
            "categories": cat_count,
            "mostUsed": [{"toolId": tid, "count": cnt} for tid, cnt in most_used],
        }


# ---------------------------------------------------------------------------
# Builder (fluent)
# ---------------------------------------------------------------------------

class ToolBuilder:
    """Fluent builder for creating AgentTool instances."""

    def __init__(self, tool_id: str, name: str, description: str) -> None:
        self._data: dict[str, Any] = {
            "id": tool_id, "name": name, "description": description,
            "tags": [], "version": "1.0.0",
        }

    def category(self, cat: str) -> ToolBuilder:
        self._data["category"] = cat
        return self

    def version(self, ver: str) -> ToolBuilder:
        self._data["version"] = ver
        return self

    def parameters(self, params: Any) -> ToolBuilder:
        self._data["parameters"] = params
        return self

    def handler(self, h: Callable) -> ToolBuilder:
        self._data["handler"] = h
        return self

    def tags(self, tgs: list[str]) -> ToolBuilder:
        self._data["tags"] = tgs
        return self

    def build(self) -> AgentTool:
        if not self._data.get("category") or not self._data.get("parameters") or not self._data.get("handler"):
            raise ValueError("Tool is missing required fields")
        return AgentTool(
            tool_id=self._data["id"],
            name=self._data["name"],
            description=self._data["description"],
            category=self._data["category"],
            version=self._data["version"],
            tags=self._data["tags"],
            parameters=self._data["parameters"],
            handler=self._data["handler"],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_params(params: Any, param_def: Any) -> dict:
    errors: list[str] = []
    if not isinstance(params, dict):
        required = param_def.get("required", [])
        if required:
            errors.append("Parameters are required")
        return {"valid": len(errors) == 0, "errors": errors}
    required = param_def.get("required", [])
    for r in required:
        if r not in params:
            errors.append(f"Missing required parameter: {r}")
    props = param_def.get("properties", {})
    for key, value in params.items():
        prop = props.get(key)
        if prop is not None:
            expected_type = prop.get("type", "")
            actual_type = "array" if isinstance(value, list) else type(value).__name__
            if expected_type and actual_type != expected_type:
                errors.append(f"Invalid type for {key}: expected {expected_type}, got {actual_type}")
    return {"valid": len(errors) == 0, "errors": errors}
