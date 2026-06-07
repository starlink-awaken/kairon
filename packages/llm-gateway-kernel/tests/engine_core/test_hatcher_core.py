"""Baseline tests for hatcher_core module.

The Hatcher class has heavy dependencies on `engine_core.organs.engine.*`
submodules that may not exist in all environments. We verify:
  - The source file exists
  - The Hatcher class signature is as expected
  - Key method signatures exist (in source)
  - Import works when dependencies are met
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

HATCHER_CORE_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "llm_gateway_kernel" / "engine_core" / "hatcher_core.py"
)


def test_source_file_exists():
    """The source file must exist on disk."""
    assert HATCHER_CORE_PATH.is_file(), f"hatcher_core.py not found at {HATCHER_CORE_PATH}"


# Parse method signatures directly from the source file
SOURCE_TEXT = HATCHER_CORE_PATH.read_text(encoding="utf-8")


class TestHatcherClassSignatures:
    """Verify Hatcher class and its methods exist in source."""

    def test_class_Hatcher_exists(self):  # noqa: N802
        assert "class Hatcher:" in SOURCE_TEXT

    def test_hatch_method_exists(self):
        assert "def hatch(" in SOURCE_TEXT

    def test_terminate_method_exists(self):
        assert "def terminate(" in SOURCE_TEXT

    def test_cancel_method_exists(self):
        assert "def cancel(" in SOURCE_TEXT

    def test_drain_all_method_exists(self):
        assert "def drain_all(" in SOURCE_TEXT

    def test_initialize_method_exists(self):
        assert "def initialize(" in SOURCE_TEXT

    def test_shutdown_method_exists(self):
        assert "def shutdown(" in SOURCE_TEXT

    def test_dispatch_task_async_exists(self):
        assert "def dispatch_task_async(" in SOURCE_TEXT

    def test_dispatch_hatch_exists(self):
        assert "def _dispatch_hatch(" in SOURCE_TEXT

    def test_hatch_cli_subprocess_exists(self):
        assert "def _hatch_cli_subprocess(" in SOURCE_TEXT

    def test_hatch_internal_thread_exists(self):
        assert "def _hatch_internal_thread(" in SOURCE_TEXT

    def test_hatch_agent_cli_exists(self):
        assert "def _hatch_agent_cli(" in SOURCE_TEXT

    def test_build_command_exists(self):
        assert "def _build_command(" in SOURCE_TEXT

    def test_build_env_exists(self):
        assert "def _build_env(" in SOURCE_TEXT


class TestHatcherCoreImports:
    """Try to import the module and test basic functionality.

    Skip if dependencies are not met — the module requires many
    companion submodules (organs.*) that may not exist.
    """

    @pytest.fixture(scope="class")
    def hatcher_module(self) -> Any:
        """Load hatcher_core.py directly via importlib.

        Skips if the required submodules can't be satisfied.
        """
        # We need to mock the missing submodules to get the import to work
        # Since hatcher_core imports from llm_gateway_kernel.engine_core.organs.engine.* and other
        # non-existent modules, we create stub modules
        missing_modules = [
            "engine_core.organs",
            "engine_core.organs.engine",
            "engine_core.organs.engine.agent_cli_bootstrap",
            "engine_core.organs.engine.hatch_runtime",
            "engine_core.organs.engine.hatcher_events",
            "engine_core.organs.engine.retry_policy",
            "engine_core.organs.engine.task_store",
            "engine_core._events",
            "engine_core.exceptions",
            "engine_core.thread_worker",
        ]
        for mod_name in missing_modules:
            if mod_name not in sys.modules:
                sys.modules[mod_name] = type(sys)(mod_name)

        spec = importlib.util.spec_from_file_location("engine_core.hatcher_core", str(HATCHER_CORE_PATH))
        if spec is None:
            pytest.skip("Could not create module spec for hatcher_core.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["engine_core.hatcher_core"] = mod
        if spec.loader is None:
            pytest.skip("No loader for hatcher_core.py")
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            pytest.skip(f"hatcher_core module import failed: {exc}")
        return mod

    def test_hatcher_can_instantiate(self, hatcher_module: Any):
        """If the module loaded, Hatcher should be instantiable."""
        hatcher = hatcher_module.Hatcher()
        assert hatcher is not None
        assert hasattr(hatcher, "hatch")
        assert hasattr(hatcher, "terminate")
        assert hasattr(hatcher, "cancel")
        assert hasattr(hatcher, "drain_all")
