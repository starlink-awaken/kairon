import json

import pytest

from scripts.kems_build_eval_manifest import build_manifest


def row(**overrides):
    value = {
        "sample_id": "sample-1",
        "source_sha256": "a" * 64,
        "source_ref": "vault://redacted/sample-1",
        "scenario_id": "oa-notice",
        "split": "test",
        "annotation_status": "adjudicated",
        "labels": {"title": "通知"},
        "annotation_version": "ann-1",
    }
    value.update(overrides)
    return value


def test_build_manifest_accepts_only_adjudicated_redacted_rows(tmp_path):
    source = tmp_path / "annotations.jsonl"
    source.write_text(json.dumps(row(), ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = build_manifest(source, dataset_id="kems-real", dataset_version="2026-07-31")
    assert manifest.to_dict()["samples"][0]["annotation_status"] == "adjudicated"


@pytest.mark.parametrize("overrides, message", [
    ({"annotation_status": "reviewed"}, "adjudicated"),
    ({"source_ref": "file:///private.pdf"}, "vault://redacted"),
    ({"text": "private body"}, "raw content"),
])
def test_build_manifest_rejects_unsafe_rows(tmp_path, overrides, message):
    source = tmp_path / "annotations.jsonl"
    source.write_text(json.dumps(row(**overrides)) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        build_manifest(source, dataset_id="kems-real", dataset_version="2026-07-31")
