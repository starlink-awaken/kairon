"""Tests for engine_core.bidder.

Covers the TaskBidder stub class.
"""
import importlib.util
import sys
from pathlib import Path

# Load bidder.py directly, bypassing broken __init__.py import chain
_mod_path = (Path(__file__).resolve().parents[2] / "src" / "llm_gateway_kernel" / "engine_core" / "bidder.py")
_spec = importlib.util.spec_from_file_location("engine_core.bidder", str(_mod_path))
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("engine_core.bidder", _mod)
_spec.loader.exec_module(_mod)


class TestTaskBidder:
    """TaskBidder stub tests."""

    def test_can_instantiate(self):
        bidder = _mod.TaskBidder()
        assert isinstance(bidder, _mod.TaskBidder)

    def test_is_distinct_type(self):
        assert _mod.TaskBidder.__name__ == "TaskBidder"

    def test_module_identity(self):
        assert _mod.__name__ == "engine_core.bidder"
