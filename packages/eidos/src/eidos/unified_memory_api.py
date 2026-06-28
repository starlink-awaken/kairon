from __future__ import annotations

"""
_TRACE_CONTEXT = contextvars.ContextVar("_TRACE_CONTEXT", default=None)
---
Type: Interface
Status: ACTIVE
Version: 1.0.0
Owner: '@Copilot'
Authority: AGENTS.md
Layer: L3
Summary: 'UnifiedMemoryAPI — parallel multi-memory query bus (holo + factgraph + nks).'
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Unified Memory Api ≡ API
# 内涵 ≝ {Unified, Memory, Api}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, UnifiedMemoryApi)}
# 功能 ⊢ {Unified_Memory, Memory_Api, Api_Init}
# =============================================================================
# 🧠 Unified Memory API (M3-T4)
# 职责: 提供统一的跨记忆查询接口，并行查询 HoloMemory / FactGraph / NKS，
#       合并、去重、排序结果，向调用方隐藏底层记忆子系统差异。
import asyncio
import contextvars
import json
import logging
import math
import time
from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass, field
from typing import Any, NotRequired, Protocol, TypedDict, cast, runtime_checkable

_TRACE_CONTEXT: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar("_TRACE_CONTEXT", default=None)

_log = logging.getLogger(__name__)

__all__ = [
    "UnifiedMemoryAPI",
    "MemoryItem",
    "QueryResult",
    "build_default_unified_memory_api",
    "get_default_unified_memory_api",
    "reset_default_unified_memory_api",
]

# Canonical set of supported memory subsystem identifiers.
MEMORY_TYPES: frozenset[str] = frozenset({"holo", "factgraph", "nks"})

# Maximum length for dedup keys — prevents unbounded memory growth when
# query results contain very large content strings.
_DEDUP_KEY_MAX_LEN: int = 120

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
type MemoryMetadata = Mapping[str, JSONValue]


def build_default_unified_memory_api() -> UnifiedMemoryAPI:
    from eidos import (
        unified_memory_api_defaults as defaults_module,
    )

    return cast("UnifiedMemoryAPI", defaults_module.build_default_unified_memory_api())


def get_default_unified_memory_api() -> UnifiedMemoryAPI:
    from eidos import (
        unified_memory_api_defaults as defaults_module,
    )

    return cast("UnifiedMemoryAPI", defaults_module.get_default_unified_memory_api())


def reset_default_unified_memory_api() -> None:
    from eidos import (
        unified_memory_api_defaults as defaults_module,
    )

    defaults_module.reset_default_unified_memory_api()


class _MemoryWriteParams(TypedDict):
    key: str
    value: str
    importance: NotRequired[float]
    ttl: NotRequired[float]
    sacred: NotRequired[bool]
    tags: NotRequired[list[str] | None]


class _MemoryQueryParams(TypedDict):
    q: str
    memory_types: NotRequired[list[str] | None]
    limit: NotRequired[int]


class _MemoryForgetParams(TypedDict):
    key: str


class _MemoryResolveParams(TypedDict):
    key: str
    winner_value: str
    reason: NotRequired[str]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MemoryItem:
    """Single memory result from any subsystem."""

    content: str
    source: str  # "holo" | "factgraph" | "nks"
    score: float = 0.0
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def dedup_key(self) -> str:
        """Normalised key for deduplication.

        Truncates to :data:`_DEDUP_KEY_MAX_LEN` characters to prevent unbounded
        memory growth when content strings are very large (e.g. full documents).
        """
        return self.content.strip().lower()[:_DEDUP_KEY_MAX_LEN]


@dataclass
class QueryResult:
    items: list[MemoryItem]
    sources: list[str]
    total: int
    elapsed_ms: float


# ---------------------------------------------------------------------------
# Subsystem interface contract (documentation-only Protocol)
# ---------------------------------------------------------------------------


@runtime_checkable
class _SubsystemProtocol(Protocol):
    """Structural interface that every memory subsystem adapter must satisfy.

    This Protocol is used for documentation and optional ``isinstance`` checks
    only — :class:`UnifiedMemoryAPI` does **not** enforce it at runtime, which
    allows third-party subsystems that satisfy the duck-typed interface without
    explicitly subclassing this Protocol.

    Methods
    -------
    keyword_search(q: str, limit: int) -> list[dict]
        Search the subsystem for *q*, returning up to *limit* result dicts.
        Each dict should contain at least a ``"content"`` key (str) and
        optionally ``"score"`` (float, 0–1) and ``"metadata"`` (dict).

    query(q: str, limit: int) -> list[dict]
        Alternative entry-point used by fact-graph style subsystems.
        Same return contract as :meth:`keyword_search`.
    """

    def keyword_search(self, q: str, limit: int) -> list[dict]: ...  # noqa: E704
    def query(self, q: str, limit: int) -> list[dict]: ...  # noqa: E704
    def find_paths(self, q: str) -> Any: ...  # noqa: E704
    def read(self, key: str) -> str | None: ...  # noqa: E704
    def write(
        self,
        key: str,
        value: str,
        importance: float = ...,
        ttl: float = ...,
        sacred: bool = ...,
        tags: list[str] | None = ...,
    ) -> None: ...  # noqa: E704
    def forget(self, key: str) -> bool: ...  # noqa: E704
    def consolidate(self, key: str) -> bool: ...  # noqa: E704
    def consolidate_to_ltm(self) -> None: ...  # noqa: E704


# ---------------------------------------------------------------------------
# UnifiedMemoryAPI
# ---------------------------------------------------------------------------


class UnifiedMemoryAPI:
    """
    Parallel query across multiple memory subsystems.

    Usage::

        api = UnifiedMemoryAPI(
            holo_memory=holo,
            fact_graph=fact,
            nks_query_engine=nks,
        )
        result = await api.query("What is the B-OS architecture?")

    All subsystem arguments are optional. Callers that want the shared runtime
    wiring should prefer :func:`get_default_unified_memory_api`, which composes
    the default HoloMemory / FactGraph / NKS stack on a best-effort basis.

    Subsystem Return Format
    -----------------------
    Each per-subsystem adapter normalises raw results into :class:`MemoryItem`
    objects.  The table below shows the raw dict keys expected from each
    subsystem **before** normalisation:

    ============  ================================  ==========  ===========
    Subsystem     Content key(s)                    Score key   Notes
    ============  ================================  ==========  ===========
    ``holo``      ``"content"`` → ``"title"``       ``"score"`` full dict stored in ``metadata``; default score **0.5**
    ``factgraph`` ``"content"`` → ``"fact"``         ``"score"`` full dict stored in ``metadata``; default score **0.5**
    ``nks``       ``str(path)`` (PathResult.paths)   ``"score"`` constructed dict; default score **0.6** for paths, **0.5** for scalar result
    ============  ================================  ==========  ===========

    When a key is absent the fallback key (``→``) is tried, then ``str(r)``
    is used as the last resort.  All scores are normalised to the ``[0, 1]``
    range by convention; values outside that range are accepted but may sort
    unexpectedly.
    """

    DEFAULT_LIMIT = 10

    def __init__(
        self,
        holo_memory: Any | None = None,
        fact_graph: Any | None = None,
        nks_query_engine: Any | None = None,
    ) -> None:
        self.status = "active"
        self._holo: _SubsystemProtocol | None = holo_memory
        self._fact: _SubsystemProtocol | None = fact_graph
        self._nks: _SubsystemProtocol | None = nks_query_engine
        # Lazy-init MemorySifter (P-10-01: Think-and-Rank before inference).
        try:
            from eidos.organs.services.memory_sifter import MemorySifter

            self._sifter: MemorySifter | None = MemorySifter()
        except ImportError:
            self._sifter = None

    def _configured_query_subsystems(
        self, memory_types: list[str] | None = None
    ) -> list[tuple[str, Callable[[str, int], Coroutine[Any, Any, list[MemoryItem]]]]]:
        """Return configured query seams in the canonical aggregation order."""
        active = set(memory_types) if memory_types else set(MEMORY_TYPES)
        configured: list[tuple[str, Callable[[str, int], Coroutine[Any, Any, list[MemoryItem]]]]] = []
        if "holo" in active and self._holo is not None:
            configured.append(("holo", self._query_holo))
        if "factgraph" in active and self._fact is not None:
            configured.append(("factgraph", self._query_factgraph))
        if "nks" in active and self._nks is not None:
            configured.append(("nks", self._query_nks))
        return configured

    def _availability_status(self) -> dict[str, bool | str]:
        holo_available = self._holo is not None
        factgraph_available = self._fact is not None
        nks_available = self._nks is not None
        return {
            "status": ("healthy" if holo_available and factgraph_available and nks_available else "degraded"),
            "holo_available": holo_available,
            "factgraph_available": factgraph_available,
            "nks_available": nks_available,
        }

    async def query(
        self,
        q: str,
        memory_types: list[str] | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> QueryResult:
        """
        Parallel query across all configured memory subsystems.

        Args:
            q:            Natural-language query string.
            memory_types: Optional filter list (subsets of ``MEMORY_TYPES``).
                          ``None`` = query all available subsystems.
            limit:        Maximum items per subsystem before merging.

        Returns:
            :class:`QueryResult` with merged, deduplicated, score-sorted items.

            **Fault-tolerance guarantee**: if *all* subsystems fail their
            individual queries, an empty :class:`QueryResult` is returned
            (``items=[]``) rather than raising an exception.  When only a
            *subset* of subsystems fail, the results from the successful
            subsystems are returned and the failed ones are logged and skipped.
            Callers can inspect :attr:`QueryResult.sources` to determine which
            subsystems contributed results.

        Raises:
            ValueError: If *q* is empty or contains only whitespace.

        Example::

            result = await api.query("what is consciousness", limit=5, memory_types=["holo"])
            for item in result.items:
                print(item.content)
        """
        if not q or not q.strip():
            raise ValueError("query must be a non-empty string")

        t0 = time.monotonic()
        configured = self._configured_query_subsystems(memory_types)
        tasks = {source: asyncio.create_task(runner(q, limit)) for source, runner in configured}

        results: list[MemoryItem] = []
        sources_hit: list[str] = []

        if tasks:
            gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for source, outcome in zip(tasks.keys(), gathered, strict=False):
                if isinstance(outcome, Exception):
                    _log.warning("Memory subsystem %s failed: %s", source, outcome)
                    continue
                assert isinstance(outcome, list)
                results.extend(outcome)
                if outcome:
                    sources_hit.append(source)

        merged = self._merge(results, limit * 3)
        # Apply MemorySifter (Think-and-Rank) to compress context before returning.
        if self._sifter is not None and len(merged) > limit:
            try:
                from eidos.organs.holo_memory import MNode

                nodes = [
                    MNode(key=item.dedup_key(), value=item.content or "", importance=item.score or 0.0)
                    for item in merged
                ]
                sifted_nodes = await self._sifter.sift(q, nodes)
                sifted_keys = {n.key for n in sifted_nodes[:limit]}
                merged = [item for item in merged if item.dedup_key() in sifted_keys]
            except ImportError as exc:
                _log.debug("MemorySifter unavailable (fail-open): %s", exc)
        elapsed_ms = (time.monotonic() - t0) * 1000
        return QueryResult(
            items=merged,
            sources=sources_hit,
            total=len(merged),
            elapsed_ms=elapsed_ms,
        )

    def query_sync(
        self,
        q: str,
        memory_types: list[str] | None = None,
        limit: int = DEFAULT_LIMIT,
        timeout: float = 30.0,
    ) -> QueryResult:
        """Synchronous wrapper for :meth:`query`. Safe to call from any context.

        Delegates to :func:`nucleus.Z_Microkernel.organs.async_utils.run_sync`
        which handles nested-loop scenarios (e.g. Jupyter, FastAPI) without
        raising "cannot run a new event loop while another loop is running".

        Args:
            q:            Natural-language query string.
            memory_types: Optional subsystem filter (see :meth:`query`).
            limit:        Maximum items per subsystem before merging.
            timeout:      Maximum seconds to wait for the async query to
                          complete.  Defaults to ``30.0``.  Raises
                          :exc:`asyncio.TimeoutError` if the deadline is
                          exceeded before all subsystems respond.
        """
        from nucleus.Z_Microkernel.organs.async_utils import run_sync  # type: ignore[import-not-found]

        return cast("QueryResult", run_sync(asyncio.wait_for(self.query(q, memory_types, limit), timeout=timeout)))

    def health_check(self) -> dict:
        """Return operational health metrics for this unified memory bus.

        Delegates to the underlying HoloMemory instance when available;
        otherwise returns a minimal status dict reflecting subsystem
        availability without raising.
        """
        status: dict = self._availability_status()
        if self._holo is not None and hasattr(self._holo, "health_check"):
            try:
                holo_health = self._holo.health_check()
                holo_status = holo_health.get("status")
                status.update({k: v for k, v in holo_health.items() if k != "status"})
                if status["status"] == "healthy" and holo_status is not None:
                    status["status"] = holo_status
            except (OSError, ValueError, AttributeError) as exc:
                _log.warning("[UnifiedMemory] health_check: holo subsystem error: %s", exc)
                status["status"] = "degraded"
        return status

    async def _query_holo(self, q: str, limit: int) -> list[MemoryItem]:
        assert self._holo is not None
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, self._holo.keyword_search, q, limit)
        items = []
        for r in raw or []:
            content = r.get("content") or r.get("title") or str(r)
            score_val = r.get("score", 0.5)
            if not isinstance(score_val, (int, float)):
                score_val = 0.5
            items.append(
                MemoryItem(
                    content=str(content),
                    source="holo",
                    score=float(score_val),
                    metadata=cast(dict[str, JSONValue], r),
                )
            )
        return items

    async def _query_factgraph(self, q: str, limit: int) -> list[MemoryItem]:
        assert self._fact is not None
        loop = asyncio.get_running_loop()
        try:
            raw = await loop.run_in_executor(None, self._fact.query, q, limit)
        except AttributeError:
            # FactGraph implementation does not expose a .query() method —
            # subsystem is unavailable; skip gracefully.
            _log.warning("[UnifiedMemory] FactGraph subsystem missing .query() method — skipping")
            return []
        except (TypeError, ValueError) as exc:
            # Gracefully degrade: return empty list on query failure.
            # fault-tolerance: all subsystems degrade independently — a bad
            # call signature or unexpected data shape must not take down the
            # whole query bus.
            _log.error("[UnifiedMemory] FactGraph query error: %s", exc)
            return []
        items = []
        for r in raw or []:
            content = r.get("content") or r.get("fact") or str(r)
            score_val = r.get("score", 0.5)
            if not isinstance(score_val, (int, float)):
                score_val = 0.5
            items.append(
                MemoryItem(
                    content=str(content),
                    source="factgraph",
                    score=float(score_val),
                    metadata=cast(dict[str, JSONValue], r),
                )
            )
        return items

    async def _query_nks(self, q: str, limit: int) -> list[MemoryItem]:
        assert self._nks is not None
        loop = asyncio.get_running_loop()
        try:
            # GraphQueryEngine.find_paths returns PathResult objects
            path_result = await loop.run_in_executor(None, self._nks.find_paths, q)
            if hasattr(path_result, "paths"):
                raw = [{"content": str(p), "score": 0.6} for p in (path_result.paths or [])[:limit]]
            else:
                raw = [{"content": str(path_result), "score": 0.5}]
            if not raw:
                _log.debug("[UnifiedMemory] NKS query returned empty result set for %r", q)
        except RuntimeError as exc:
            # Infrastructure/subsystem failure — unknown error level
            _log.error("[UnifiedMemory] NKS subsystem error: %s", exc)
            raw = []
        except (TypeError, ValueError) as exc:
            # Gracefully degrade: return empty result on bad data / unexpected
            # NKS API shape.
            # fault-tolerance: all subsystems degrade independently — failures
            # in one subsystem never affect results from the others.
            _log.error("[UnifiedMemory] NKS query unexpected error: %s", exc)
            raw = []
        except AttributeError as exc:
            # Subsystem completely unavailable (method does not exist)
            _log.warning("[UnifiedMemory] NKS subsystem unavailable (missing attribute): %s", exc)
            raw = []
        items = []
        for r in raw or []:
            content = str(r.get("content", ""))
            score_val = r.get("score", 0.5)
            if not isinstance(score_val, (int, float)):
                score_val = 0.5
            score = float(score_val)
            items.append(MemoryItem(content=content, source="nks", score=score, metadata=cast(dict[str, JSONValue], r)))
        return items

    # ── Agentic Memory Management ──────────────────────────────────────────────

    async def store(
        self,
        key: str,
        value: str,
        importance: float = 0.5,
        ttl: float = 3600.0,
        sacred: bool = False,
        tags: list[str] | None = None,
    ) -> None:
        """
        Store a memory fragment with consensus checking (RFC-003).
        """
        if self._holo is not None:
            loop = asyncio.get_running_loop()

            # 1. 冲突检测逻辑 (Consensus Check)
            try:
                # HoloMemory.read 返回的是 str | None (真值内容)
                old_value = await loop.run_in_executor(None, self._holo.read, key)

                if old_value is not None and old_value != value:
                    # 获取旧分（默认为 0.5，HoloMemory 并不直接返回分值给 read 调用，需要单独获取或使用约定）
                    # 简化逻辑：内容不同即触发冲突，除非新值声明为 sacred
                    if not sacred:
                        _log.warning("⚠️ [Memory] Conflict detected for key '%s'.", key)
                        _tc_val = _TRACE_CONTEXT.get()
                        conflict_data = {
                            "key": key,
                            "old_value": old_value,
                            "new_value": value,
                            "timestamp": time.time(),
                            "trace_id": _tc_val.get("trace_id") if _tc_val else None,
                        }
                        # 记录冲突项
                        conflict_key = f"conflict:{key}"
                        await self.store(conflict_key, json.dumps(conflict_data), importance=1.0, sacred=True)
                        await self.consolidate(conflict_key)  # 显式持久化到 LTM 以便搜索
                        return  # 挂起写入
            except (AttributeError, TypeError, ValueError, OSError, RuntimeError) as e:
                _log.debug("[Memory] Consensus check error (fail-safe to write): %s", e)

            # 2. 正式写入
            holo = self._holo
            assert holo is not None
            await loop.run_in_executor(
                None,
                lambda: holo.write(
                    key=key,
                    value=value,
                    importance=importance,
                    ttl=ttl,
                    sacred=sacred,
                    tags=tags,
                ),
            )

    async def _handle_write(self, params: _MemoryWriteParams) -> dict[str, object]:
        """处理记忆写入请求。"""
        key = params.get("key")
        value = params.get("value")
        if not isinstance(key, str) or not key or not isinstance(value, str):
            return {"status": "error", "message": "key and value are required"}
        importance = params.get("importance", 0.5)
        if not isinstance(importance, (int, float)) or isinstance(importance, bool):
            return {"status": "error", "message": "importance must be a number"}
        if not math.isfinite(float(importance)) or not (0.0 <= float(importance) <= 1.0):
            return {"status": "error", "message": "importance must be in [0, 1]"}
        ttl = params.get("ttl", 3600.0)
        if not isinstance(ttl, (int, float)) or isinstance(ttl, bool):
            return {"status": "error", "message": "ttl must be a number"}
        if not math.isfinite(float(ttl)) or float(ttl) <= 0:
            return {"status": "error", "message": "ttl must be positive"}
        sacred = params.get("sacred", False)
        if not isinstance(sacred, bool):
            return {"status": "error", "message": "sacred must be a boolean"}
        tags = params.get("tags")
        if tags is not None and (not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags)):
            return {"status": "error", "message": "tags must be a list of strings"}

        await self.store(
            key=key,
            value=value,
            importance=float(importance),
            ttl=float(ttl),
            sacred=sacred,
            tags=tags,
        )
        return {"status": "success", "key": key}

    async def _handle_query(self, params: _MemoryQueryParams) -> dict[str, object]:
        """处理记忆查询请求。"""
        q = params.get("q")
        if not isinstance(q, str) or not q.strip():
            return {"status": "error", "message": "query 'q' is required"}
        limit = params.get("limit", 10)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            return {"status": "error", "message": "limit must be a positive integer"}
        memory_types = params.get("memory_types")
        if memory_types is not None:
            if not isinstance(memory_types, list) or any(
                not isinstance(memory_type, str) for memory_type in memory_types
            ):
                return {"status": "error", "message": "memory_types must be a list of strings"}
            if any(memory_type not in MEMORY_TYPES for memory_type in memory_types):
                return {"status": "error", "message": "memory_types contains unknown type"}

        result = await self.query(
            q=q,
            memory_types=memory_types,
            limit=limit,
        )
        return {
            "status": "success",
            "items": [item.__dict__ for item in result.items],
            "total": result.total,
            "elapsed_ms": result.elapsed_ms,
        }

    async def _handle_forget(self, params: _MemoryForgetParams) -> dict[str, str]:
        """处理记忆删除请求。"""
        key = params.get("key")
        if not isinstance(key, str) or not key:
            return {"status": "error", "message": "key is required"}

        success = await self.forget(key)
        return {"status": "success" if success else "error", "key": key}

    async def _handle_resolve(self, params: _MemoryResolveParams) -> dict[str, str]:
        """[RFC-003] 处理记忆冲突调解接口。"""
        key = params.get("key")
        winner_value = params.get("winner_value")
        reason = params.get("reason", "Manual adjudication")

        if not isinstance(key, str) or not key or not isinstance(winner_value, str):
            return {"status": "error", "message": "key and winner_value are required"}
        if not isinstance(reason, str):
            return {"status": "error", "message": "reason must be a string"}
        canonical_key = key.removeprefix("conflict:")
        if not canonical_key:
            return {"status": "error", "message": "key and winner_value are required"}

        # 1. 写入优胜值（强制覆盖）
        await self.store(canonical_key, winner_value, importance=1.0, sacred=True)

        # 2. 清除冲突记录
        await self.forget(f"conflict:{canonical_key}")

        _log.info(
            "✅ [Memory] Conflict for key '%s' resolved. Reason: %s",
            canonical_key,
            reason,
        )
        return {"status": "success", "message": f"Conflict for '{canonical_key}' resolved."}

    async def update(
        self,
        key: str,
        value: str,
        importance: float = 0.5,
        ttl: float = 3600.0,
        sacred: bool = False,
        tags: list[str] | None = None,
    ) -> None:
        """
        Update an existing memory fragment (currently same as store/upsert).
        """
        await self.store(key, value, importance, ttl, sacred, tags)

    async def forget(self, key: str) -> bool:
        """
        Explicitly forget a memory fragment by key.
        """
        if self._holo is not None:
            loop = asyncio.get_running_loop()
            holo = self._holo
            return await loop.run_in_executor(None, lambda: holo.forget(key))
        return False

    async def consolidate(self, key: str) -> bool:
        """
        Manually trigger consolidation of a WM node to LTM.
        """
        if self._holo is not None:
            loop = asyncio.get_running_loop()
            holo = self._holo
            return await loop.run_in_executor(None, lambda: holo.consolidate(key))
        return False

    async def consolidate_all(self) -> None:
        """
        Trigger consolidation of all eligible nodes in WM to LTM.
        """
        if self._holo is not None:
            loop = asyncio.get_running_loop()
            holo = self._holo
            await loop.run_in_executor(None, lambda: holo.consolidate_to_ltm())

    # ── Merge / dedup / sort ──────────────────────────────────────────────────

    @staticmethod
    def _merge(items: list[MemoryItem], cap: int) -> list[MemoryItem]:
        """Deduplicate by content key, then sort by score descending.

        Deduplication algorithm:
          1. Each item is keyed by :meth:`MemoryItem.dedup_key` — a normalised,
             lowercased, 120-char prefix of the content string.
          2. When two items share the same key the one with the *higher* score
             wins, ensuring cross-subsystem duplicates always surface the most
             confident hit.
          3. After deduplication the surviving items are sorted by ``score``
             descending and truncated to *cap* entries.
        """
        seen: dict[str, MemoryItem] = {}
        for item in items:
            key = item.dedup_key()
            # Keep the higher-scoring item when duplicates collide.
            if key not in seen or item.score > seen[key].score:
                seen[key] = item
        return sorted(seen.values(), key=lambda x: x.score or 0.0, reverse=True)[:cap]
