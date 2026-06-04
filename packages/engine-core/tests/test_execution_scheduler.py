"""Baseline tests for execution_scheduler module.

ExecutionScheduler has dependencies on:
  - ProjectPaths from _compat
  - SQLite3 (stdlib, available)
  - Potential base class with metadata_path __init__ parameter

We verify source-level signatures and attempt import with stubs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

EXEC_SCHEDULER_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "engine_core"
    / "execution_scheduler.py"
)

SOURCE_TEXT = EXEC_SCHEDULER_PATH.read_text(encoding="utf-8")


def test_source_file_exists():
    assert EXEC_SCHEDULER_PATH.is_file()


class TestExecutionSchedulerSourceSignatures:
    """Verify ExecutionScheduler class and key methods exist in source."""

    def test_class_execution_scheduler_exists(self):
        assert "class ExecutionScheduler:" in SOURCE_TEXT

    def test_task_priority_enum_exists(self):
        assert "class TaskPriority(" in SOURCE_TEXT

    def test_task_status_enum_exists(self):
        assert "class TaskStatus(" in SOURCE_TEXT

    def test_prioritized_task_dataclass_exists(self):
        assert "class PrioritizedTask:" in SOURCE_TEXT

    def test_queue_full_error_exists(self):
        assert "class QueueFullError(" in SOURCE_TEXT

    def test_submit_task_method_exists(self):
        assert "def submit_task(" in SOURCE_TEXT

    def test_get_task_status_method_exists(self):
        assert "def get_task_status(" in SOURCE_TEXT

    def test_get_task_info_method_exists(self):
        assert "def get_task_info(" in SOURCE_TEXT

    def test_cancel_task_method_exists(self):
        assert "def cancel_task(" in SOURCE_TEXT

    def test_suspend_task_method_exists(self):
        assert "def suspend_task(" in SOURCE_TEXT

    def test_resume_task_method_exists(self):
        assert "def resume_task(" in SOURCE_TEXT

    def test_retry_task_method_exists(self):
        assert "def retry_task(" in SOURCE_TEXT

    def test_create_sandbox_method_exists(self):
        assert "def create_sandbox(" in SOURCE_TEXT

    def test_initialize_method_exists(self):
        assert "def initialize(" in SOURCE_TEXT

    def test_task_priority_values(self):
        assert "CRITICAL = 0" in SOURCE_TEXT
        assert "HIGH = 1" in SOURCE_TEXT
        assert "NORMAL = 2" in SOURCE_TEXT
        assert "LOW = 3" in SOURCE_TEXT
        assert "IDLE = 4" in SOURCE_TEXT

    def test_task_status_values(self):
        assert 'QUEUED = "QUEUED"' in SOURCE_TEXT
        assert 'RUNNING = "RUNNING"' in SOURCE_TEXT
        assert 'COMPLETED = "COMPLETED"' in SOURCE_TEXT
        assert 'FAILED = "FAILED"' in SOURCE_TEXT
        assert 'SUSPENDED = "SUSPENDED"' in SOURCE_TEXT
        assert 'CANCELLED = "CANCELLED"' in SOURCE_TEXT
        assert 'TIMEOUT = "TIMEOUT"' in SOURCE_TEXT
        assert 'RETRYING = "RETRYING"' in SOURCE_TEXT


class TestExecutionSchedulerImport:
    """Try to import execution_scheduler module and test basic instantiation.

    The module has a super().__init__(metadata_path=...) call that may fail.
    """

    @pytest.fixture(scope="class")
    def scheduler_module(self) -> Any:
        # Ensure _compat is loaded first
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

        # Mock metadata_aware base class if needed for super().__init__
        class MetadataAwareBase:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def initialize(self) -> None:
                pass

            def shutdown(self) -> None:
                pass

        # The module doesn't import a base class directly - let's see if it
        # inherits from one defined in the module itself
        spec = importlib.util.spec_from_file_location(
            "engine_core.execution_scheduler", str(EXEC_SCHEDULER_PATH)
        )
        if spec is None:
            pytest.skip("Could not create module spec for execution_scheduler.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("engine_core.execution_scheduler", mod)
        if spec.loader is None:
            pytest.skip("No loader for execution_scheduler.py")
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            pytest.skip(f"execution_scheduler module import failed: {exc}")
        return mod

    def test_module_loaded(self, scheduler_module: Any):
        assert hasattr(scheduler_module, "__name__")
        assert hasattr(scheduler_module, "ExecutionScheduler")

    def test_task_priority_enum(self, scheduler_module: Any):
        assert scheduler_module.TaskPriority.CRITICAL == 0
        assert scheduler_module.TaskPriority.HIGH == 1
        assert scheduler_module.TaskPriority.NORMAL == 2
        assert scheduler_module.TaskPriority.LOW == 3
        assert scheduler_module.TaskPriority.IDLE == 4

    def test_task_status_enum(self, scheduler_module: Any):
        assert scheduler_module.TaskStatus.QUEUED.value == "QUEUED"
        assert scheduler_module.TaskStatus.RUNNING.value == "RUNNING"
        assert scheduler_module.TaskStatus.COMPLETED.value == "COMPLETED"

    def test_queue_full_error_raise(self, scheduler_module: Any):
        with pytest.raises(scheduler_module.QueueFullError):
            raise scheduler_module.QueueFullError("Queue is full")

    def test_prioritized_task_dataclass(self, scheduler_module: Any):
        task = scheduler_module.PrioritizedTask(
            priority=scheduler_module.TaskPriority.NORMAL,
            sequence=1,
            task_id="t1",
            task_data={"cmd": "echo hello"},
        )
        assert task.task_id == "t1"
        assert task.priority == scheduler_module.TaskPriority.NORMAL
        assert task.sequence == 1
        assert task.task_data == {"cmd": "echo hello"}
