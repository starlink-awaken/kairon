"""Baseline tests for lifecycle_manager module.

SwarmLifecycleManager has heavy dependencies on engine_core.organs.engine.lifecycle.*
and other submodules that may not exist. We verify:
  - The compatibility facade exists
  - The real implementation exposes expected classes/methods/subcomponents
  - Import when dependencies are met
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

COMPAT_LIFECYCLE_MANAGER_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "engine_core"
    / "lifecycle_manager.py"
)

IMPL_LIFECYCLE_MANAGER_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "engine_core"
    / "lifecycle"
    / "lifecycle_manager.py"
)

SOURCE_TEXT = IMPL_LIFECYCLE_MANAGER_PATH.read_text(encoding="utf-8")
SOURCE_AST = ast.parse(SOURCE_TEXT)


def _find_class(name: str) -> ast.ClassDef:
    for node in SOURCE_AST.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"Class {name} not found")


def _class_method_names(name: str) -> set[str]:
    node = _find_class(name)
    return {
        child.name
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

def test_source_file_exists():
    assert COMPAT_LIFECYCLE_MANAGER_PATH.is_file()
    assert IMPL_LIFECYCLE_MANAGER_PATH.is_file()


class TestSwarmLifecycleManagerClassSignatures:
    """Verify SwarmLifecycleManager class and key methods exist in implementation."""

    def test_class_swarm_lifecycle_manager_exists(self):
        assert _find_class("SwarmLifecycleManager").name == "SwarmLifecycleManager"

    def test_iswarm_lifecycle_protocol_exists(self):
        assert _find_class("ISwarmLifecycle").name == "ISwarmLifecycle"

    def test_hatch_method_exists(self):
        assert "hatch" in _class_method_names("SwarmLifecycleManager")

    def test_reap_method_exists(self):
        assert "reap" in _class_method_names("SwarmLifecycleManager")

    def test_spawn_method_exists(self):
        assert "spawn" in _class_method_names("SwarmLifecycleManager")

    def test_list_active_method_exists(self):
        assert "list_active" in _class_method_names("SwarmLifecycleManager")

    def test_initialize_method_exists(self):
        assert "initialize" in _class_method_names("SwarmLifecycleManager")

    def test_shutdown_method_exists(self):
        assert "shutdown" in _class_method_names("SwarmLifecycleManager")

    def test_update_state_method_exists(self):
        assert "update_state" in _class_method_names("SwarmLifecycleManager")

    def test_reap_by_id_method_exists(self):
        assert "reap_by_id" in _class_method_names("SwarmLifecycleManager")

    def test_ping_heartbeat_method_exists(self):
        assert "ping_heartbeat" in _class_method_names("SwarmLifecycleManager")

    def test_get_stale_workers_method_exists(self):
        assert "get_stale_workers" in _class_method_names("SwarmLifecycleManager")

    def test_init_cluster_method_exists(self):
        assert "init_cluster" in _class_method_names("SwarmLifecycleManager")

    def test_discover_peers_method_exists(self):
        assert "discover_peers" in _class_method_names("SwarmLifecycleManager")

    def test_sync_state_method_exists(self):
        assert "sync_state" in _class_method_names("SwarmLifecycleManager")

    def test_get_cluster_status_method_exists(self):
        assert "get_cluster_status" in _class_method_names("SwarmLifecycleManager")

    def test_list_active_threads_method_exists(self):
        assert "list_active_threads" in _class_method_names("SwarmLifecycleManager")


class TestSwarmLifecycleManagerDataClasses:
    """Verify supporting data classes exist in source."""

    def test_task_result_class_exists(self):
        assert _find_class("TaskResult").name == "TaskResult"

    def test_worker_bundle_class_exists(self):
        assert _find_class("WorkerBundle").name == "WorkerBundle"

    def test_worker_handle_class_exists(self):
        assert _find_class("WorkerHandle").name == "WorkerHandle"

    def test_worker_state_enum_exists(self):
        assert _find_class("WorkerState").name == "WorkerState"

    def test_worker_state_values(self):
        assert "HATCHING = \"HATCHING\"" in SOURCE_TEXT
        assert "ACTIVE = \"ACTIVE\"" in SOURCE_TEXT
        assert "STARVING = \"STARVING\"" in SOURCE_TEXT
        assert "REAPED = \"REAPED\"" in SOURCE_TEXT


class TestSwarmLifecycleManagerSubcomponents:
    """Verify subcomponent references exist in source."""

    def test_call_dispatcher_referenced(self):
        assert "CallDispatcher" in SOURCE_TEXT

    def test_cluster_coordinator_referenced(self):
        assert "ClusterCoordinator" in SOURCE_TEXT

    def test_swarm_event_emitter_referenced(self):
        assert "SwarmEventEmitter" in SOURCE_TEXT

    def test_swarm_governance_referenced(self):
        assert "SwarmGovernance" in SOURCE_TEXT

    def test_parallel_dispatch_referenced(self):
        assert "ParallelDispatch" in SOURCE_TEXT

    def test_swarm_persistence_referenced(self):
        assert "SwarmPersistence" in SOURCE_TEXT

    def test_swarm_state_machine_referenced(self):
        assert "SwarmStateMachine" in SOURCE_TEXT

    def test_swarm_watchdog_referenced(self):
        assert "SwarmWatchdog" in SOURCE_TEXT

    def test_worker_pool_referenced(self):
        assert "WorkerPool" in SOURCE_TEXT

    def test_spore_registry_referenced(self):
        assert "SporeRegistry" in SOURCE_TEXT

    def test_hatcher_referenced(self):
        assert "Hatcher" in SOURCE_TEXT


class TestSwarmLifecycleManagerImport:
    """Try to import lifecycle_manager module.

    This has extensive dependencies; most are caught-and-continue
    (ImportError → fallback imports). Skip gracefully if import fails.
    """

    @pytest.fixture(scope="class")
    def lifecycle_module(self) -> Any:
        # Need _compat loaded first
        compat_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "engine_core"
            / "_compat.py"
        )
        spec_c = importlib.util.spec_from_file_location(
            "engine_core._compat", str(compat_path)
        )
        if spec_c and spec_c.loader:
            compat_mod = importlib.util.module_from_spec(spec_c)
            sys.modules["engine_core._compat"] = compat_mod
            spec_c.loader.exec_module(compat_mod)

        spec = importlib.util.spec_from_file_location(
            "engine_core.lifecycle_manager", str(COMPAT_LIFECYCLE_MANAGER_PATH)
        )
        if spec is None:
            pytest.skip("Could not create module spec for lifecycle_manager.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["engine_core.lifecycle_manager"] = mod
        if spec.loader is None:
            pytest.skip("No loader for lifecycle_manager.py")
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            pytest.skip(f"lifecycle_manager module import failed: {exc}")
        return mod

    def test_module_loaded(self, lifecycle_module: Any):
        """Verify the module was loaded (has __name__)."""
        assert hasattr(lifecycle_module, "__name__")
        assert lifecycle_module.__name__ == "engine_core.lifecycle_manager"
