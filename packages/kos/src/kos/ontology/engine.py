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
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
VAULT_OPS_DIR = get_vault_ops_dir()

from kos.config import get_artifact_path, get_workspace_manifest

# Re-export schema 组 (抽到 schema.py, 保持 engine API 向后兼容 + mypy 跟踪)
from kos.ontology.schema import (  # type: ignore[no-redef]
    ENTITY_REF_RE,
    FRONTMATTER_RE,
    KNOWN_PREDICATES,
    MD_HEADING_RE,
    MD_LINK_RE,
    MD_TAG_RE,
    PREFIX_LIST,
    PREDICATE_RE,
    TYPE_MAP,
    _entity_sources,
    _manifest,
    _predicate_patterns,
    cross_domain_file,
    entity_files,
    get_db,
    init_schema,
)

# Re-export extract 组 (抽到 extract.py, wave 1, 保持 engine API)
from kos.ontology.extract import (  # type: ignore[no-redef]
    _auto_discover_metadata,
    extract,
)


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

    # 5. Semantic reasoning on L0 architecture & X-axis governance checks
    inferred += _reason_governance_rules(conn, now)

    conn.commit()
    conn.close()
    return {"inferred": inferred, "timestamp": now}


def _reason_governance_rules(conn: sqlite3.Connection, now: str) -> int:
    """结合 L0 层级架构与 X 层一致性规则进行本体推理推导"""
    inferred = 0

    # 1. L0 层级依赖冲突推导
    layer_weights = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "I0": 5, "M0": 6, "X": 7}

    rows = conn.execute(
        """SELECT r.source_id as proj, r.target_id as layer_concept 
           FROM kos_relations r 
           WHERE r.predicate='member_of' AND r.source_id LIKE 'J:%' AND r.target_id LIKE 'C:Layer-%'"""
    ).fetchall()

    proj_layers = {}
    for r in rows:
        proj = r["proj"]
        layer_concept = r["layer_concept"]
        layer_name = layer_concept.replace("C:Layer-", "")
        if layer_name in layer_weights:
            proj_layers[proj] = layer_name

    dep_rows = conn.execute(
        """SELECT source_id, predicate, target_id FROM kos_relations 
           WHERE source_id LIKE 'J:%' AND target_id LIKE 'J:%' AND predicate != 'violates_layer_dependency'"""
    ).fetchall()

    for dep in dep_rows:
        src = dep["source_id"]
        tgt = dep["target_id"]
        src_layer = proj_layers.get(src)
        tgt_layer = proj_layers.get(tgt)

        if src_layer and tgt_layer:
            # 如果源层级优先级值低于目标层级（即逆向引用，如 L1 引用 L3），说明发生了架构设计违规！
            if layer_weights[src_layer] < layer_weights[tgt_layer]:
                conn.execute(
                    """INSERT OR REPLACE INTO kos_relations
                    (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (src, "violates_layer_dependency", tgt, 0.95, "ontology-rules", "reasoning", now),
                )
                inferred += 1

    # 2. X4 规则链审计：找出所有未绑定 ADR 决策的 Axiom 规则
    axioms = conn.execute("SELECT entity_id, label FROM kos_entities WHERE entity_type='Axiom'").fetchall()
    for ax in axioms:
        ax_id = ax["entity_id"]
        has_adr = conn.execute(
            "SELECT 1 FROM kos_relations WHERE source_id=? AND predicate='related_to' AND target_id LIKE 'D:ADR-%'",
            (ax_id,),
        ).fetchone()

        if not has_adr:
            conn.execute(
                """INSERT OR REPLACE INTO kos_relations
                (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                VALUES (?,?,?,?,?,?,?)""",
                (ax_id, "lacks_adr_evidence", "A:CR-X4-HEALTH-SSOT", 0.9, "ontology-rules", "reasoning", now),
            )
            inferred += 1

    return inferred


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

    # Enhanced: Document list (top 20 most relevant)
    doc_list = conn.execute(
        """SELECT d.doc_id, d.title, d.zone, d.canonical_path, d.updated_at, ed.relevance
           FROM kos_entity_docs ed JOIN documents d ON ed.doc_id=d.doc_id
           WHERE ed.entity_id=? ORDER BY ed.relevance DESC, d.updated_at DESC LIMIT 20""",
        (entity_id,),
    ).fetchall()

    # Enhanced: Entity graph (all entities within 2 hops)
    entity_graph = _entity_graph_2hop(conn, entity_id)

    # Enhanced: Related entities (co-occurring in same docs)
    related_entities = conn.execute(
        """SELECT e2.entity_id, e2.label, e2.entity_type, COUNT(*) as shared_docs
           FROM kos_entity_docs ed1
           JOIN kos_entity_docs ed2 ON ed1.doc_id = ed2.doc_id AND ed1.entity_id != ed2.entity_id
           JOIN kos_entities e2 ON ed2.entity_id = e2.entity_id
           WHERE ed1.entity_id = ?
           GROUP BY e2.entity_id ORDER BY shared_docs DESC LIMIT 10""",
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
        # Enhanced fields
        "documents": [
            {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "zone": d["zone"],
                "canonical_path": d["canonical_path"],
                "updated_at": d["updated_at"],
                "relevance": d["relevance"],
            }
            for d in doc_list
        ],
        "entity_graph": entity_graph,
        "related_entities": [
            {
                "entity_id": r["entity_id"],
                "label": r["label"],
                "type": r["entity_type"],
                "shared_docs": r["shared_docs"],
            }
            for r in related_entities
        ],
    }


def _entity_graph_2hop(conn: sqlite3.Connection, entity_id: str) -> dict[str, Any]:
    """Get the entity graph within 2 hops of the given entity."""
    # Direct neighbors (1 hop)
    neighbors_1 = conn.execute(
        """SELECT DISTINCT target_id as entity_id FROM kos_relations WHERE source_id = ?
           UNION
           SELECT DISTINCT source_id as entity_id FROM kos_relations WHERE target_id = ?""",
        (entity_id, entity_id),
    ).fetchall()

    neighbor_ids = {r["entity_id"] for r in neighbors_1}
    neighbor_ids.add(entity_id)

    # 2-hop neighbors
    if neighbor_ids:
        placeholders = ",".join(["?"] * len(neighbor_ids))
        neighbors_2 = conn.execute(
            f"""SELECT DISTINCT target_id as entity_id FROM kos_relations 
                WHERE source_id IN ({placeholders}) AND target_id NOT IN ({placeholders})
                UNION
                SELECT DISTINCT source_id as entity_id FROM kos_relations 
                WHERE target_id IN ({placeholders}) AND source_id NOT IN ({placeholders})""",
            list(neighbor_ids) * 4,
        ).fetchall()
        for r in neighbors_2:
            neighbor_ids.add(r["entity_id"])

    # Get all entities and relations in the graph
    if not neighbor_ids:
        return {"nodes": [], "edges": []}

    placeholders = ",".join(["?"] * len(neighbor_ids))
    nodes = conn.execute(
        f"SELECT entity_id, entity_type, label FROM kos_entities WHERE entity_id IN ({placeholders})",
        list(neighbor_ids),
    ).fetchall()

    edges = conn.execute(
        f"""SELECT source_id, predicate, target_id FROM kos_relations 
            WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})""",
        list(neighbor_ids) * 2,
    ).fetchall()

    return {
        "nodes": [{"id": n["entity_id"], "type": n["entity_type"], "label": n["label"]} for n in nodes],
        "edges": [{"source": e["source_id"], "predicate": e["predicate"], "target": e["target_id"]} for e in edges],
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


def deduplicate_entities() -> dict[str, Any]:
    """Merge duplicate entities based on label similarity.

    Returns:
        Dict with merge results.
    """
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]

    # Find entities with duplicate labels (case-insensitive)
    duplicates = conn.execute("""
        SELECT LOWER(label) as low_label, COUNT(*) as cnt,
               GROUP_CONCAT(entity_id, '|||') as ids,
               GROUP_CONCAT(entity_type, '|||') as types
        FROM kos_entities
        GROUP BY LOWER(label)
        HAVING cnt > 1
    """).fetchall()

    merged = 0
    for dup in duplicates:
        ids = dup["ids"].split("|||")
        types = dup["types"].split("|||")
        # Keep the first entity, merge others into it
        canonical_id = ids[0]
        for other_id in ids[1:]:
            # Update all relations pointing to other_id to point to canonical_id
            conn.execute("UPDATE OR IGNORE kos_relations SET target_id=? WHERE target_id=?", (canonical_id, other_id))
            conn.execute("UPDATE OR IGNORE kos_relations SET source_id=? WHERE source_id=?", (canonical_id, other_id))
            # Update entity_docs
            conn.execute("UPDATE OR IGNORE kos_entity_docs SET entity_id=? WHERE entity_id=?", (canonical_id, other_id))
            # Delete the duplicate
            conn.execute("DELETE FROM kos_entities WHERE entity_id=?", (other_id,))
            merged += 1

    conn.commit()
    conn.close()

    return {
        "duplicate_groups": len(duplicates),
        "entities_merged": merged,
    }


def entity_timeline(entity_id: str) -> dict[str, Any]:
    """Get the timeline of an entity based on document creation dates.

    Args:
        entity_id: The entity ID.

    Returns:
        Dict with timeline data.
    """
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]

    entity = conn.execute("SELECT * FROM kos_entities WHERE entity_id=?", (entity_id,)).fetchone()
    if not entity:
        conn.close()
        return {"error": f"Entity not found: {entity_id}"}

    # Get document timeline
    timeline = conn.execute(
        """SELECT d.title, d.zone, d.canonical_path, d.created_at, d.updated_at, ed.relevance,
                  SUBSTR(d.body, 1, 200) as snippet
           FROM kos_entity_docs ed
           JOIN documents d ON ed.doc_id = d.doc_id
           WHERE ed.entity_id = ?
           ORDER BY d.created_at DESC""",
        (entity_id,),
    ).fetchall()

    conn.close()

    return {
        "entity_id": entity_id,
        "label": entity["label"],
        "entity_type": entity["entity_type"],
        "total_docs": len(timeline),
        "timeline": [
            {
                "title": t["title"],
                "zone": t["zone"],
                "canonical_path": t["canonical_path"],
                "created_at": t["created_at"],
                "updated_at": t["updated_at"],
                "relevance": t["relevance"],
                "snippet": t["snippet"],
            }
            for t in timeline
        ],
    }
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
                except Exception:  # noqa: BLE001
                    logger.error("Unexpected exception caught", exc_info=True)  # type: ignore[name-defined]
                    pass

    # 3. Optional local LLM semantic enrichment via omlx gateway (MBP coder model)
    llm_enriched = _enrich_with_local_llm(conn, now)
    if llm_enriched > 0:
        print(f"Successfully enriched {llm_enriched} entities using local omlx/coder model.")

    conn.commit()
    conn.close()
    return {"enriched": enriched + llm_enriched, "timestamp": now}


def _enrich_with_local_llm(conn: sqlite3.Connection, now: str) -> int:
    """利用本地 omlx 推理网关 (http://localhost:4000) 自动为缺失描述的实体进行源码及文档级语义丰富化"""
    import urllib.request
    import urllib.error

    # 1. 快速探测本地 omlx 网关是否在线
    gateway_url = "http://localhost:4000/v1/chat/completions"
    try:
        req = urllib.request.Request(
            "http://localhost:4000/v1/models", headers={"Authorization": "Bearer sk-omlx-admin"}, method="GET"
        )
        with urllib.request.urlopen(req, timeout=1.0) as response:
            if response.status != 200:
                return 0
    except Exception:
        # 网关不在线，直接静默退出
        return 0

    # 2. 查找所有描述缺失或仅有默认占位描述的实体
    query = """
        SELECT entity_id, entity_type, label, source_file, description 
        FROM kos_entities 
        WHERE description IS NULL 
           OR description = '' 
           OR description LIKE 'Subproject in workspace%'
        LIMIT 5
    """
    targets = conn.execute(query).fetchall()
    if not targets:
        return 0

    enriched_count = 0
    for t in targets:
        eid = t["entity_id"]
        etype = t["entity_type"]
        label = t["label"]
        src_file = t["source_file"]

        context = ""
        if src_file and Path(src_file).is_file():
            try:
                with open(src_file, "r", encoding="utf-8") as f:
                    context = f.read(3000)
            except Exception:
                pass

        prompt = f"请为实体 '{label}' (类型: {etype}) 生成一段 100 字以内的专业语义摘要。\n"
        if context:
            prompt += f"以下是该实体的物理源码或配置片段，请基于它进行总结，不要有虚构内容：\n\n```\n{context}\n```\n"
        else:
            prompt += "请直接给出该实体在软件工程或治理规范中的常规定义与定位。"

        payload = {
            "model": "coder",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个严谨的产品架构师，请用中文简明扼要地总结，直接输出结果，不要有前言和废话。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 150,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            post_req = urllib.request.Request(
                gateway_url,
                data=data,
                headers={"Content-Type": "application/json", "Authorization": "Bearer sk-omlx-admin"},
                method="POST",
            )
            with urllib.request.urlopen(post_req, timeout=12.0) as res:
                res_data = json.loads(res.read().decode("utf-8"))
                choices = res_data.get("choices", [])
                if choices:
                    summary = choices[0].get("message", {}).get("content", "").strip()
                    if summary:
                        conn.execute(
                            "UPDATE kos_entities SET description=?, updated_at=? WHERE entity_id=?", (summary, now, eid)
                        )
                        enriched_count += 1
        except Exception as ex:
            print(f"  ⚠️  Local LLM enrichment failed for {eid}: {ex}", file=sys.stderr)

    return enriched_count


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
