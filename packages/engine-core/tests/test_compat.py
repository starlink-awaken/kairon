"""Tests for engine_core._compat.

Covers compatibility stubs, error types, URI parsing, surface contracts,
and utility functions migrated from SharedBrain.
"""
import importlib.util
import sys
from pathlib import Path

# Load _compat.py directly, bypassing broken __init__.py import chain
_compat_path = (Path(__file__).resolve().parent.parent / "src" / "engine_core" / "_compat.py")
_spec = importlib.util.spec_from_file_location("engine_core._compat", str(_compat_path))
_compat = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("engine_core._compat", _compat)
_spec.loader.exec_module(_compat)


# ── Utility enums reused across test classes ──────────────────────────────────
