"""Pipeline data models — status enums, result types, and state management.

Extracted from SharedBrain D_Logos. Zero coupling to any external system.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ============================================================
# Data type definitions
# ============================================================


class StepStatus(Enum):
    """Step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStatus(Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class StepResult:
    """Step execution result."""

    step_name: str
    status: StepStatus
    start_time: float
    end_time: float = 0.0
    duration: float = 0.0
    output: Any = None
    error: str | None = None
    items_processed: int = 0
    items_failed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "output": str(self.output) if self.output else None,
            "error": self.error,
            "items_processed": self.items_processed,
            "items_failed": self.items_failed,
        }


@dataclass
class ProgressInfo:
    """Progress information."""

    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    current: str = ""

    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "current": self.current,
            "percentage": self.percentage,
        }


@dataclass
class PipelineState:
    """Pipeline state (for checkpoint/resume support)."""

    pipeline_id: str
    status: PipelineStatus
    start_time: float
    end_time: float = 0.0
    steps: dict[str, StepResult] = field(default_factory=dict)
    progress: ProgressInfo = field(default_factory=ProgressInfo)
    checkpoint_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def save(self) -> None:
        """Save state to checkpoint file."""
        if self.checkpoint_path:
            data = {
                "pipeline_id": self.pipeline_id,
                "status": self.status.value,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "steps": {k: v.to_dict() for k, v in self.steps.items()},
                "progress": self.progress.to_dict(),
                "metadata": self.metadata,
            }
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self.checkpoint_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, checkpoint_path: Path) -> PipelineState:
        """Load state from checkpoint file."""
        data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        steps = {}
        for k, v in data.get("steps", {}).items():
            steps[k] = StepResult(
                step_name=v["step_name"],
                status=StepStatus(v["status"]),
                start_time=v["start_time"],
                end_time=v.get("end_time", 0),
                duration=v.get("duration", 0),
                error=v.get("error"),
                items_processed=v.get("items_processed", 0),
                items_failed=v.get("items_failed", 0),
            )
        progress = ProgressInfo(**data.get("progress", {}))
        return cls(
            pipeline_id=data["pipeline_id"],
            status=PipelineStatus(data["status"]),
            start_time=data["start_time"],
            end_time=data.get("end_time", 0),
            steps=steps,
            progress=progress,
            checkpoint_path=checkpoint_path,
            metadata=data.get("metadata", {}),
        )


@dataclass
class BatchItem:
    """Batch processing item."""

    id: str
    path: Path
    doc_path: Path | None = None
    code_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str | None = None
    status: StepStatus = StepStatus.PENDING

    @classmethod
    def from_paths(cls, paths: list[Path]) -> list[BatchItem]:
        """Create batch items from path list."""
        items = []
        for path in paths:
            item_id = str(uuid.uuid4())[:8]
            items.append(
                cls(
                    id=item_id,
                    path=path,
                )
            )
        return items


@dataclass
class BatchResult:
    """Batch processing result."""

    total: int
    completed: int
    failed: int
    skipped: int
    results: list[BatchItem]
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "duration": self.duration,
            "success_rate": (self.completed / self.total * 100) if self.total > 0 else 0,
        }
