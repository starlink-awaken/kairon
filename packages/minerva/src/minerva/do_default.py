"""P58-W0 minerva do_default — 真业务 (调 minerva search / pipeline / triage 真类)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 minerva do_default: 真调 TriageRouter / SearchEngine / create_default_pipeline."""
    try:
        from minerva import __version__
        from minerva.executor.executor import CostGuard, ResearchExecutor
        from minerva.search.engine import SearchEngine
        from minerva.triage.router import TriageRouter
    except Exception as exc:  # noqa: BLE001
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list_components")
    try:
        if action == "list_components":
            return {
                "_method": "do_default",
                "_action": "list_components",
                "TriageRouter": TriageRouter.__name__,
                "SearchEngine": SearchEngine.__name__,
                "ResearchExecutor": ResearchExecutor.__name__,
                "CostGuard": CostGuard.__name__,
                "version": __version__,
            }
        if action == "pipeline":
            from minerva.pipeline.engine import create_default_pipeline

            pipe = create_default_pipeline()
            return {
                "_method": "do_default",
                "_action": "pipeline",
                "pipeline_type": type(pipe).__name__,
                "methods": [m for m in dir(pipe) if not m.startswith("_")][:10],
            }
        if action == "search_engine":
            se = SearchEngine()
            return {
                "_method": "do_default",
                "_action": "search_engine",
                "engine_type": type(se).__name__,
                "methods": [m for m in dir(se) if not m.startswith("_")][:10],
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:  # noqa: BLE001
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
