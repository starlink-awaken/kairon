"""build_index 安全性: 失败批次不错位、增量不删旧向量、查询路径不同步建库。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

lancedb = pytest.importorskip("lancedb")

from kos import semantic


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "kos-index.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE documents (doc_id TEXT, title TEXT, body TEXT, zone TEXT, kind TEXT, canonical_path TEXT)"
    )
    conn.commit()
    conn.close()
    vec_db = lancedb.connect(str(tmp_path / "vectors"))
    monkeypatch.setattr(semantic, "get_artifact_path", lambda _name: str(db_path))
    monkeypatch.setattr(semantic, "_get_lancedb", lambda: vec_db)
    monkeypatch.setattr(semantic, "_get_embed_backend", lambda: "omlx")
    monkeypatch.setattr(semantic, "BATCH_SIZE", 1)

    def add_docs(*doc_ids: str) -> None:
        c = sqlite3.connect(db_path)
        c.executemany(
            "INSERT INTO documents VALUES (?, ?, ?, 'z', 'k', ?)", [(d, d, f"body {d}", f"/{d}") for d in doc_ids]
        )
        c.commit()
        c.close()

    return vec_db, add_docs


def _vec_for(text: str) -> list[float]:
    return [float(len(text)), 1.0]


def test_failed_batch_does_not_shift_vectors(env, monkeypatch: pytest.MonkeyPatch) -> None:
    vec_db, add_docs = env
    add_docs("a", "bb", "ccc")
    monkeypatch.setattr(
        semantic, "_embed_texts", lambda texts: [] if "bb" in texts[0] else [_vec_for(t) for t in texts]
    )

    semantic.build_index()

    rows = vec_db.open_table(semantic.VECTOR_TABLE).to_arrow().to_pylist()
    assert sorted(r["doc_id"] for r in rows) == ["a", "ccc"]
    for row in rows:
        assert list(row["vector"]) == _vec_for(f"{row['doc_id']}\nbody {row['doc_id']}")


def test_incremental_keeps_existing_vectors(env, monkeypatch: pytest.MonkeyPatch) -> None:
    vec_db, add_docs = env
    monkeypatch.setattr(semantic, "_embed_texts", lambda texts: [_vec_for(t) for t in texts])
    add_docs("a")
    semantic.build_index()
    add_docs("b")

    semantic.build_index(incremental=True)

    assert sorted(vec_db.open_table(semantic.VECTOR_TABLE).to_arrow()["doc_id"].to_pylist()) == ["a", "b"]


def test_search_without_index_does_not_build(env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(semantic, "build_index", lambda *a, **k: pytest.fail("search must not build synchronously"))

    result = semantic.semantic_search("anything")

    assert result["count"] == 0
    assert "not built" in result["error"]
