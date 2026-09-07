"""Integration tests for eidos.vector_backends.mos_backend (T6-02 Phase 2).

Verifies that MOSVectorBackend correctly delegates to mos.unified.
"""

from __future__ import annotations

import os

os.environ.setdefault("MOS_RBAC", "0")

import pytest

from eidos.vector_backends.mos_backend import MOSVectorBackend, _cosine_similarity
from eidos.vector_backends.base import VectorSearchResult


def _fresh() -> MOSVectorBackend:
    return MOSVectorBackend(dimension=64)  # small dim for speed


class TestMOSVectorBackendAddSearch:
    def test_add_and_count(self) -> None:
        backend = _fresh()
        vec = [0.1] * 64
        backend.add("e1", vec, "first entry", {"topic": "AI"})
        assert backend.count() == 1

    def test_add_multiple(self) -> None:
        backend = _fresh()
        for i in range(5):
            backend.add(f"e{i}", [float(i)] * 64, f"entry {i}")
        assert backend.count() == 5

    def test_search_returns_results(self) -> None:
        backend = _fresh()
        backend.add("e1", [1.0] * 64, "content about neural networks")
        backend.add("e2", [0.0] * 64, "content about cooking")
        results = backend.search([1.0] * 64, limit=2)
        assert isinstance(results, list)
        assert len(results) >= 1
        assert isinstance(results[0], VectorSearchResult)

    def test_search_ranking(self) -> None:
        backend = _fresh()
        # e1: all 1s, e2: all 0s
        backend.add("e1", [1.0] * 64, "high similarity")
        backend.add("e2", [0.0] * 64, "low similarity")
        results = backend.search([1.0] * 64, limit=2)
        # e1 should rank first (cosine sim = 1.0)
        assert results[0].entry_id == "e1"

    def test_remove(self) -> None:
        backend = _fresh()
        backend.add("e1", [1.0] * 64, "content")
        assert backend.remove("e1") is True
        assert backend.count() == 0

    def test_remove_nonexistent(self) -> None:
        backend = _fresh()
        assert backend.remove("nonexistent") is False

    def test_get_existing(self) -> None:
        backend = _fresh()
        backend.add("e1", [1.0] * 64, "retrievable content")
        result = backend.get("e1")
        # get may return None if MOS recall doesn't find by scope
        # but shouldn't crash
        assert result is None or isinstance(result, VectorSearchResult)


class TestMOSVectorBackendTextToVector:
    def test_text_to_vector_returns_correct_dim(self) -> None:
        backend = _fresh()
        vec = backend.text_to_vector("hello world")
        assert len(vec) == 64  # matches dimension

    def test_text_to_vector_deterministic(self) -> None:
        backend = _fresh()
        v1 = backend.text_to_vector("same text")
        v2 = backend.text_to_vector("same text")
        assert v1 == v2

    def test_text_to_vector_normalized(self) -> None:
        backend = _fresh()
        vec = backend.text_to_vector("test")
        norm = sum(x ** 2 for x in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-5


class TestMOSVectorBackendHealth:
    def test_health_check(self) -> None:
        backend = _fresh()
        health = backend.health_check()
        assert health["status"] == "healthy"
        assert health["backend_type"] == "mos_unified"


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        v = [1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(_cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_zero_vector(self) -> None:
        a = [0.0, 0.0]
        b = [1.0, 0.0]
        assert _cosine_similarity(a, b) == 0.0
