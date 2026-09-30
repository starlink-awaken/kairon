"""Shim for the ledger verify command ``uv run python -m mos.test_unified_memory``.

The real tests moved to ``tests/test_unified_memory.py`` so the package test
loop (``pytest tests/``) collects them — they were previously unreachable in
``src/``. This module keeps the historical ``python -m mos.test_unified_memory``
entry working by loading that file and running its inline ``_run_module()``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _tests_file() -> Path:
    # src/mos/test_unified_memory.py → packages/mos/tests/test_unified_memory.py
    return Path(__file__).resolve().parents[2] / "tests" / "test_unified_memory.py"


def _run_module() -> int:
    path = _tests_file()
    if not path.is_file():
        print(f"unified-memory tests not found at {path}")
        return 1
    spec = importlib.util.spec_from_file_location("mos_unified_memory_tests", path)
    if spec is None or spec.loader is None:
        print(f"cannot load unified-memory tests from {path}")
        return 1
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runner = getattr(module, "_run_module", None)
    if runner is None:
        print(f"_run_module missing in {path}")
        return 1
    return int(runner())


if __name__ == "__main__":
    sys.exit(_run_module())
