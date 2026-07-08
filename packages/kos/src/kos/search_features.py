"""KOS Search Features — suggestions, clustering, related searches.

Usage:
    from kos.search_features import SearchFeatures
    
    features = SearchFeatures()
    suggestions = features.suggest("数字化", limit=5)
    clusters = features.cluster(results)
    related = features.related("数字化平台", limit=5)
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path


class SearchFeatures:
    """Search enhancement features: suggestions, clustering, related searches."""
    
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = get_artifact_path("retrievalDatabase")
        self.db_path = str(db_path)
    
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn
    
    def suggest(self, prefix: str, limit: int = 8) -> dict[str, Any]:
        """Generate search suggestions based on indexed terms and entity labels.
        
        Args:
            prefix: User's partial input.
            limit: Maximum number of suggestions.
            
        Returns:
            Dict with 'suggestions' list.
        """
        if not prefix or len(prefix.strip()) < 1:
            return {"suggestions": [], "prefix": prefix}
        
        conn = self._connect()
        suggestions = []
        seen = set()
        
        # 1. Entity labels matching the prefix
        try:
            entity_rows = conn.execute(
                """SELECT label, entity_type FROM kos_entities 
                   WHERE label LIKE ? OR label LIKE ?
                   ORDER BY entity_type, label LIMIT ?""",
                (f"{prefix}%", f"% {prefix}%", limit)
            ).fetchall()
            for row in entity_rows:
                label = row["label"]
                if label.lower() not in seen:
                    suggestions.append({
                        "text": label,
                        "type": "entity",
                        "entity_type": row["entity_type"],
                    })
                    seen.add(label.lower())
        except sqlite3.OperationalError:
            pass
        
        # 2. Document titles matching the prefix
        try:
            title_rows = conn.execute(
                """SELECT DISTINCT title FROM documents 
                   WHERE title LIKE ? OR title LIKE ?
                   ORDER BY title LIMIT ?""",
                (f"{prefix}%", f"% {prefix}%", limit)
            ).fetchall()
            for row in title_rows:
                title = row["title"]
                if title.lower() not in seen:
                    suggestions.append({
                        "text": title,
                        "type": "title",
                    })
                    seen.add(title.lower())
        except sqlite3.OperationalError:
            pass
        
        # 3. Popular FTS terms matching prefix
        try:
            term_rows = conn.execute(
                """SELECT DISTINCT substr(canonical_path, 
                       instr(canonical_path, '/') + 1, 50) as term
                   FROM documents 
                   WHERE canonical_path LIKE ? AND title != ''
                   GROUP BY term ORDER BY COUNT(*) DESC LIMIT ?""",
                (f"%{prefix}%", limit)
            ).fetchall()
            for row in term_rows:
                term = row["term"]
                if term and term.lower() not in seen:
                    # Extract just the filename part
                    short = term.split("/")[-1] if "/" in term else term
                    if len(short) > 2:
                        suggestions.append({
                            "text": short,
                            "type": "path",
                        })
                        seen.add(short.lower())
        except sqlite3.OperationalError:
            pass
        
        conn.close()
        return {
            "prefix": prefix,
            "suggestions": suggestions[:limit],
            "count": len(suggestions[:limit]),
        }
    
    def cluster(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Cluster search results by entity co-occurrence.
        
        Args:
            results: List of search result dicts.
            
        Returns:
            Dict with 'clusters' list, each containing entity info and results.
        """
        if not results:
            return {"clusters": [], "ungrouped": []}
        
        conn = self._connect()
        
        # For each result, find linked entities
        doc_entities: dict[str, list[dict]] = {}
        all_entities: dict[str, dict] = {}
        
        for r in results:
            doc_id = r.get("doc_id", "")
            if not doc_id:
                continue
            try:
                entity_rows = conn.execute(
                    """SELECT e.entity_id, e.label, e.entity_type
                       FROM kos_entity_docs ed
                       JOIN kos_entities e ON ed.entity_id = e.entity_id
                       WHERE ed.doc_id = ?
                       ORDER BY ed.relevance DESC LIMIT 5""",
                    (doc_id,)
                ).fetchall()
                doc_entities[doc_id] = [
                    {"entity_id": row["entity_id"], "label": row["label"], "type": row["entity_type"]}
                    for row in entity_rows
                ]
                for row in entity_rows:
                    all_entities[row["entity_id"]] = {
                        "entity_id": row["entity_id"],
                        "label": row["label"],
                        "type": row["entity_type"],
                    }
            except sqlite3.OperationalError:
                doc_entities[doc_id] = []
        
        conn.close()
        
        # Group results by entity
        entity_results: dict[str, list[dict]] = {}
        ungrouped: list[dict] = []
        
        for r in results:
            doc_id = r.get("doc_id", "")
            entities = doc_entities.get(doc_id, [])
            if not entities:
                ungrouped.append(r)
                continue
            for entity in entities:
                eid = entity["entity_id"]
                if eid not in entity_results:
                    entity_results[eid] = []
                entity_results[eid].append(r)
        
        # Sort clusters by size
        sorted_clusters = sorted(
            entity_results.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )
        
        clusters = []
        for eid, cluster_results in sorted_clusters:
            if len(cluster_results) >= 2:  # Only cluster if 2+ results
                entity_info = all_entities.get(eid, {})
                clusters.append({
                    "entity": entity_info,
                    "results": cluster_results,
                    "count": len(cluster_results),
                })
        
        return {
            "clusters": clusters,
            "ungrouped": ungrouped,
            "total_clusters": len(clusters),
            "total_ungrouped": len(ungrouped),
        }
    
    def related(self, query: str, limit: int = 6) -> dict[str, Any]:
        """Generate related search queries based on entity co-occurrence.
        
        Args:
            query: The current search query.
            limit: Maximum number of related queries.
            
        Returns:
            Dict with 'related' list.
        """
        if not query or len(query.strip()) < 2:
            return {"related": [], "query": query}
        
        conn = self._connect()
        related: list[dict] = []
        
        # 1. Find entities that co-occur in docs matching the query
        try:
            co_entity_rows = conn.execute(
                """SELECT e2.label, e2.entity_type, COUNT(*) as co_count
                   FROM documents_fts f
                   JOIN kos_entity_docs ed1 ON f.doc_id = ed1.doc_id
                   JOIN kos_entity_docs ed2 ON f.doc_id = ed2.doc_id
                   JOIN kos_entities e2 ON ed2.entity_id = e2.entity_id
                   WHERE documents_fts MATCH ?
                     AND ed1.entity_id != ed2.entity_id
                   GROUP BY e2.entity_id
                   ORDER BY co_count DESC LIMIT ?""",
                (query, limit * 2)
            ).fetchall()
            for row in co_entity_rows:
                if row["label"].lower() != query.lower():
                    related.append({
                        "text": row["label"],
                        "type": "co-occurring entity",
                        "score": row["co_count"],
                    })
        except sqlite3.OperationalError:
            pass
        
        # 2. Find docs with similar titles and suggest their titles
        try:
            title_rows = conn.execute(
                """SELECT DISTINCT title FROM documents
                   WHERE title LIKE ? AND title != ''
                   ORDER BY updated_at DESC LIMIT ?""",
                (f"%{query[:3]}%", limit)
            ).fetchall()
            for row in title_rows:
                if row["title"].lower() != query.lower():
                    related.append({
                        "text": row["title"],
                        "type": "similar title",
                        "score": 1,
                    })
        except sqlite3.OperationalError:
            pass
        
        conn.close()
        
        # Deduplicate and limit
        seen = set()
        unique_related = []
        for r in related:
            if r["text"].lower() not in seen:
                unique_related.append(r)
                seen.add(r["text"].lower())
        
        return {
            "query": query,
            "related": unique_related[:limit],
            "count": len(unique_related[:limit]),
        }
    
    def history(self, action: str = "list", query: str | None = None) -> dict[str, Any]:
        """Manage search history.
        
        Args:
            action: 'list', 'add', 'clear', or 'popular'.
            query: Query to add (for 'add' action).
            
        Returns:
            Dict with history entries.
        """
        history_path = Path.home() / ".kos" / "search_history.json"
        
        if action == "add" and query:
            return self._add_to_history(history_path, query)
        elif action == "clear":
            return self._clear_history(history_path)
        elif action == "popular":
            return self._popular(history_path)
        else:
            return self._list_history(history_path)
    
    def _add_to_history(self, path: Path, query: str) -> dict[str, Any]:
        """Add a query to history."""
        history = self._load_history(path)
        from datetime import datetime
        entry = {"query": query, "timestamp": datetime.now().isoformat()}
        # Remove duplicate if exists
        history = [h for h in history if h["query"] != query]
        history.insert(0, entry)
        # Keep only last 100 entries
        history = history[:100]
        self._save_history(path, history)
        return {"action": "add", "query": query, "count": len(history)}
    
    def _clear_history(self, path: Path) -> dict[str, Any]:
        """Clear search history."""
        self._save_history(path, [])
        return {"action": "clear", "count": 0}
    
    def _list_history(self, path: Path) -> dict[str, Any]:
        """List search history."""
        history = self._load_history(path)
        return {"history": history[:20], "count": len(history)}
    
    def _popular(self, path: Path) -> dict[str, Any]:
        """Get popular queries."""
        history = self._load_history(path)
        from collections import Counter
        queries = [h["query"] for h in history]
        popular = Counter(queries).most_common(10)
        return {
            "popular": [{"query": q, "count": c} for q, c in popular],
            "count": len(popular),
        }
    
    def _load_history(self, path: Path) -> list[dict]:
        """Load history from file."""
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, IOError):
                return []
        return []
    
    def _save_history(self, path: Path, history: list[dict]) -> None:
        """Save history to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2))
