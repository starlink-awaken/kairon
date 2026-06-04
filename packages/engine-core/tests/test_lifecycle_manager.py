"""Baseline tests for lifecycle_manager module.

SwarmLifecycleManager has heavy dependencies on engine_core.organs.engine.lifecycle.*
and other submodules that may not exist. We verify:
  - The source file exists
  - Class and method signatures from source
  - Import when dependencies are met
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

LIFECYCLE_MANAGER_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "engine_core"
    / "lifecycle_manager.py"
)

SOURCE_TEXT = LIFECYCLE_MANAGER_PATH.read_text(encoding="utf-8")


def test_source_file_exists():
    assert LIFECYCLE_MANAGER_PATH.is_file()


class TestSwarmLifecycleManagerClassSignatures:
    """Verify SwarmLifecycleManager class and key methods exist in source."""

    def test_class_swarm_lifecycle_manager_exists(self):
        assert "class SwarmLifecycleManager(" in SOURCE_TEXT

    def test_iswarm_lifecycle_protocol_exists(self):
        assert "class ISwarmLifecycle(" in SOURCE_TEXT

    def test_hatch_method_exists(self):
        assert "def hatch(" in SOURCE_TEXT

    def test_reap_method_exists(self):
        assert "def reap(" in SOURCE_TEXT

    def test_spawn_method_exists(self):
        assert "def spawn(" in SOURCE_TEXT

    def test_list_active_method_exists(self):
        assert "def list_active(" in SOURCE_TEXT

    def test_initialize_method_exists(self):
        assert "def initialize(" in SOURCE_TEXT

    def test_shutdown_method_exists(self):
        assert "def shutdown(" in SOURCE_TEXT

    def test_update_state_method_exists(self):
        assert "def update_state(" in SOURCE_TEXT

    def test_reap_by_id_method_exists(self):
        assert "def reap_by_id(" in SOURCE_TEXT

    def test_ping_heartbeat_method_exists(self):
        assert "def ping_heartbeat(" in SOURCE_TEXT

    def test_get_stale_workers_method_exists(self):
        assert "def get_stale_workers(" in SOURCE_TEXT

    def test_init_cluster_method_exists(self):
        assert "def init_cluster(" in SOURCE_TEXT

    def test_discover_peers_method_exists(self):
        assert "def discover_peers(" in SOURCE_TEXT

    def test_sync_state_method_exists(self):
        assert "def sync_state(" in SOURCE_TEXT

    def test_get_cluster_status_method_exists(self):
        assert "def get_cluster_status(" in SOURCE_TEXT

    def test_list_active_threads_method_exists(self):
        assert "def list_active_threads(" in SOURCE_TEXT


class TestSwarmLifecycleManagerDataClasses:
    """Verify supporting data classes exist in source."""

    def test_task_result_class_exists(self):
        assert "class TaskResult:" in SOURCE_TEXT

    def test_worker_bundle_class_exists(self):
        assert "class WorkerBundle:" in SOURCE_TEXT

    def test_worker_handle_class_exists(self):
        assert "class WorkerHandle:" in SOURCE_TEXT

    def test_worker_state_enum_exists(self):
        assert "class WorkerState(" in SOURCE_TEXT

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
            "engine_core.lifecycle_manager", str(LIFECYCLE_MANAGER_PATH)
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
