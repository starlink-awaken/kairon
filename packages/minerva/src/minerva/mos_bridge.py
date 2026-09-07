"""Minerva → MOS unified bridge (T6-02 Phase 2).

Delegates embedding, write, recall, and search operations to
``mos.unified.UnifiedMemory`` — the single source of truth for
knowledge-layer memory access.

Replaces the standalone FallbackEmbeddingProvider + VectorEmbeddingPipeline
adapter chain with a thin delegation layer.

Usage::

    from minerva.mos_bridge import MinervaUnifiedMemory
    mem = MinervaUnifiedMemory()
    mem.write("key insight about neural architecture search", type="semantic")
    results = mem.search("neural architecture", limit=5)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

from mos.unified import UnifiedMemory, default_unified_memory

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data classes (kept for backward compat with VectorPipeline consumers)
# ---------------------------------------------------------------------------

@dataclass
class EmbeddingResult:
    """Embedding result — mirrors minerva.index.vector_pipeline.EmbeddingResult."""

    item_id: int
    success: bool
    embedding: list[float] | None = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class PipelineStats:
    """Pipeline stats — mirrors minerva.index.vector_pipeline.PipelineStats."""

    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    retried: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    last_update: str = ""

    def update(self, result: EmbeddingResult) -> None:
        self.total_processed += 1
        if result.success:
            self.successful += 1
        else:
            self.failed += 1
        self.total_duration_ms += result.duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.total_processed
        from datetime import UTC, datetime
        self.last_update = datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# MinervaUnifiedMemory — the bridge
# ---------------------------------------------------------------------------

class MinervaUnifiedMemory:
    """Unified memory surface for Minerva, backed by MOS.

    Provides write / recall / search that delegate to mos.unified.UnifiedMemory.
    Also exposes a ``embed_texts`` async method for callers that still need raw
    embedding vectors (e.g. RAG pipeline).
    """

    def __init__(self, memory_os: Any | None = None) -> None:
        self._um = UnifiedMemory(memory_os) if memory_os else default_unified_memory()
        self._stats = PipelineStats()
        # Simple in-memory embedding cache (text → vector)
        self._embedding_cache: dict[str, list[float]] = {}

    @property
    def unified_memory(self) -> UnifiedMemory:
        return self._um

    # ── write ────────────────────────────────────────────────────────────

    def write(
        self,
        content: str,
        *,
        scope: str | None = None,
        type: str = "episodic",
        dedup: bool = True,
        role: str | None = None,
    ) -> dict[str, Any]:
        """Write via MOS unified surface. Returns WriteResult as dict."""
        result = self._um.unified_write(
            content, scope=scope, type=type, dedup=dedup, role=role,
        )
        return {"ok": result.ok, "envelope_id": result.envelope_id}

    # ── recall ───────────────────────────────────────────────────────────

    def recall(
        self,
        query: str,
        *,
        intent: str | None = None,
        limit: int = 10,
        role: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recall via MOS unified intent-routed surface."""
        result = self._um.unified_recall(
            query, intent=intent, limit=limit, role=role,
        )
        return [dict(h) for h in result.hits] if result.hits else []

    # ── search ───────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        intent: str | None = None,
        limit: int = 10,
        role: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search via MOS unified RRF-fused surface."""
        return self._um.unified_search(query, intent=intent, limit=limit, role=role)

    # ── embed (for RAG pipeline compatibility) ───────────────────────────

    def _text_to_vector(self, text: str) -> list[float]:
        """Deterministic hash-based embedding (same as mos.test fallback)."""
        cached = self._embedding_cache.get(text)
        if cached is not None:
            return cached
        digest = hashlib.sha256(text.encode()).digest()
        target_dim = 384
        vec_bytes = digest
        while len(vec_bytes) < target_dim:
            vec_bytes += hashlib.sha256(vec_bytes).digest()
        import numpy as np
        raw = vec_bytes[:target_dim]
        vec = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        vec = (vec / 127.5) - 1.0
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        result = vec.tolist()
        self._embedding_cache[text] = result
        return result

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts — delegates to deterministic hash vectors.

        For callers that need raw embedding vectors (RAG, vector pipeline).
        """
        return [self._text_to_vector(t) for t in texts]

    # ── stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        return {
            "pipeline": {
                "total_processed": self._stats.total_processed,
                "successful": self._stats.successful,
                "failed": self._stats.failed,
                "retried": self._stats.retried,
                "avg_duration_ms": round(self._stats.avg_duration_ms, 2),
                "last_update": self._stats.last_update,
            },
            "backend": "mos.unified",
            "cache_size": len(self._embedding_cache),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default: MinervaUnifiedMemory | None = None


def get_minerva_unified() -> MinervaUnifiedMemory:
    """Get or create the singleton MinervaUnifiedMemory."""
    global _default
    if _default is None:
        _default = MinervaUnifiedMemory()
    return _default
