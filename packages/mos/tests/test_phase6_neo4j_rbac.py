"""Phase 6: Neo4j production writer + policy-table RBAC."""

from __future__ import annotations

import pytest
from mos.neo4j_writer import FakeNeo4jDriver, Neo4jFactWriter, neo4j_configured
from mos.rbac import RbacDenied, check_action, load_policy, resolve_role
from mos.service import MemoryOS


def test_rbac_resolve_and_deny():
    pol = load_policy()
    assert resolve_role(agent_profile="external-readonly", policy=pol) == "readonly"
    assert check_action("recall", role="readonly", policy=pol, raise_on_deny=False) is True
    assert check_action("write", role="readonly", policy=pol, raise_on_deny=False) is False
    with pytest.raises(RbacDenied):
        check_action("write", role="guest", policy=pol)


def test_service_rbac_guest_cannot_write():
    mos = MemoryOS(enforce_rbac=True)
    with pytest.raises(RbacDenied):
        mos.write(
            {"type": "semantic", "content": "secret", "confidence": 0.9, "agent_profile": "external-readonly"},
            role="guest",
        )


def test_service_rbac_agent_can_write():
    mos = MemoryOS(enforce_rbac=True)
    r = mos.write({"type": "semantic", "content": "ok note", "confidence": 0.9})
    assert r.ok


def test_neo4j_writer_skips_without_uri(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    w = Neo4jFactWriter()
    assert neo4j_configured() is False
    out = w.upsert_fact({"id": "e1", "subject": "A", "predicate": "knows", "object": "B"})
    assert out.get("skipped") is True


def test_neo4j_writer_with_fake_driver(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    fake = FakeNeo4jDriver()
    w = Neo4jFactWriter(driver_factory=lambda: fake)
    assert w.available() is True
    out = w.upsert_fact(
        {
            "id": "fact_1",
            "content": "Alice works at X",
            "subject": "Alice",
            "predicate": "works_at",
            "object": "X",
            "scope": {"principal_id": "u1", "agent_profile": "claude"},
            "temporal": {"valid_from": "2026-01-01T00:00:00Z"},
            "graph": {"subject": "Alice", "predicate": "works_at", "object": "X"},
            "provenance": {"content_hash": "abc"},
        }
    )
    assert out["ok"] is True
    assert out["store"] == "neo4j"
    assert len(fake.calls) == 1
    assert "MERGE" in fake.calls[0]["query"]
    assert fake.calls[0]["parameters"]["subject"] == "Alice"

    inv = w.invalidate("fact_1", "2026-08-04T00:00:00Z")
    assert inv["ok"] is True
    assert len(fake.calls) == 2


def test_service_write_routes_to_neo4j(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("MOS_TEMPORAL", "1")
    fake = FakeNeo4jDriver()
    writer = Neo4jFactWriter(driver_factory=lambda: fake)
    mos = MemoryOS(neo4j=writer, enforce_rbac=True)
    r = mos.write(
        {
            "type": "semantic",
            "content": "Bob invested in FundY",
            "subject": "Bob",
            "predicate": "invested_in",
            "object": "FundY",
            "confidence": 0.95,
            "principal_id": "u1",
        }
    )
    assert r.ok
    assert r.neo4j is not None
    assert r.neo4j.get("ok") is True
    assert any("MERGE" in c["query"] for c in fake.calls)


def test_status_reports_neo4j_and_rbac(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    mos = MemoryOS(enforce_rbac=True)
    st = mos.status()
    assert st["version"] == "0.10.0"
    assert st["neo4j_configured"] is False
    assert st["rbac_enforced"] is True
    assert "graphiti" in st


class _RefusingDriver:
    """Lazy double: constructing it never connects, probing it refuses.

    Mirrors the real neo4j driver's laziness — `GraphDatabase.driver()` does
    no I/O, only `verify_connectivity()` actually dials bolt://…:7687.
    """

    def session(self):
        raise AssertionError("connectivity probe must not open a session")

    def close(self) -> None:
        return None

    def verify_connectivity(self):
        raise OSError("SocketException: Connection refused (localhost:7687)")


class _ReachableDriver:
    def session(self):
        raise AssertionError("connectivity probe must not open a session")

    def close(self) -> None:
        return None

    def verify_connectivity(self):
        return None


def test_available_false_when_connectivity_refused(monkeypatch):
    """Fake-ready regression: driver object exists but the server refuses."""
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    w = Neo4jFactWriter(driver_factory=lambda: _RefusingDriver())
    assert w.available() is False


def test_available_true_when_connectivity_ok(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    w = Neo4jFactWriter(driver_factory=lambda: _ReachableDriver())
    assert w.available() is True


def test_available_false_when_driver_missing(monkeypatch):
    """neo4j package absent / factory bails → None driver must read as unavailable."""
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    w = Neo4jFactWriter(driver_factory=lambda: None)
    assert w.available() is False


def test_available_false_without_uri(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    w = Neo4jFactWriter(driver_factory=lambda: _ReachableDriver())
    assert neo4j_configured() is False
    assert w.available() is False


def test_status_reports_neo4j_unavailable_when_connectivity_refused(monkeypatch):
    """bos://memory/mos/status must not claim neo4j_available for a refused server."""
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    writer = Neo4jFactWriter(driver_factory=lambda: _RefusingDriver())
    mos = MemoryOS(neo4j=writer, enforce_rbac=True)
    st = mos.status()
    assert st["neo4j_configured"] is True
    assert st["neo4j_available"] is False
    assert st["neo4j_recall"] is False
    assert st["adapters"]["neo4j"]["available"] is False
