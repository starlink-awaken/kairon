"""Pipeline step base class — abstract base for all pipeline steps.

Re-exported from engine.pipeline_steps.base for src/ontoderive compatibility.
Contains an inline copy to avoid triggering engine package import chain side effects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class PipelineStep(ABC):
    """Pipeline step base class.

    Subclass and implement ``execute()`` to create a custom pipeline step.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._result: Any = None
        self._progress_callback: Callable | None = None

    @abstractmethod
    def execute(self, context: dict, progress: Any) -> Any:
        """Execute the step. Override in subclasses."""
        ...

    def set_progress_callback(self, callback: Callable) -> None:
        """Set progress callback for this step."""
        self._progress_callback = callback


__all__ = [
    "PipelineStep",
]
