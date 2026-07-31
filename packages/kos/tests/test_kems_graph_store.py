"""Tests for the versioned KEMS graph persistence contract."""

from kos.kems import DocumentVersion, EvidenceSpan, GraphEntity, GraphRelation, GraphStore


def seeded_store(tmp_path):
    store = GraphStore(tmp_path / "graph.sqlite")
    store.put_document_version(
        DocumentVersion("doc-1", "v1", "a" * 64, "official_work", "原始文本", run_id="run-1")
    )
    store.add_evidence(EvidenceSpan("ev-1", "doc-1", "v1", "line=1", "原始文本", "rules", 0.99, "run-1"))
    store.add_entity(GraphEntity("ent-1", "policy", "政策 A", "doc-1", "v1", "ev-1", 0.95, created_by_run="run-1"))
    store.add_entity(GraphEntity("ent-2", "organization", "单位 B", "doc-1", "v1", "ev-1", 0.91, created_by_run="run-1"))
    return store


def test_graph_store_preserves_provenance_and_is_idempotent(tmp_path):
    store = seeded_store(tmp_path)
    store.add_relation(GraphRelation("rel-1", "ent-1", "issued_by", "ent-2", "doc-1", "v1", ("ev-1",), 0.9))
    store.add_relation(GraphRelation("rel-1", "ent-1", "issued_by", "ent-2", "doc-1", "v1", ("ev-1",), 0.95))

    entity = store.get_entity("ent-1")
    assert entity is not None
    assert entity["source_version_id"] == "v1"
    assert store.list_evidence("doc-1", "v1")[0]["evidence_id"] == "ev-1"
    snapshot = store.export_snapshot()
    assert len(snapshot["entities"]) == 2
    assert len(snapshot["relations"]) == 1


def test_graph_store_rejects_orphaned_facts(tmp_path):
    store = GraphStore(tmp_path / "graph.sqlite")
    store.initialize()
    try:
        store.add_entity(GraphEntity("orphan", "policy", "无来源", "missing", "v1", "ev", 0.8))
    except Exception as exc:
        assert "FOREIGN KEY" in str(exc).upper()
    else:
        raise AssertionError("orphaned graph facts must be rejected")
