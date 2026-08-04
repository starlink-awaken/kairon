"""Neo4j production writer for Memory OS temporal facts (Phase 6).

Enabled when NEO4J_URI is set (and optionally NEO4J_USER / NEO4J_PASSWORD).
Uses official neo4j driver when installed; otherwise reports unavailable.
Injectable driver factory for unit tests (no live Neo4j required).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable


def neo4j_configured() -> bool:
    return bool((os.environ.get("NEO4J_URI") or "").strip())


@runtime_checkable
class Neo4jSessionLike(Protocol):
    def run(self, query: str, parameters: dict[str, Any] | None = None) -> Any: ...


@runtime_checkable
class Neo4jDriverLike(Protocol):
    def session(self) -> Any: ...

    def close(self) -> None: ...


DriverFactory = Callable[[], Neo4jDriverLike | None]


def default_driver_factory() -> Neo4jDriverLike | None:
    uri = (os.environ.get("NEO4J_URI") or "").strip()
    if not uri:
        return None
    try:
        from neo4j import GraphDatabase  # type: ignore[import-not-found]
    except Exception:
        return None
    user = os.environ.get("NEO4J_USER") or os.environ.get("NEO4J_USERNAME") or "neo4j"
    password = os.environ.get("NEO4J_PASSWORD") or ""
    auth = (user, password) if password else None
    try:
        if auth:
            return GraphDatabase.driver(uri, auth=auth)
        return GraphDatabase.driver(uri)
    except Exception:
        return None


UPSERT_CYPHER = """
MERGE (s:Entity {name: $subject})
MERGE (o:Entity {name: $object})
MERGE (s)-[r:FACT {id: $id, predicate: $predicate}]->(o)
SET r.valid_from = $valid_from,
    r.valid_to = $valid_to,
    r.ingested_at = $ingested_at,
    r.invalidated_at = $invalidated_at,
    r.principal_id = $principal_id,
    r.agent_profile = $agent_profile,
    r.scene_id = $scene_id,
    r.text = $text,
    r.content_hash = $content_hash
RETURN r.id AS id
"""

INVALIDATE_CYPHER = """
MATCH ()-[r:FACT {id: $id}]->()
SET r.invalidated_at = $invalidated_at,
    r.valid_to = coalesce(r.valid_to, $invalidated_at)
RETURN r.id AS id
"""


@dataclass
class Neo4jFactWriter:
    """Production write path for bi-temporal FACT relationships."""

    driver_factory: DriverFactory = field(default=default_driver_factory)
    _driver: Neo4jDriverLike | None = field(default=None, init=False, repr=False)

    def available(self) -> bool:
        if not neo4j_configured():
            return False
        try:
            d = self._get_driver()
            return d is not None
        except Exception:
            return False

    def _get_driver(self) -> Neo4jDriverLike | None:
        if self._driver is not None:
            return self._driver
        self._driver = self.driver_factory()
        return self._driver

    def upsert_fact(self, envelope: dict[str, Any]) -> dict[str, Any]:
        if not neo4j_configured():
            return {"ok": False, "skipped": True, "reason": "neo4j_uri_unset"}
        driver = self._get_driver()
        if driver is None:
            return {"ok": False, "skipped": True, "reason": "neo4j_driver_unavailable"}
        graph = envelope.get("graph") or {}
        temporal = envelope.get("temporal") or {}
        scope = envelope.get("scope") or {}
        params = {
            "id": envelope.get("id"),
            "subject": graph.get("subject") or envelope.get("subject") or "unknown",
            "predicate": graph.get("predicate") or envelope.get("predicate") or "relates",
            "object": graph.get("object") or envelope.get("object") or "",
            "valid_from": temporal.get("valid_from"),
            "valid_to": temporal.get("valid_to"),
            "ingested_at": temporal.get("ingested_at"),
            "invalidated_at": temporal.get("invalidated_at"),
            "principal_id": scope.get("principal_id"),
            "agent_profile": scope.get("agent_profile"),
            "scene_id": scope.get("scene_id"),
            "text": envelope.get("content") or "",
            "content_hash": (envelope.get("provenance") or {}).get("content_hash"),
        }
        try:
            with driver.session() as session:  # type: ignore[union-attr]
                result = session.run(UPSERT_CYPHER, params)
                # consume
                if hasattr(result, "single"):
                    result.single()
                elif hasattr(result, "data"):
                    result.data()
            return {"ok": True, "id": params["id"], "store": "neo4j", "uri": os.environ.get("NEO4J_URI")}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "store": "neo4j"}

    def invalidate(self, edge_id: str, invalidated_at: str) -> dict[str, Any]:
        if not neo4j_configured():
            return {"ok": False, "skipped": True}
        driver = self._get_driver()
        if driver is None:
            return {"ok": False, "skipped": True, "reason": "neo4j_driver_unavailable"}
        try:
            with driver.session() as session:  # type: ignore[union-attr]
                session.run(INVALIDATE_CYPHER, {"id": edge_id, "invalidated_at": invalidated_at})
            return {"ok": True, "id": edge_id, "store": "neo4j"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:  # noqa: BLE001
                pass
            self._driver = None


@dataclass
class FakeNeo4jDriver:
    """Test double recording Cypher calls."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def session(self) -> FakeNeo4jSession:
        return FakeNeo4jSession(self)

    def close(self) -> None:
        return None


@dataclass
class FakeNeo4jSession:
    driver: FakeNeo4jDriver

    def __enter__(self) -> FakeNeo4jSession:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> FakeNeo4jResult:
        self.driver.calls.append({"query": query, "parameters": dict(parameters or {})})
        return FakeNeo4jResult()


class FakeNeo4jResult:
    def single(self) -> dict[str, Any]:
        return {"id": "ok"}

    def data(self) -> list[dict[str, Any]]:
        return [{"id": "ok"}]
