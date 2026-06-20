#!/usr/bin/env python3
# ruff: noqa
"""
KOS Ontology Engine v1.0 — 本体推理与实体管理
"""

import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from kos.config import get_vault_ops_dir  # type: ignore[unused-ignore, import-not-found]

import hashlib
import json
from typing import Any, cast
import re
import sqlite3
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VAULT_OPS_DIR = get_vault_ops_dir()

from kos.config import get_artifact_path, get_workspace_manifest

# ── Patterns ─────────────────────────────────────────────

PREDICATE_RE = re.compile(r"(\w+)::\[\[([^\]]+)\]\]")
ENTITY_REF_RE = re.compile(
    r"\[(person|org|project|regulation|doc|concept|event|role|axiom|principle|theory|framework|skill|consensus|task)-([\w-]+)\]",
    re.IGNORECASE,
)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
MD_HEADING_RE = re.compile(r"^###\s+(.+)", re.MULTILINE)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(#([^)]+)\)")
MD_TAG_RE = re.compile(r"#(\w[\w/-]*)")

# ── Manifest-driven configuration (lazy) ────────────────
# These are computed at first call, not import time, so the module
# can be imported without a fully configured workspace.

_MANIFEST = None


def _manifest() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    global _MANIFEST
    if _MANIFEST is None:
        _MANIFEST = get_workspace_manifest()
    return cast("dict[str, Any]", _MANIFEST)


def _entity_sources() -> list[str]:  # type: ignore[no-untyped-def]
    sources = _manifest().get("entitySources", [])
    if not sources:
        raise RuntimeError(
            "manifest 'entitySources' is empty or missing. "
            "Run 'kos init' to scaffold a workspace, or add entitySources to your manifest."
        )
    return cast("list[str]", sources)


def entity_files() -> list[str]:  # type: ignore[no-untyped-def]
    return _entity_sources()


def cross_domain_file() -> str:  # type: ignore[no-untyped-def]
    return _entity_sources()[0]


PREFIX_LIST = [
    "person-",
    "org-",
    "project-",
    "regulation-",
    "doc-",
    "concept-",
    "role-",
    "axiom-",
    "principle-",
    "theory-",
    "framework-",
    "skill-",
    "consensus-",
    "task-",
]

_PREDICATE_PATTERNS = None


def _predicate_patterns() -> dict[str, list[str]]:  # type: ignore[no-untyped-def]
    """Load predicate patterns from manifest, merging all language sets."""
    global _PREDICATE_PATTERNS
    if _PREDICATE_PATTERNS is not None:
        return _PREDICATE_PATTERNS
    configured = _manifest().get("predicatePatterns", {})
    if not configured:
        raise RuntimeError(
            "manifest 'predicatePatterns' is empty or missing. "
            "Run 'kos init' to scaffold a workspace, or add predicatePatterns to your manifest."
        )
    merged: dict[str, Any] = {}
    for lang_patterns in configured.values():
        for predicate, patterns in lang_patterns.items():
            merged.setdefault(predicate, []).extend(patterns)
    _PREDICATE_PATTERNS = merged
    return merged


TYPE_MAP = {
    "person": "Person",
    "people": "Person",
    "org": "Organization",
    "organization": "Organization",
    "project": "Project",
    "regulation": "Regulation",
    "doc": "Document",
    "document": "Document",
    "concept": "Concept",
    "event": "Event",
    "role": "Role",
    "axiom": "Axiom",
    "principle": "Principle",
    "theory": "Theory",
    "framework": "Framework",
    "skill": "Skill",
    "consensus": "Consensus",
    "task": "Task",
}

KNOWN_PREDICATES = [
    "works_at",
    "seconded_to",
    "reports_to",
    "works_on",
    "described_in",
    "derived_from",
    "related_to",
    "conforms_to",
    "depends_on",
    "triggers",
    "member_of",
    "manages",
    "belongs_to",
    "applied_in",
]


def get_db() -> sqlite3.Connection:  # type: ignore[no-untyped-def]
    from pathlib import Path

    path = Path(get_artifact_path("retrievalDatabase"))
    if not path.exists():
        raise FileNotFoundError(f"Retrieval DB not found: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_schema(conn) -> None:  # type: ignore[no-untyped-def]
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kos_entities (
            entity_id   TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            label       TEXT NOT NULL,
            aliases     TEXT,
            description TEXT,
            primary_zone TEXT,
            source_file TEXT,
            metadata    TEXT,
            updated_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS kos_relations (
            source_id   TEXT,
            predicate   TEXT,
            target_id   TEXT,
            confidence  REAL DEFAULT 1.0,
            source_doc  TEXT,
            source_type TEXT DEFAULT 'manual',
            updated_at  TEXT,
            PRIMARY KEY (source_id, predicate, target_id)
        );
        CREATE TABLE IF NOT EXISTS kos_entity_docs (
            entity_id TEXT,
            doc_id    TEXT,
            relevance REAL DEFAULT 0.5,
            PRIMARY KEY (entity_id, doc_id)
        );
        CREATE TABLE IF NOT EXISTS kos_ontology_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_kos_rel_src ON kos_relations(source_id);
        CREATE INDEX IF NOT EXISTS idx_kos_rel_tgt ON kos_relations(target_id);
        CREATE INDEX IF NOT EXISTS idx_kos_ent_doc ON kos_entity_docs(entity_id);
    """)


# ── Step 1: Extract entities from source files ───────────


def extract() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    added = 0

    for file_path in entity_files():
        p = Path(file_path)
        if not p.exists():
            print(f"  ⚠️  Not found: {file_path}", file=sys.stderr)
            continue
        content = p.read_text(encoding="utf-8")
        zone = "guozhuan" if "国转中心" in str(p) else "gongwen"

        # Match entity sections like: ### person-xxx
        for m in MD_HEADING_RE.finditer(content):
            heading = m.group(1).strip()
            em = re.match(
                r"(person|org|project|regulation|doc|concept|event|role|axiom|principle|theory|framework|skill|consensus|task)-([\w-]+)",
                heading,
                re.IGNORECASE,
            )
            if not em:
                continue
            etype_raw = em.group(1).lower()
            eid_raw = em.group(2)
            etype = TYPE_MAP.get(etype_raw, etype_raw.capitalize())
            entity_id = f"{etype[0].upper()}:{eid_raw}"

            # Extract body until next ### or ---
            body_start = m.end()
            next_section = re.search(r"(^###|\n---)", content[body_start:], re.MULTILINE)
            body_end = body_start + next_section.start() if next_section else len(content)
            body = content[body_start:body_end].strip()

            # Extract label: **名称**: 夏同学 or **名称**：夏同学
            label = eid_raw.replace("-", " ").replace("_", " ")
            # Try multiple patterns for 名称 extraction
            name_match = re.search(r"\*\*名称\*\*\s*[：:]\s*(.+)", body)
            if not name_match:
                # Try without 名称 prefix: first non-empty meaningful line
                for line in body.split("\n"):
                    line = line.strip().lstrip("-").strip()
                    nm = re.match(r"\*\*([^*]+)\*\*\s*[：:]\s*(.+)", line)
                    if nm and nm.group(1).strip() not in (
                        "名称",
                        "标签",
                        "角色",
                        "背景",
                        "关联",
                        "详见",
                        "当前状态",
                        "成员",
                        "双重使命",
                    ):
                        label = nm.group(2).strip()
                        name_match = re.search(r"(.+)", label)  # dummy to pass the check below
                        break
            if name_match:
                label = name_match.group(1).strip()

            # Extract description: prefer background, fallback to role, then cleaned body
            for key in ["背景", "角色", "职责"]:
                dm = re.search(rf"\*\*{key}\*\*\s*[：:]\s*(.+?)(?:\n\*\*|\n##|\n\n\n|\Z)", body, re.DOTALL)
                if dm:
                    desc = dm.group(1).strip()
                    if len(desc) > 10:
                        description = desc[:200]
                        break
            else:
                clean_body = re.sub(r"\*\*[^*]+\*\*[：:]?\s*", "", body).strip()
                description = clean_body[:200]

            # Extract relations with per-relation predicate matching
            tags = MD_TAG_RE.findall(body)
            for m_link in MD_LINK_RE.finditer(body):
                m_link.group(1)
                rid = m_link.group(2)
                for prefix in PREFIX_LIST:
                    if rid.startswith(prefix):
                        etype_char = prefix[0].upper()
                        target_id = f"{etype_char}:{rid[len(prefix) :]}"
                        # Per-relation predicate: look at text after the link up to next | or [
                        post_link_start = m_link.end()
                        next_sep = re.search(r"[\[|]", body[post_link_start : post_link_start + 80])
                        post_text = body[post_link_start : post_link_start + 80]
                        if next_sep:
                            post_text = post_text[: next_sep.start()]
                        # Match predicate from the text between link and next separator
                        pred = "related_to"
                        for kn, patterns in _predicate_patterns().items():
                            for pattern in patterns:
                                if re.search(pattern, post_text):
                                    pred = kn
                                    break
                            if pred != "related_to":
                                break
                        # Insert with specific predicate
                        conn.execute(
                            """INSERT OR REPLACE INTO kos_relations
                            (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                            VALUES (?,?,?,?,?,?,?)""",
                            (entity_id, pred, target_id, 0.8, str(p), "auto-extract", now),
                        )
                        break

            # Associate entity with source document
            canonical = "kos::guozhuan::_工作机制/wiki/ENTITIES.md"
            doc_id = hashlib.sha1(canonical.encode()).hexdigest()
            conn.execute(
                """INSERT OR REPLACE INTO kos_entity_docs
                (entity_id,doc_id,relevance) VALUES (?,?,?)""",
                (entity_id, doc_id, 1.0),
            )

            # Upsert entity
            conn.execute(
                """INSERT OR REPLACE INTO kos_entities
                (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    entity_id,
                    etype,
                    label,
                    json.dumps([label]),
                    description,
                    zone,
                    str(p),
                    json.dumps({"tags": tags}),
                    now,
                ),
            )
            added += 1

    # ── Named-predicate entity extraction (entities.md format) ──
    ENTITY_HEADING_RE = re.compile(r"^###\s+([POJCDRANTFKSW]):(\S+)", re.MULTILINE)
    PRED_LINE_RE = re.compile(r"-\s+(\w+)::\[\[([A-Z]):([^\]]+)\]\]")
    TYPE_PREFIX_MAP = {
        "P": "Person",
        "O": "Organization",
        "J": "Project",
        "C": "Concept",
        "D": "Document",
        "R": "Role",
        "A": "Axiom",
        "N": "Principle",
        "T": "Theory",
        "F": "Framework",
        "K": "Skill",
        "S": "Consensus",
        "W": "Task",
    }

    for file_path in entity_files():
        p = Path(file_path)
        if not p.exists() or "entities.md" not in str(p):
            continue
        content = p.read_text(encoding="utf-8")
        for em in ENTITY_HEADING_RE.finditer(content):
            etype_char = em.group(1)
            eid = em.group(2)
            etype = TYPE_PREFIX_MAP.get(etype_char, "Concept")
            entity_id = f"{etype_char}:{eid}"
            body_start = em.end()
            ns = re.search(r"\n###", content[body_start:])
            body = content[body_start : body_start + ns.start()] if ns else content[body_start:]
            label = eid.replace("-", " ").replace("_", " ").title()
            for pm in PRED_LINE_RE.finditer(body):
                target_id = f"{pm.group(2)}:{pm.group(3)}"
                conn.execute(
                    """INSERT OR REPLACE INTO kos_relations
                    (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (entity_id, pm.group(1), target_id, 1.0, str(p), "manual", now),
                )
            conn.execute(
                """INSERT OR REPLACE INTO kos_entities
                (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    entity_id,
                    etype,
                    label,
                    json.dumps([label]),
                    body.strip()[:200],
                    "obsidian",
                    str(p),
                    json.dumps({"source": "entities.md"}),
                    now,
                ),
            )
            added += 1

    conn.commit()
    # ── Gongwen domain structure (NOT extracted as Concepts) ──
    # Directory names like "组织机构", "制度规范" are file categories, not knowledge concepts.
    # They are accessible via KOS zone browsing (`kos domains`, `kos status`).
    # See: kos-entity-governance.py for entity quality rules.

    conn.commit()
    conn.close()
    return {"extracted": added, "timestamp": now}


# ── Step 2: Infer relations from indexed documents ───────


def infer() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]
    now = datetime.now().strftime("%Y%m%d%H%M%S")

    # Get all entity labels for matching
    entities = {
        r["entity_id"]: json.loads(r["aliases"] or "[]") + [r["label"]]
        for r in conn.execute("SELECT entity_id,label,aliases FROM kos_entities").fetchall()
    }

    if not entities:
        conn.close()
        return {"inferred": 0, "error": "No entities extracted yet. Run 'extract' first."}

    # Scan all indexed documents for predicate::[[target]] patterns
    inferred = 0
    docs = conn.execute("SELECT doc_id,canonical_path,body FROM documents WHERE body != ''").fetchall()

    for doc in docs:
        body = doc["body"] or ""
        for m in PREDICATE_RE.finditer(body):
            predicate = m.group(1)
            if predicate not in KNOWN_PREDICATES:
                continue
            target_raw = m.group(2)

            # Match target against known entities
            best_match = None
            best_conf = 0
            for eid, aliases in entities.items():
                for alias in aliases:
                    if alias in target_raw or target_raw in alias:
                        score = len(alias) / max(len(target_raw), 1)
                        if score > best_conf:
                            best_conf = score  # type: ignore[assignment]
                            best_match = eid

            if best_match and best_conf > 0.3:
                # Find source entity from doc associations
                source_ents = conn.execute(
                    "SELECT entity_id FROM kos_entity_docs WHERE doc_id=?", (doc["doc_id"],)
                ).fetchall()
                if not source_ents:
                    continue
                source_id = source_ents[0]["entity_id"]
                confidence = min(best_conf, 0.8)  # cap auto-extracted confidence

                conn.execute(
                    """INSERT OR REPLACE INTO kos_relations
                    (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (source_id, predicate, best_match, confidence, doc["canonical_path"], "auto-extract", now),
                )
                conn.execute(
                    """INSERT OR REPLACE INTO kos_entity_docs
                    (entity_id,doc_id,relevance) VALUES (?,?,?)""",
                    (best_match, doc["doc_id"], confidence),
                )
                inferred += 1

    conn.commit()
    conn.close()
    return {"inferred": inferred, "timestamp": now}


# ── Step 3: Entity card ──────────────────────────────────


def card(entity_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]

    entity = conn.execute("SELECT * FROM kos_entities WHERE entity_id=?", (entity_id,)).fetchone()
    if not entity:
        conn.close()
        return {"error": f"Entity not found: {entity_id}"}

    # Outgoing relations
    outgoing = conn.execute(
        "SELECT predicate,target_id,confidence,source_doc FROM kos_relations WHERE source_id=?", (entity_id,)
    ).fetchall()

    # Incoming relations
    incoming = conn.execute(
        "SELECT source_id,predicate,confidence,source_doc FROM kos_relations WHERE target_id=?", (entity_id,)
    ).fetchall()

    # Document count by zone
    doc_zones = conn.execute(
        """SELECT d.zone, COUNT(*) as cnt
           FROM kos_entity_docs ed JOIN documents d ON ed.doc_id=d.doc_id
           WHERE ed.entity_id=? GROUP BY d.zone""",
        (entity_id,),
    ).fetchall()

    conn.close()

    return {
        "entity_id": entity["entity_id"],
        "entity_type": entity["entity_type"],
        "label": entity["label"],
        "aliases": json.loads(entity["aliases"] or "[]"),
        "description": entity["description"],
        "primary_zone": entity["primary_zone"],
        "outgoing_relations": [
            {"predicate": r["predicate"], "target": r["target_id"], "confidence": r["confidence"]} for r in outgoing
        ],
        "incoming_relations": [
            {"source": r["source_id"], "predicate": r["predicate"], "confidence": r["confidence"]} for r in incoming
        ],
        "document_zones": {r["zone"]: r["cnt"] for r in doc_zones},
        "total_docs": sum(r["cnt"] for r in doc_zones),
    }


# ── Step 4: Find path between entities ───────────────────


def find_path(from_id: str, to_id: str) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
    conn = get_db()  # type: ignore[no-untyped-call]
    # BFS on relation graph
    edges = conn.execute("SELECT source_id,predicate,target_id FROM kos_relations").fetchall()
    conn.close()

    adj: dict[str, list[tuple[str, str]]] = {}
    for s, p, t in edges:
        adj.setdefault(s, []).append((t, p))

    queue = deque([(from_id, [])])  # type: ignore[var-annotated]
    visited = {from_id}

    while queue:
        node, path = queue.popleft()
        if node == to_id:
            return {"path": path, "hops": len(path)}
        for neighbor, predicate in adj.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [{"from": node, "predicate": predicate, "to": neighbor}]))

    return {"error": f"No path found between {from_id} and {to_id}"}


# ── Step 5: Discover implicit connections ────────────────


def discover() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    conn = get_db()  # type: ignore[no-untyped-call]
    # Find entities that co-occur in same docs but have no explicit relation
    implicit = conn.execute("""
        SELECT e1.entity_id as a, e2.entity_id as b, COUNT(*) as shared_docs
        FROM kos_entity_docs e1
        JOIN kos_entity_docs e2 ON e1.doc_id = e2.doc_id AND e1.entity_id < e2.entity_id
        WHERE NOT EXISTS (
            SELECT 1 FROM kos_relations r
            WHERE (r.source_id=e1.entity_id AND r.target_id=e2.entity_id)
               OR (r.source_id=e2.entity_id AND r.target_id=e1.entity_id)
        )
        GROUP BY 1,2
        HAVING shared_docs >= 2
        ORDER BY shared_docs DESC
        LIMIT 20
    """).fetchall()

    conn.close()
    return {
        "implicit_connections": [
            {"entity_a": r["a"], "entity_b": r["b"], "shared_docs": r["shared_docs"]} for r in implicit
        ]
    }


def list_entities(entity_type: str | None = None) -> dict:
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]
    if entity_type:
        rows = conn.execute(
            "SELECT entity_id,entity_type,label,primary_zone FROM kos_entities WHERE entity_type=? ORDER BY entity_type,label",
            (entity_type.capitalize(),),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT entity_id,entity_type,label,primary_zone FROM kos_entities ORDER BY entity_type,label"
        ).fetchall()
    conn.close()
    return {"entities": [dict(r) for r in rows], "count": len(rows)}


# ── Main ─────────────────────────────────────────────────


def enrich() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Link entities to indexed documents via text search."""
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    entities = conn.execute("SELECT entity_id,label,aliases FROM kos_entities").fetchall()
    enriched = 0

    for e in entities:
        label = e["label"]
        aliases = json.loads(e["aliases"] or "[]")
        search_terms = [label] + [a for a in aliases if a != label]

        for term in search_terms[:3]:  # max 3 terms per entity
            # Sanitize: FTS5 doesn't like special chars, use simple word matching
            safe_term = re.sub(r'[.()（）\-*"~]', " ", term)[:60].strip()
            if len(safe_term) < 2:
                continue
            try:
                docs = conn.execute(
                    "SELECT doc_id FROM documents_fts WHERE documents_fts MATCH ? LIMIT 10", (safe_term,)
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for d in docs:
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO kos_entity_docs (entity_id,doc_id,relevance) VALUES (?,?,?)",
                        (e["entity_id"], d["doc_id"], 0.5),
                    )
                    enriched += 1
                except Exception:
                    logger.error("Unexpected exception caught", exc_info=True)  # type: ignore[name-defined]
                    pass

    conn.commit()
    conn.close()
    return {"enriched": enriched, "timestamp": now}


def graph(entity_type: str | None = None) -> dict:
    """Generate Mermaid graph of entity relations."""
    conn = get_db()  # type: ignore[no-untyped-call]
    edges = conn.execute("SELECT source_id,predicate,target_id FROM kos_relations").fetchall()
    entities = {r["entity_id"]: dict(r) for r in conn.execute("SELECT * FROM kos_entities").fetchall()}
    conn.close()

    lines = ["```mermaid", "graph LR"]
    seen = set()
    for s, p, t in edges:
        if entity_type and entities.get(s, {}).get("entity_type") != entity_type:
            continue
        sl = entities.get(s, {}).get("label", s)
        tl = entities.get(t, {}).get("label", t)
        # Truncate long labels for readability
        sl = sl[:20] + ("…" if len(sl) > 20 else "")
        tl = tl[:20] + ("…" if len(tl) > 20 else "")
        key = (sl, tl)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f'    "{sl}" -->|{p}| "{tl}"')
    lines.append("```")
    return {"graph": "\n".join(lines), "nodes": len(entities), "edges": len(edges)}


def _record_source_mtimes(conn) -> None:  # type: ignore[no-untyped-def]
    """Persist current entitySources file mtimes into kos_ontology_meta."""
    now = datetime.now().isoformat()
    meta: dict[str, Any] = {"rebuilt_at": now, "sources": {}}
    for fp in entity_files():
        p = Path(fp)
        if p.exists():
            meta["sources"][fp] = p.stat().st_mtime
    conn.execute(
        "INSERT OR REPLACE INTO kos_ontology_meta (key,value) VALUES (?,?)", ("source_mtimes", json.dumps(meta))
    )
    conn.commit()


def check_stale() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Compare entitySources file mtimes to last rebuild. Returns stale info."""
    from pathlib import Path

    db_path = Path(get_artifact_path("retrievalDatabase"))
    if not db_path.exists():  # type: ignore[attr-defined]
        return {"stale": True, "reason": "never_built", "changes": []}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    init_schema(conn)  # type: ignore[no-untyped-call]
    row = conn.execute("SELECT value FROM kos_ontology_meta WHERE key='source_mtimes'").fetchone()
    if not row:
        conn.close()
        return {"stale": True, "reason": "never_built", "changes": []}

    last = json.loads(row["value"])
    changes: list[dict[str, Any]] = []
    for fp in entity_files():
        p = Path(fp)
        if not p.exists():
            changes.append({"file": fp, "status": "missing"})
            continue
        last_mtime = last.get("sources", {}).get(fp)
        curr_mtime = p.stat().st_mtime
        if last_mtime is None or abs(curr_mtime - last_mtime) > 0:
            changes.append({"file": fp, "status": "modified", "last": last_mtime, "current": curr_mtime})

    conn.close()
    return {"stale": bool(changes), "changes": changes, "last_rebuilt": last.get("rebuilt_at")}


def rebuild() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """One-command rebuild: clear + extract + enrich + record mtimes."""
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]
    conn.execute("DELETE FROM kos_relations")
    conn.execute("DELETE FROM kos_entities")
    conn.execute("DELETE FROM kos_entity_docs")
    conn.commit()
    conn.close()
    r1 = extract()  # type: ignore[no-untyped-call]
    r2 = enrich()  # type: ignore[no-untyped-call]
    # Record mtimes after successful rebuild
    conn = get_db()  # type: ignore[no-untyped-call]
    _record_source_mtimes(conn)  # type: ignore[no-untyped-call]
    conn.close()
    return {"cleared": True, "extracted": r1["extracted"], "enriched": r2.get("enriched", 0)}


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "rebuild":
        print(json.dumps(rebuild(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif cmd == "check-stale":
        print(json.dumps(check_stale(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]

    elif cmd == "enrich":
        print(json.dumps(enrich(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif cmd == "extract":
        print(json.dumps(extract(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif cmd == "infer":
        print(json.dumps(infer(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif cmd == "card":
        eid = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(card(eid), ensure_ascii=False, indent=2))
    elif cmd == "path":
        a = sys.argv[2] if len(sys.argv) > 2 else ""
        b = sys.argv[3] if len(sys.argv) > 3 else ""
        print(json.dumps(find_path(a, b), ensure_ascii=False, indent=2))
    elif cmd == "discover":
        print(json.dumps(discover(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif cmd == "graph":
        etype = None
        for i, a in enumerate(sys.argv):
            if a == "--type" and i + 1 < len(sys.argv):
                etype = sys.argv[i + 1]
        print(json.dumps(graph(etype), ensure_ascii=False, indent=2))  # type: ignore[arg-type]
    elif cmd == "list":
        etype = None
        for i, a in enumerate(sys.argv):
            if a == "--type" and i + 1 < len(sys.argv):
                etype = sys.argv[i + 1]
        print(json.dumps(list_entities(etype), ensure_ascii=False, indent=2))  # type: ignore[arg-type]
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
