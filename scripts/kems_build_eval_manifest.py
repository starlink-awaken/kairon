#!/usr/bin/env python3
"""Build a redaction-verified KEMS evaluation manifest from adjudicated JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from kos.kems import EvaluationManifest, EvaluationSample

_FORBIDDEN = {"body", "content", "ocr_text", "raw_text", "text"}


def _sample(row: dict[str, Any], line: int) -> EvaluationSample:
    forbidden = sorted(_FORBIDDEN.intersection(row))
    if forbidden:
        raise ValueError(f"line {line}: raw content fields are forbidden: {', '.join(forbidden)}")
    if row.get("annotation_status") != "adjudicated":
        raise ValueError(f"line {line}: annotation_status must be adjudicated")
    source_ref = str(row.get("source_ref", ""))
    if not source_ref.startswith("vault://redacted/"):
        raise ValueError(f"line {line}: source_ref must use vault://redacted/")
    return EvaluationSample(
        sample_id=str(row.get("sample_id", "")),
        source_sha256=str(row.get("source_sha256", "")),
        source_ref=source_ref,
        scenario_id=str(row.get("scenario_id", "")),
        split=str(row.get("split", "test")),
        annotation_status="adjudicated",
        labels=row.get("labels", {}),
        annotation_version=str(row.get("annotation_version", "")),
    )


def build_manifest(input_path: Path, *, dataset_id: str, dataset_version: str) -> EvaluationManifest:
    samples: list[EvaluationSample] = []
    for line, raw in enumerate(input_path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError(f"line {line}: each JSONL row must be an object")
        samples.append(_sample(row, line))
    return EvaluationManifest(
        schema_version="kems.evaluation-manifest.v1",
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        redaction_status="verified",
        samples=tuple(samples),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="adjudicated redacted JSONL")
    parser.add_argument("--output", type=Path, required=True, help="manifest JSON output")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--dataset-version", required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.input, dataset_id=args.dataset_id, dataset_version=args.dataset_version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(manifest.to_json() + "\n", encoding="utf-8")
    print(json.dumps({"dataset_id": args.dataset_id, "dataset_version": args.dataset_version, "samples": len(manifest.samples), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
