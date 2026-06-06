"""Baseline tests for lifecycle_events module (SwarmEventEmitter).

SwarmEventEmitter is a standalone component with a soft dependency on
kairon_lib.events. All failures are silently swallowed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

LIFECYCLE_EVENTS_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "engine_core"
    / "lifecycle_events.py"
)

SOURCE_TEXT = LIFECYCLE_EVENTS_PATH.read_text(encoding="utf-8")


def test_source_file_exists():
    assert LIFECYCLE_EVENTS_PATH.is_file()


class TestSwarmEventEmitterSourceSignatures:
    """Verify SwarmEventEmitter and its methods exist in source."""

    def test_class_swarm_event_emitter_exists(self):
        assert "class SwarmEventEmitter:" in SOURCE_TEXT

    def test_emit_method_exists(self):
        assert "def emit(" in SOURCE_TEXT

    def test_source_name_constant_exists(self):
        assert 'SOURCE_NAME = "swarm_lifecycle_manager"' in SOURCE_TEXT


class TestSwarmEventEmitterImportAndInstantiate:
    """Try to import and instantiate SwarmEventEmitter.

    The soft dependency on kairon_lib.events is caught internally,
    so this should always work.
    """

    @pytest.fixture(scope="class")
    def emitter_module(self) -> Any:
        spec = importlib.util.spec_from_file_location(
            "engine_core.lifecycle_events", str(LIFECYCLE_EVENTS_PATH)
        )
        if spec is None:
            pytest.skip("Could not create module spec for lifecycle_events.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("engine_core.lifecycle_events", mod)
        if spec.loader is None:
            pytest.skip("No loader for lifecycle_events.py")
        spec.loader.exec_module(mod)
        return mod

    def test_can_instantiate(self, emitter_module: Any):
        emitter = emitter_module.SwarmEventEmitter()
        assert emitter is not None
        assert emitter.SOURCE_NAME == "swarm_lifecycle_manager"

    def test_emit_method_exists(self, emitter_module: Any):
        emitter = emitter_module.SwarmEventEmitter()
        assert hasattr(emitter, "emit")
        assert callable(emitter.emit)

    def test_emit_does_not_raise(self, emitter_module: Any):
        """emit() should never raise — errors are silently caught."""
        emitter = emitter_module.SwarmEventEmitter()
        # This should not raise even though kairon_lib is unavailable
        emitter.emit("test.event", {"key": "value"})

    def test_is_distinct_type(self, emitter_module: Any):
        emitter = emitter_module.SwarmEventEmitter()
        assert type(emitter).__name__ == "SwarmEventEmitter"

    def test_module_identity(self, emitter_module: Any):
        assert hasattr(emitter_module, "SwarmEventEmitter")
        assert hasattr(emitter_module, "__name__")
