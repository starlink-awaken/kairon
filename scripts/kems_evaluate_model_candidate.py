#!/usr/bin/env python3
"""Evaluate a redacted forecast candidate against a deterministic baseline."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "kems.model-acceptance.v1"
FORBIDDEN_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}


class ModelInputError(ValueError):
    """The candidate evaluation payload is not safe or complete."""


def _finite_number(value: object, field: str, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ModelInputError(f"case {index}: {field} must be a finite number")
    return float(value)


def _case(record: object, index: int) -> tuple[str, float, float, float]:
    if not isinstance(record, dict):
        raise ModelInputError(f"case {index}: record must be an object")
    if any(str(key).lower() in FORBIDDEN_KEYS for key in record):
        raise ModelInputError(f"case {index}: raw content fields are forbidden")
    case_id = record.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ModelInputError(f"case {index}: case_id is required")
    predictions = record.get("predictions")
    actual = record.get("actual")
    if not isinstance(predictions, list) or not predictions:
        raise ModelInputError(f"case {index}: predictions must be a non-empty list")
    if not isinstance(actual, list) or len(actual) != len(predictions):
        raise ModelInputError(f"case {index}: actual must match predictions")
    predicted_values = [_finite_number(value, "prediction", index) for value in predictions]
    actual_values = [_finite_number(value, "actual", index) for value in actual]
    baseline = _finite_number(record.get("baseline_value"), "baseline_value", index)
    model_mae = sum(abs(predicted - observed) for predicted, observed in zip(predicted_values, actual_values)) / len(
        actual_values
    )
    baseline_mae = sum(abs(baseline - observed) for observed in actual_values) / len(actual_values)
    return case_id.strip(), model_mae, baseline_mae, len(actual_values)


def evaluate_candidate(
    payload: object,
    *,
    candidate_model_id: str,
    baseline_model_id: str = "naive-last-v1",
    min_cases: int = 1,
    min_relative_improvement: float = 0.0,
) -> dict[str, Any]:
    if not candidate_model_id.strip() or not baseline_model_id.strip():
        raise ModelInputError("model ids are required")
    if min_cases <= 0 or not 0 <= min_relative_improvement < 1:
        raise ModelInputError("invalid admission thresholds")
    if not isinstance(payload, list) or not payload:
        raise ModelInputError("evaluation payload must be a non-empty list")
    cases = [_case(record, index) for index, record in enumerate(payload, start=1)]
    case_ids = [case[0] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ModelInputError("case_id values must be unique")
    model_total = sum(case[1] * case[3] for case in cases)
    baseline_total = sum(case[2] * case[3] for case in cases)
    observations = sum(case[3] for case in cases)
    model_mae = model_total / observations
    baseline_mae = baseline_total / observations
    relative_improvement = (baseline_mae - model_mae) / baseline_mae if baseline_mae else 0.0
    threshold = 1.0 - min_relative_improvement
    passes = len(cases) >= min_cases and model_mae <= baseline_mae * threshold
    return {
        "schema_version": SCHEMA,
        "candidate_model_id": candidate_model_id.strip(),
        "baseline_model_id": baseline_model_id.strip(),
        "case_count": len(cases),
        "observation_count": observations,
        "model_mae": model_mae,
        "baseline_mae": baseline_mae,
        "relative_improvement": relative_improvement,
        "min_cases": min_cases,
        "min_relative_improvement": min_relative_improvement,
        "case_ids": case_ids,
        "status": "shadow_pass" if passes else "needs_review",
        "promotion": "blocked_until_omo_approval",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="redacted forecast cases JSON")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-model-id", required=True)
    parser.add_argument("--baseline-model-id", default="naive-last-v1")
    parser.add_argument("--min-cases", type=int, default=1)
    parser.add_argument("--min-relative-improvement", type=float, default=0.0)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.expanduser().resolve().read_text(encoding="utf-8"))
        result = evaluate_candidate(
            payload,
            candidate_model_id=args.candidate_model_id,
            baseline_model_id=args.baseline_model_id,
            min_cases=args.min_cases,
            min_relative_improvement=args.min_relative_improvement,
        )
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ModelInputError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "succeeded", **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
