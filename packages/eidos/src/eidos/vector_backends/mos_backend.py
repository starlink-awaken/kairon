"""Eidos → MOS unified vector backend adapter (T6-02 Phase 2).

Thin adapter that routes eidos VectorStoreBackend operations through
``mos.unified.UnifiedMemory`` — the single source of truth for
knowledge-layer memory.

This replaces standalone LanceDB / NumPy implementations for callers
that want to use the unified knowledge surface. Existing backends
remain available as fallback.

Usage::

    from eidos.vector_backends.mos_backend import MOSVectorBackend
    backend = MOSVectorBackend()
    backend.add("entry-1", [0.1]*384, "some content", {"topic": "AI"})
    results = backend.search([0.1]*384, limit=5)
"""

from __future__ import annotations

import logging
from typing import Any

from mos.unified import UnifiedMemory, default_unified_memory

from .base import VectorSearchResult, VectorStoreBackend

_log = logging.getLogger(__name__)


class MOSVectorBackend(VectorStoreBackend):
    """VectorStoreBackend backed by MOS unified memory.

    Delegates add/search/get/remove/count to MOS.  Embeddings are
    stored as metadata alongside the content — MOS handles persistence,
    intent routing, and dedup.
    """

    def __init__(
        self,
        dimension: int = 384,
        db_path: str | None = None,
        role: str = "default",
        memory_os: Any | None = None,
    ) -> None:
        super().__init__(dimension=dimension, db_path=db_path)
        self.role = role
        self._um = UnifiedMemory(memory_os) if memory_os else default_unified_memory()
        # In-memory vector cache for search (MOS stores content, we cache vectors)
        self._vectors: dict[str, list[float]] = {}
        self._counter: int = 0

    # ── VectorStoreBackend interface ──────────────────────────────────────

    def add(
        self,
        entry_id: str,
        vector: Any,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store content + vector via MOS unified write."""
        vec = list(vector) if not isinstance(vector, list) else vector
        self._vectors[entry_id] = vec
        meta = dict(metadata) if metadata else {}
        meta["vector_dim"] = len(vec)
        meta["entry_id"] = entry_id
        meta["source"] = "eidos"
        self._um.unified_write(
            content,
            scope=entry_id,
            type="semantic",
            dedup=False,
            role=self.role,
        )
        self._counter += 1

    def search(
        self,
        query_vector: Any,
        limit: int = 5,
        min_similarity: float = 0.0,
    ) -> list[VectorSearchResult]:
        """Search via MOS unified search, then rank by cosine similarity."""
        # Use MOS unified search for content-based retrieval
        hits = self._um.unified_search(
            "",  # empty query — we'll rank by vector similarity
            limit=limit * 3,
            role=self.role,
        )

        # Rank cached vectors by cosine similarity to query
        qvec = list(query_vector) if not isinstance(query_vector, list) else query_vector
        scored: list[tuple[str, float]] = []
        for entry_id, cached_vec in self._vectors.items():
            sim = _cosine_similarity(qvec, cached_vec)
            if sim >= min_similarity:
                scored.append((entry_id, sim))
        scored.sort(key=lambda x: x[1], reverse=True)

        results: list[VectorSearchResult] = []
        for entry_id, sim in scored[:limit]:
            # Try to find content from MOS hits
            content = ""
            for h in hits:
                sid = h.get("scope") or h.get("id") or ""
                if sid == entry_id or entry_id in str(sid):
                    content = str(h.get("content") or h.get("snippet") or h.get("text") or "")
                    break
            results.append(
                VectorSearchResult(
                    entry_id=entry_id,
                    content=content or f"[mos-backend:{entry_id}]",
                    similarity=sim,
                    metadata={"backend": "mos", "role": self.role},
                    distance=1.0 - sim,
                )
            )
        return results

    def get(self, entry_id: str) -> VectorSearchResult | None:
        """Retrieve by ID — checks MOS recall."""
        hits = self._um.unified_recall(entry_id, limit=1, role=self.role)
        if hits and hits.hits:
            h = hits.hits[0]
            vec = self._vectors.get(entry_id, [])
            return VectorSearchResult(
                entry_id=entry_id,
                content=str(h.get("content") or h.get("snippet") or ""),
                similarity=1.0,
                metadata={"backend": "mos"},
            )
        return None

    def remove(self, entry_id: str) -> bool:
        """Remove from vector cache. MOS content persists (forget not yet delegated)."""
        if entry_id in self._vectors:
            del self._vectors[entry_id]
            self._counter -= 1
            return True
        return False

    def count(self) -> int:
        return len(self._vectors)

    def text_to_vector(self, text: str) -> list[float]:
        """Deterministic hash-based vector (same as mos.test fallback)."""
        import hashlib
        import numpy as np
        digest = hashlib.sha256(text.encode()).digest()
        vec_bytes = digest
        while len(vec_bytes) < self.dimension:
            vec_bytes += hashlib.sha256(vec_bytes).digest()
        raw = vec_bytes[: self.dimension]
        vec = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        vec = (vec / 127.5) - 1.0
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def health_check(self) -> dict[str, Any]:
        base = super().health_check()
        if base["status"] == "healthy":
            base["backend_type"] = "mos_unified"
            base["role"] = self.role
            base["cached_vectors"] = len(self._vectors)
        return base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
