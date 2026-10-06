"""Regression for the engine FTS writer: `documents.body` raw, FTS body tokenized.

P0 fixed 2026-10-06 (BET-Y2Q4-T3-04). `KosIndexer._process_file` used to overwrite
`body` with its jieba-segmented form and let `_batch_write` reuse it for BOTH the
`documents` row and `documents_fts`, so:
  * `documents.body` stored tokenized text (segmentation spaces), diverging from the
    `maintenance/indexer.py` ingest path which stores raw; and
  * the FTS tokenization was an implicit side effect of that overwrite.

The invariant (kos/tokenize.py: "任何写 documents_fts 的地方都用 fts_text()") is
now explicit: `documents.body` = RAW text, `documents_fts.body` = `fts_text(raw)`.
This test fails against the pre-fix engine and passes after.
"""

from pathlib import Path

from kos.indexer import engine
from kos.tokenize import fts_text, jieba_available


def _index_one(tmp_path: Path, text: str):
    idx = engine.KosIndexer()
    idx.db_path = tmp_path / "kos.sqlite"
    conn = idx._connect()
    idx._init_schema(conn)
    conn.commit()

    doc = tmp_path / "doc.md"
    doc.write_text(text, encoding="utf-8")
    result = idx._process_file("doc.md", doc, "default", "full_text")
    assert result["action"] == "added", result
    idx._batch_write(conn, [result])
    return conn, result["doc"]


def test_documents_body_is_raw_and_fts_body_is_tokenized(tmp_path):
    raw = "# 中文标题\n\n这是一段中文正文，用于分词一致性测试。\n"
    conn, d = _index_one(tmp_path, raw)

    # The in-memory record keeps raw body + a separate tokenized FTS body.
    assert d["body"] == raw, "engine must keep documents.body raw"
    assert d["body_fts"] == fts_text(raw)
    if jieba_available():
        assert d["body_fts"] != raw, "FTS body must be segmented, not the raw text"

    # And the same holds for the rows actually written.
    row = conn.execute("SELECT body FROM documents WHERE doc_id=?", (d["doc_id"],)).fetchone()
    fts = conn.execute("SELECT body FROM documents_fts WHERE doc_id=?", (d["doc_id"],)).fetchone()
    assert row["body"] == raw
    assert fts["body"] == fts_text(raw)
    conn.close()
