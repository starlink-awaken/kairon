"""Compute tool composer — dynamic tool composition (toolkit tools/DynamicComposer.ts)."""

from __future__ import annotations

from typing import Any


class DynamicComposer:
    """Compose multiple tools into a pipeline."""

    def compose(self, steps: list[dict[str, Any]], context: dict[str, Any] | None = None) -> Any:
        result = None; ctx = dict(context or {})
        for step in steps:
            name = step.get("tool", ""); args = step.get("args", {})
            resolved = {k: ctx.get(v[1:], v) if isinstance(v, str) and v.startswith("$") else v for k, v in args.items()}
            result = {"tool": name, "args": resolved, "result": None}
            ctx[step.get("output", name)] = result
        return result
