# ---
# domain: D-Memory
# layer: organ
# status: active
# ---
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eidos.organs.unified_memory_api import UnifiedMemoryAPI  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)

_default_unified_memory_api_singleton: UnifiedMemoryAPI | None = None


def _build_default_holo_memory() -> Any:
    from eidos.organs.holo_memory import HoloMemory  # type: ignore[import-not-found]

    return HoloMemory()


def _build_default_fact_graph() -> Any:
    from eidos.organs.fact_graph import get_fact_graph  # type: ignore[import-not-found]

    return get_fact_graph()


def _build_default_nks_query_engine() -> Any:
    from eidos.organs.nks.graph_store import GraphStore  # type: ignore[import-not-found]
    from eidos.organs.nks.query_engine import GraphQueryEngine  # type: ignore[import-not-found]

    store = GraphStore("eidos/nks_graph.db")
    return GraphQueryEngine(store)


def _build_optional_subsystem(name: str, builder: Callable[[], object]) -> Any | None:
    try:
        return builder()
    except Exception as exc:
        _log.warning("[UnifiedMemoryAPI] default %s wiring unavailable: %s", name, exc)
        return None


def build_default_unified_memory_api() -> UnifiedMemoryAPI:
    from eidos.organs.unified_memory_api import UnifiedMemoryAPI

    return UnifiedMemoryAPI(
        holo_memory=_build_optional_subsystem("holo", _build_default_holo_memory),
        fact_graph=_build_optional_subsystem("factgraph", _build_default_fact_graph),
        nks_query_engine=_build_optional_subsystem("nks", _build_default_nks_query_engine),
    )


def get_default_unified_memory_api() -> UnifiedMemoryAPI:
    global _default_unified_memory_api_singleton
    if _default_unified_memory_api_singleton is None:
        _default_unified_memory_api_singleton = build_default_unified_memory_api()
    return _default_unified_memory_api_singleton


def reset_default_unified_memory_api() -> None:
    global _default_unified_memory_api_singleton
    _default_unified_memory_api_singleton = None
