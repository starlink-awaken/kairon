from __future__ import annotations

import pytest
from kos.kems import AdjudicationStore


def item(sample_id: str = "sample-1") -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "source_sha256": "a" * 64,
        "source_ref": "vault://redacted/sample-1",
        "scenario_id": "oa-notice",
        "split": "test",
        "annotation_status": "pending",
    }


def test_queue_is_idempotent_and_adjudication_is_auditable(tmp_path) -> None:
    store = AdjudicationStore(tmp_path / "adjudication.sqlite")

    assert store.ingest_queue([item()]) == 1
    assert store.ingest_queue([item()]) == 0
    assert store.list_items(status="pending")[0]["annotation_status"] == "pending"

    claimed = store.claim("sample-1", annotator="reviewer-1")
    assert claimed["annotation_status"] == "reviewed"
    assert store.claim("sample-1", annotator="reviewer-1")["annotator"] == "reviewer-1"
    with pytest.raises(ValueError, match="another annotator"):
        store.claim("sample-1", annotator="reviewer-2")
    result = store.adjudicate(
        "sample-1",
        labels={"category": "notice", "priority": "normal"},
        annotation_version="ann-1",
        annotator="reviewer-1",
    )

    assert result["annotation_status"] == "adjudicated"
    assert result["labels"] == {"category": "notice", "priority": "normal"}
    assert result["annotator"] == "reviewer-1"
    assert len(store.adjudicated_items()) == 1


def test_queue_rejects_raw_content_and_invalid_refs(tmp_path) -> None:
    store = AdjudicationStore(tmp_path / "adjudication.sqlite")

    with pytest.raises(ValueError, match="raw content"):
        store.ingest_queue([item() | {"text": "private"}])
    with pytest.raises(ValueError, match="vault://redacted"):
        store.ingest_queue([item() | {"source_ref": "file:///private/source"}])


def test_adjudication_rejects_raw_labels_and_unknown_samples(tmp_path) -> None:
    store = AdjudicationStore(tmp_path / "adjudication.sqlite")
    store.ingest_queue([item()])

    with pytest.raises(ValueError, match="raw content"):
        store.adjudicate("sample-1", labels={"text": "private"}, annotation_version="ann-1", annotator="r")
    with pytest.raises(KeyError):
        store.adjudicate("missing", labels={"category": "notice"}, annotation_version="ann-1", annotator="r")
