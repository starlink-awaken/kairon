#!/usr/bin/env python3
"""Evaluate a redacted forecast candidate against a deterministic baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kos.kems.model_acceptance import ModelInputError, evaluate_candidate


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
