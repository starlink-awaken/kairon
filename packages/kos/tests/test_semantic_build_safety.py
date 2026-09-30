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

    def add_docs(*doc_ids: str, body: str | None = None) -> None:
        c = sqlite3.connect(db_path)
        c.executemany(
            "INSERT INTO documents VALUES (?, ?, ?, 'z', 'k', ?)",
            [(d, d, body or f"body {d}", f"/{d}") for d in doc_ids],
        )
        c.commit()
        c.close()

    return vec_db, add_docs


def _vec_for(text: str) -> list[float]:
    return [float(len(text)), 1.0]


def test_failed_batch_aborts_build(env, monkeypatch: pytest.MonkeyPatch) -> None:
    """批失败必须中止构建 —— 窟窿库查询时看不出缺失, 比构建失败更糟(2026-09-29 实测跳了 2 万块)。"""
    vec_db, add_docs = env
    add_docs("a", "bb", "ccc")
    monkeypatch.setattr(
        semantic, "_embed_texts", lambda texts: [] if "bb" in texts[0] else [_vec_for(t) for t in texts]
    )
    monkeypatch.setattr(semantic.time, "sleep", lambda *_: None)  # 重试不真等

    with pytest.raises(RuntimeError, match="aborting build"):
        semantic.build_index()


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


def test_batch_size_env(monkeypatch):
    """KOS_EMBED_BATCH 可调(omlx 嵌入端点大批量阵发 502, 小批存活率高)。"""
    monkeypatch.setenv("KOS_EMBED_BATCH", "8")
    import importlib

    import kos.semantic as sem

    importlib.reload(sem)
    assert sem.BATCH_SIZE == 8


def test_incremental_falls_back_when_fingerprint_mismatch(env, monkeypatch: pytest.MonkeyPatch) -> None:
    """旧模型向量表 + incremental → 必须退化为全量, 不能 0 条跳过假成功(2026-09-30 实测)。"""
    vec_db, add_docs = env
    add_docs("a")
    monkeypatch.setattr(semantic, "_embed_texts", lambda texts: [_vec_for(t) for t in texts])
    semantic.build_index()  # 建表并写指纹
    # 伪造"别的模型": 改掉指纹文件
    meta_path = semantic._embed_meta_path()
    meta_path.write_text('{"fingerprint": "deadbeef"}')
    add_docs("b")
    r = semantic.build_index(incremental=True)
    rows = vec_db.open_table(semantic.VECTOR_TABLE).to_arrow()["doc_id"].to_pylist()
    assert sorted(rows) == ["a", "b"], f"指纹不匹配的增量必须全量重建: {rows}"


def test_checkpoint_resume_after_abort(env, monkeypatch: pytest.MonkeyPatch) -> None:
    """嵌入中断后重启: checkpoint 落盘的块不重嵌, 续跑补齐 —— 此前 abort 全丢(2026-09-30 实测 81% 白跑)。"""
    vec_db, add_docs = env
    long_body = "主干内容。" * 300  # 确保 4 文档 ≥ 2 批(BATCH_SIZE=2 按 chunk 计)
    add_docs("a", "b", "c", "d", body=long_body)
    calls = {"n": 0}

    def ok_then_dead(texts):
        calls["n"] += 1
        if calls["n"] > 2:  # 批 1 起(含重试)永久失败 → abort; 批 0 已嵌在 pending
            return []
        return [_vec_for(t) for t in texts]

    monkeypatch.setattr(semantic, "_embed_texts", ok_then_dead)
    monkeypatch.setattr(semantic, "BATCH_SIZE", 2)
    monkeypatch.setattr(semantic.time, "sleep", lambda *_: None)
    try:
        semantic.build_index()
    except RuntimeError:
        pass  # 预期 abort
    assert semantic.CHECKPOINT_TABLE in vec_db.table_names()  # 已有落盘断点

    # 续跑: 只嵌剩余的, 完成后正式表 + checkpoint 清除
    monkeypatch.setattr(semantic, "_embed_texts", lambda texts: [_vec_for(t) for t in texts])
    semantic.build_index()
    assert set(vec_db.open_table(semantic.VECTOR_TABLE).to_arrow()["doc_id"].to_pylist()) == {"a", "b", "c", "d"}
    assert semantic.CHECKPOINT_TABLE not in vec_db.table_names()
