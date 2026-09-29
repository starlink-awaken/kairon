"""kos rebuild-fts: 从 documents 表已存的标题/正文重建 documents_fts(统一分词), 不重新扫描文件。

用于分词规则变更后刷新全文索引(2026-09-29: 线上文档经 `kos ingest` 写入时未切中文)。
单事务: 删除旧索引 → 逐条以 fts_text() 写入 → 核对行数, 不一致则回滚。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path
from kos.tokenize import fts_text


def rebuild_fts(db_path: str | Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    path = Path(db_path or get_artifact_path("retrievalDatabase"))
    conn = sqlite3.connect(str(path))
    t0 = time.time()
    docs = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
    before = conn.execute("SELECT count(*) FROM documents_fts").fetchone()[0]
    if dry_run:
        conn.close()
        return {"ok": True, "dry_run": True, "db": str(path), "documents": docs, "fts_rows_before": before}
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM documents_fts")
        rows = conn.execute("SELECT doc_id, title, body, canonical_path FROM documents").fetchall()
        conn.executemany(
            "INSERT INTO documents_fts (doc_id,title,body,tags,canonical_path) VALUES (?,?,?,?,?)",
            ((d, fts_text(t or ""), fts_text(b or ""), "", p) for d, t, b, p in rows),
        )
        after = conn.execute("SELECT count(*) FROM documents_fts").fetchone()[0]
        if after != docs:
            conn.rollback()
            return {"ok": False, "error": f"行数不一致: documents={docs} fts={after}, 已回滚", "db": str(path)}
        conn.commit()
        conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('optimize')")
        conn.commit()
    finally:
        conn.close()
    return {
        "ok": True,
        "db": str(path),
        "documents": docs,
        "fts_rows_before": before,
        "fts_rows_after": after,
        "secs": round(time.time() - t0, 1),
    }
