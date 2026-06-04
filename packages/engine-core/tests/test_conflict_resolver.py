"""Tests for engine_core.conflict_resolver.

Covers the DeterministicConflictResolver stub class.
"""
import importlib.util
import sys
from pathlib import Path

_mod_path = (Path(__file__).resolve().parent.parent / "src" / "engine_core" / "conflict_resolver.py")
_spec = importlib.util.spec_from_file_location("engine_core.conflict_resolver", str(_mod_path))
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("engine_core.conflict_resolver", _mod)
_spec.loader.exec_module(_mod)


class TestDeterministicConflictResolver:
    """DeterministicConflictResolver stub tests."""

    def test_can_instantiate(self):
        resolver = _mod.DeterministicConflictResolver()
        assert isinstance(resolver, _mod.DeterministicConflictResolver)

    def test_is_distinct_type(self):
        assert _mod.DeterministicConflictResolver.__name__ == "DeterministicConflictResolver"

    def test_module_identity(self):
        assert _mod.__name__ == "engine_core.conflict_resolver"
