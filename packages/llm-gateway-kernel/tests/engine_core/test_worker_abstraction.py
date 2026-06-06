"""Tests for engine_core.worker_abstraction.

Covers WorkerAbstract, WorkerCapability, WorkerMetrics, WorkerStatus, WorkerType stubs.
"""
import importlib.util
import sys
from pathlib import Path

_mod_path = (Path(__file__).resolve().parents[2] / "src" / "llm_gateway_kernel" / "engine_core" / "worker_abstraction.py")
_spec = importlib.util.spec_from_file_location("engine_core.worker_abstraction", str(_mod_path))
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("engine_core.worker_abstraction", _mod)
_spec.loader.exec_module(_mod)


class TestWorkerAbstract:
    """WorkerAbstract stub tests."""

    def test_can_instantiate(self):
        instance = _mod.WorkerAbstract()
        assert isinstance(instance, _mod.WorkerAbstract)

    def test_is_distinct_type(self):
        assert _mod.WorkerAbstract.__name__ == "WorkerAbstract"

    def test_module_identity(self):
        assert _mod.__name__ == "engine_core.worker_abstraction"


class TestWorkerCapability:
    """WorkerCapability stub tests."""

    def test_can_instantiate(self):
        instance = _mod.WorkerCapability()
        assert isinstance(instance, _mod.WorkerCapability)


class TestWorkerMetrics:
    """WorkerMetrics stub tests."""

    def test_can_instantiate(self):
        instance = _mod.WorkerMetrics()
        assert isinstance(instance, _mod.WorkerMetrics)


class TestWorkerStatus:
    """WorkerStatus stub tests."""

    def test_can_instantiate(self):
        instance = _mod.WorkerStatus()
        assert isinstance(instance, _mod.WorkerStatus)


class TestWorkerType:
    """WorkerType stub tests."""

    def test_can_instantiate(self):
        instance = _mod.WorkerType()
        assert isinstance(instance, _mod.WorkerType)
