#!/usr/bin/env python3
# ruff: noqa
"""
KOS Semantic Search — LanceDB vector index for cross-domain semantic retrieval.

Usage:
    kos-semantic build              # Build/rebuild vector index
    kos-semantic build --domain X   # Build for single domain
    kos-semantic search "query"     # Semantic search
    kos-semantic status             # Index stats

Requires: pip install lancedb sentence-transformers --break-system-packages
"""

import json
import sqlite3
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
from kos.config import get_vault_ops_dir  # type: ignore[unused-ignore, import-not-found]

VAULT_OPS_DIR = get_vault_ops_dir()
from kos.config import get_artifact_path
from typing import Any

# ── Configuration ──────────────────────────────────────

MODEL_NAME = "all-MiniLM-L6-v2"  # 384 dims, English+multilingual, 80MB
EMBEDDING_DIM = 384
VECTOR_TABLE = "kos_documents"
BATCH_SIZE = 64

# ── Lazy imports (heavy deps) ──────────────────────────

_embedder = None
_lancedb = None


def _get_embedder() -> Any:
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(MODEL_NAME)
    return _embedder


def _get_lancedb() -> Any:
    global _lancedb
    if _lancedb is None:
        import lancedb  # type: ignore[import-untyped]

        db_path = Path(get_artifact_path("retrievalDatabase"))
        lancedb_dir = db_path.parent / "vectors"  # type: ignore[attr-defined]
        lancedb_dir.mkdir(parents=True, exist_ok=True)
        _lancedb = lancedb.connect(str(lancedb_dir))
    return _lancedb


# ── Build ──────────────────────────────────────────────


def build_index(domain: str | None = None) -> dict:  # type: ignore[unknown]
    """Embed all indexed documents and store in LanceDB."""
    try:
        embedder = _get_embedder()  # type: ignore[no-untyped-call]
        db = _get_lancedb()  # type: ignore[no-untyped-call]
    except ImportError as e:
        return {"error": f"Dependency missing: {e}. Install: pip install lancedb sentence-transformers"}

    # Get documents from FTS5
    db_path = Path(get_artifact_path("retrievalDatabase"))
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    where = ""
    params = []
    if domain:
        where = "WHERE zone = ?"
        params.append(domain)

    docs = conn.execute(
        f"SELECT doc_id, title, body, zone, kind, canonical_path FROM documents {where}", params
    ).fetchall()
    conn.close()

    total = len(docs)
    if total == 0:
        return {"error": "No documents indexed. Run 'kos index' first.", "count": 0}

    # Prepare data
    texts = []
    metadata = []
    for d in docs:
        # Combine title + body for embedding
        text = f"{d['title'] or ''}\n{d['body'] or ''}"[:2000]
        texts.append(text)
        metadata.append(
            {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "zone": d["zone"],
                "kind": d["kind"],
                "canonical_path": d["canonical_path"],
            }
        )

    # Embed in batches
    print(f"  Embedding {total} documents ({EMBEDDING_DIM}d)...", file=sys.stderr)
    t0 = time.time()
    embeddings = []
    for i in range(0, total, BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        batch_vecs = embedder.encode(batch, show_progress_bar=False)
        embeddings.extend(batch_vecs.tolist())
        if (i + BATCH_SIZE) % 500 == 0:
            print(f"    {min(i + BATCH_SIZE, total)}/{total}", file=sys.stderr)
    elapsed = time.time() - t0

    # Store in LanceDB
    table_data = []
    for i, meta in enumerate(metadata):
        table_data.append(
            {
                "vector": embeddings[i],
                "doc_id": meta["doc_id"],
                "title": meta["title"],
                "zone": meta["zone"],
                "kind": meta["kind"],
                "canonical_path": meta["canonical_path"],
            }
        )

    # Drop and recreate table
    try:
        db.drop_table(VECTOR_TABLE)
    except Exception:
        pass

    tbl = db.create_table(VECTOR_TABLE, table_data)
    count = tbl.count_rows()

    return {
        "embedded": count,
        "dimensions": EMBEDDING_DIM,
        "model": MODEL_NAME,
        "elapsed_seconds": round(elapsed, 1),
        "domain": domain or "all",
    }


# ── Search ─────────────────────────────────────────────


def semantic_search(query: str, limit: int = 10, domain: str | None = None) -> dict:  # type: ignore[unknown]
    """Semantic vector search with optional domain filter."""
    try:
        embedder = _get_embedder()  # type: ignore[no-untyped-call]
        db = _get_lancedb()  # type: ignore[no-untyped-call]
    except ImportError as e:
        return {"error": f"Dependency missing: {e}", "results": [], "count": 0}

    if VECTOR_TABLE not in db.table_names():
        return {"error": "Vector index not built. Run: kos-semantic build", "results": [], "count": 0}

    # Embed query
    q_vec = embedder.encode([query]).tolist()[0]

    # Search
    tbl = db.open_table(VECTOR_TABLE)

    if domain:
        results = tbl.search(q_vec).limit(limit * 3).to_list()
        # Filter post-search by domain
        results = [r for r in results if r.get("zone") == domain][:limit]
    else:
        results = tbl.search(q_vec).limit(limit).to_list()

    return {
        "query": query,
        "results": [
            {
                "doc_id": r["doc_id"],
                "title": r.get("title", ""),
                "zone": r.get("zone", ""),
                "kind": r.get("kind", ""),
                "canonical_path": r.get("canonical_path", ""),
                "_distance": r.get("_distance", 0),
            }
            for r in results
        ],
        "count": len(results),
        "backend": "lancedb",
        "model": MODEL_NAME,
    }


def hybrid_search(query: str, limit: int = 10) -> dict:  # type: ignore[type-arg]
    """Combine FTS5 + LanceDB results via RRF fusion."""
    # FTS5 results
    db_path = Path(get_artifact_path("retrievalDatabase"))
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        fts_results = conn.execute(
            """SELECT d.doc_id, d.title, d.zone, d.kind, d.canonical_path
               FROM documents_fts f JOIN documents d ON f.doc_id = d.doc_id
               WHERE documents_fts MATCH ? ORDER BY rank LIMIT ?""",
            (query, limit * 2),
        ).fetchall()
    except sqlite3.OperationalError:
        fts_results = []
    conn.close()

    # Semantic results
    sem = semantic_search(query, limit=limit * 2)
    sem_results = sem.get("results", [])

    # RRF fusion
    k = 60
    scores: dict[str, float] = {}
    docs = {}

    for rank, r in enumerate(fts_results):
        d = dict(r)
        doc_id = d["doc_id"]
        docs[doc_id] = d
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)

    for rank, r in enumerate(sem_results):
        doc_id = r["doc_id"]
        if doc_id not in docs:
            docs[doc_id] = {
                "doc_id": doc_id,
                "title": r["title"],
                "zone": r["zone"],
                "kind": r["kind"],
                "canonical_path": r["canonical_path"],
            }
        # Semantic results get slight boost for semantic relevance
        scores[doc_id] = scores.get(doc_id, 0) + 1.2 / (k + rank + 1)

    ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]
    results = [{**docs[doc_id], "_score": round(score, 4)} for doc_id, score in ranked]

    return {
        "query": query,
        "results": results,
        "count": len(results),
        "backend": "hybrid (FTS5 + LanceDB)",
    }


# ── Status ─────────────────────────────────────────────


def status() -> dict:  # type: ignore[type-arg]
    try:
        db = _get_lancedb()  # type: ignore[no-untyped-call]
        tables = db.table_names()
        if VECTOR_TABLE in tables:
            tbl = db.open_table(VECTOR_TABLE)
            count = tbl.count_rows()
            return {"status": "active", "documents": count, "model": MODEL_NAME, "dimensions": EMBEDDING_DIM}
        return {"status": "not_built", "documents": 0}
    except ImportError:
        return {"status": "unavailable", "error": "lancedb or sentence-transformers not installed"}


# ── Main ───────────────────────────────────────────────


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    domain = None
    limit = 10
    for i, a in enumerate(sys.argv):
        if a == "--domain" and i + 1 < len(sys.argv):
            domain = sys.argv[i + 1]
        if a == "--limit" and i + 1 < len(sys.argv):
            try:
                limit = int(sys.argv[i + 1])
            except ValueError:
                pass

    if cmd == "build":
        result = build_index(domain)  # type: ignore[arg-type]
    elif cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        result = semantic_search(query, limit=limit, domain=domain)  # type: ignore[arg-type]
    elif cmd == "hybrid":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        result = hybrid_search(query, limit=limit)
    elif cmd == "status":
        result = status()
    else:
        result = {"error": f"Unknown: {cmd}", "usage": "build|search|hybrid|status"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
