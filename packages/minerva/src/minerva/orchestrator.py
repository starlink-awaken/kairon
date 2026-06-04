"""Stub module for HarvestOrchestrator - used for type hints only."""

from dataclasses import dataclass


@dataclass
class HarvestResult:
    """收割结果 (stub)"""

    success: bool = True
    items_count: int = 0
    error: str | None = None


class HarvestOrchestrator:
    """知识收割编排器 (stub)"""

    pass
