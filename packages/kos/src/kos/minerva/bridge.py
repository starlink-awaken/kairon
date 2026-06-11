#!/usr/bin/env python3
# ruff: noqa
"""
KOS-Minerva Bridge — bidirectional knowledge synchronization.

Capabilities:
  1. kos-minerva search "query" --level L2 → delegate to Minerva deep research
  2. kos-minerva ingest → auto-index Minerva reports into KOS
  3. kos-minerva sync  → bidirectional entity sync (KOS ontology ↔ Minerva Neo4j)
  4. kos-minerva status → check Minerva health

Usage:
    kos-minerva search "MoE architecture" --level L2
    kos-minerva ingest
    kos-minerva status
    kos-minerva report → generate a KOS-Minerva cross-domain activity report
"""

import json
import os
import sqlite3
import subprocess as sp
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
from kos.config import get_vault_ops_dir  # type: ignore[unused-ignore, import-not-found]

VAULT_OPS_DIR = get_vault_ops_dir()
# Unified Minerva adapter (version-aware discovery)
from kos.adapters import MinervaAdapter, NullMinerva  # type: ignore[import-not-found]
from kos.config import get_artifact_path, get_workspace_manifest
from typing import Any

_MINERVA = None  # lazy singleton


def _get_minerva() -> MinervaAdapter:
    """Lazy singleton: discover Minerva once per process."""
    global _MINERVA
    if _MINERVA is None:
        _MINERVA = MinervaAdapter.discover() or NullMinerva
    return _MINERVA  # type: ignore[return-value]


MINERVA_HOME = Path(os.environ.get("MINERVA_HOME", Path.home() / "Workspace" / "minerva"))
MINERVA_REPORTS = Path.home() / "knowledge" / "reports"
KOS_MINERVA_BRIDGE = Path.home() / ".kos" / "minerva_bridge.json"


def _minerva_mcp_check() -> dict:  # type: ignore[type-arg]
    """Check Minerva health via adapter."""
    adapter = _get_minerva()
    h = adapter.health()
    if h["available"]:
        return {"minerva_installed": True, "version": h.get("version"), "path": h.get("path")}
    return {"minerva_installed": False}


def cmd_search(query: str, level: str = "L2", max_cost: float = 1.0) -> dict:  # type: ignore[type-arg]
    """Execute a deep research query via Minerva.

    Falls back to KOS local search if Minerva is unavailable.
    """
    adapter = _get_minerva()
    if not adapter.health()["available"]:
        print("⚠️  Minerva not available — falling back to local KOS search", file=sys.stderr)
        r = sp.run(
            [sys.executable, str(SCRIPT_DIR / "kos-cli.py"), "search", query, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            result = json.loads(r.stdout)
            result["_backend"] = "kos-local"
            return result  # type: ignore[Any, Any]
        return {"error": "Minerva unavailable and KOS fallback failed", "query": query}

    print(f"🔬 Minerva research: {query} (level={level})", file=sys.stderr)
    return adapter.research(query, level=level, max_cost=max_cost, timeout=600, cwd=str(MINERVA_HOME))


def cmd_ingest() -> dict:  # type: ignore[type-arg]
    """Ingest Minerva research reports into KOS index."""
    if not MINERVA_REPORTS.exists():
        return {"ingested": 0, "message": f"No reports directory: {MINERVA_REPORTS}"}

    reports = list(MINERVA_REPORTS.glob("*.md"))
    if not reports:
        return {"ingested": 0, "message": "No reports found"}

    # Use KOS ingest for each report
    ingested = []
    for r in sorted(reports, key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            # Use kos-ingest to add the report
            ingest_path = SCRIPT_DIR / "kos-ingest.py"
            r2 = sp.run([sys.executable, str(ingest_path), str(r)], capture_output=True, text=True, timeout=30)
            ingested.append({"file": r.name, "success": r2.returncode == 0})
        except Exception as e:
            ingested.append({"file": r.name, "success": False, "error": str(e)})

    # After ingest, re-index minerva domain
    indexer_path = SCRIPT_DIR / "kos-indexer.py"
    r3 = sp.run(
        [sys.executable, str(indexer_path), "index", "--domain", "minerva", "--incremental"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    return {
        "ingested": len(ingested),
        "files": ingested,
        "indexed": r3.returncode == 0,
        "timestamp": datetime.now().isoformat()[:19],
    }


def cmd_status() -> dict:  # type: ignore[type-arg]
    """Check the status of the KOS-Minerva bridge."""
    manifest = get_workspace_manifest()
    minerva_zone = manifest.get("zones", {}).get("minerva", {})
    minerva_domain = manifest.get("domains", {}).get("minerva", {})

    # Check KOS index for minerva documents
    index_status: dict[str, Any] = {"documents": 0}
    try:
        db_path = get_artifact_path("retrievalDatabase")
        if db_path.exists():  # type: ignore[attr-defined]
            conn = sqlite3.connect(str(db_path))
            count = conn.execute("SELECT COUNT(*) FROM documents WHERE zone='minerva'").fetchone()[0]
            docs = conn.execute(
                "SELECT title, kind, updated_at FROM documents WHERE zone='minerva' ORDER BY updated_at DESC LIMIT 5"
            ).fetchall()
            index_status = {"documents": count, "recent": [dict(d) for d in docs]}
            conn.close()
    except Exception as e:
        index_status = {"error": str(e)}

    return {
        "minerva_zone": minerva_zone.get("label", "not configured"),
        "minerva_domain": minerva_domain.get("description", "not configured"),
        "minerva_health": _minerva_mcp_check(),
        "kos_index": index_status,
        "bridge_version": "1.0",
        "manifest_version": manifest.get("version", "unknown"),
    }


def cmd_report() -> dict:  # type: ignore[type-arg]
    """Generate a cross-domain activity report covering KOS + Minerva."""
    manifest = get_workspace_manifest()
    now = datetime.now().isoformat()[:19]

    # KOS domain stats
    try:
        db_path = get_artifact_path("retrievalDatabase")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        zones = conn.execute("SELECT zone, COUNT(*) as cnt FROM documents GROUP BY zone ORDER BY cnt DESC").fetchall()
        minerva_count = conn.execute("SELECT COUNT(*) FROM documents WHERE zone='minerva'").fetchone()[0]
        recent = conn.execute(
            "SELECT title, zone, updated_at FROM documents ORDER BY updated_at DESC LIMIT 10"
        ).fetchall()
        conn.close()
    except Exception:
        zones = []
        minerva_count = 0
        recent = []

    return {
        "timestamp": now,
        "domains": len(manifest.get("domains", {})),
        "zones": {z["zone"]: z["cnt"] for z in zones},
        "minerva_docs": minerva_count,
        "recent_activity": [dict(r) for r in recent],
        "minerva_reports_available": len(list(MINERVA_REPORTS.glob("*.md"))) if MINERVA_REPORTS.exists() else 0,
    }


def main():  # type: ignore[unknown]
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    rest = sys.argv[2:] if len(sys.argv) > 2 else []

    if cmd == "search":
        query = rest[0] if rest else ""
        level = "L2"
        for i, a in enumerate(rest):
            if a == "--level" and i + 1 < len(rest):
                level = rest[i + 1]
        result = cmd_search(query, level)
    elif cmd == "ingest":
        result = cmd_ingest()
    elif cmd == "status":
        result = cmd_status()
    elif cmd == "report":
        result = cmd_report()
    else:
        result = {"error": f"Unknown command: {cmd}", "usage": "search|ingest|status|report"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
