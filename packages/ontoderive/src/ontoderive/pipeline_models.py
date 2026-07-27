"""Pipeline data models — re-exported for compatibility.

These are the canonical pipeline model classes (ProgressInfo, StepResult,
StepStatus, BatchItem, BatchResult) used by the ontoderive pipeline steps.
Originally sourced from engine/pipeline_models; restored here for
backward compatibility after the engine/ directory was removed in P30.

Used by:
  - pipeline_steps.base (PipelineStep class)
  - governance_steps (RootNamespaceStep, SectionIndexStep, AgentContextStep)
  - validation_steps (BatchValidateStep, EvolveStep, ValidateStep)
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class StepStatus(str, enum.Enum):
    """Status of a pipeline step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProgressInfo:
    """Progress information for a pipeline step."""
    step_name: str
    current: int = 0
    total: int = 0
    message: str = ""


@dataclass
class StepResult:
    """Result of a pipeline step execution."""
    step_name: str
    status: StepStatus = StepStatus.PENDING
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class BatchItem:
    """Item in a batch operation."""
    id: str
    data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""


@dataclass
class BatchResult:
    """Result of a batch operation."""
    items: list[BatchItem] = field(default_factory=list)
    succeeded: int = 0
    failed: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    total: int = 0
    completed: int = 0
    skipped: int = 0
    results: list[BatchItem] = field(default_factory=list)
    duration: float = 0.0


__all__ = [
    "BatchItem",
    "BatchResult",
    "ProgressInfo",
    "StepResult",
    "StepStatus",
]
