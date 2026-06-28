"""P58-W0 kairon_pipeline do_default — 真业务 (调 SourceRegistry / QualityGate 真类)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 kairon_pipeline do_default: 真调 SourceRegistry / QualityGate / trigger."""
    try:
        from kairon_pipeline import (
            HarvestPriorityQueue,
            QualityGate,
            SourceRegistry,
            trigger_downstream_processing,
        )
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list_components")
    try:
        if action == "list_components":
            return {
                "_method": "do_default",
                "_action": "list_components",
                "SourceRegistry": SourceRegistry.__name__,
                "QualityGate": QualityGate.__name__,
                "HarvestPriorityQueue": HarvestPriorityQueue.__name__,
                "trigger_fn": trigger_downstream_processing.__name__,
            }
        if action == "sources":
            sr = SourceRegistry()
            return {
                "_method": "do_default",
                "_action": "sources",
                "registry_type": type(sr).__name__,
                "methods": [m for m in dir(sr) if not m.startswith("_")][:15],
            }
        if action == "quality_gate":
            qg = QualityGate()
            return {
                "_method": "do_default",
                "_action": "quality_gate",
                "gate_type": type(qg).__name__,
                "methods": [m for m in dir(qg) if not m.startswith("_")][:10],
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
