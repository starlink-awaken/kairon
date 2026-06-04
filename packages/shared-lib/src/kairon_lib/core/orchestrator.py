from __future__ import annotations

"""
D-Harvest orchestrator — coordinates the end-to-end harvest lifecycle.

Provides ``HarvestOrchestrator`` which manages checkpoint save/load/verify/clear
operations, bridging the source registry, content extractor, and quality gate.
"""

from typing import Any

from kairon_lib.extractors.base import StructuredKnowledge
from kairon_lib.extractors.html_extractor import HtmlContentExtractor
from kairon_lib.quality.gate import QualityGate
from kairon_lib.sources.registry import SourceRegistry


class Checkpoint:
    """A saved checkpoint for a harvest cycle."""

    def __init__(
        self,
        job_id: str,
        step: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.job_id = job_id
        self.step = step
        self.data = data or {}


class HarvestOrchestrator:
    """Coordinates the D-Harvest lifecycle.

    Parameters
    ----------
    source_registry:
        Registry of known data sources.
    content_extractor:
        Extractor that converts raw content into ``StructuredKnowledge`` items.
    quality_gate:
        Quality gate that validates extracted items.
    """

    def __init__(
        self,
        source_registry: SourceRegistry | None = None,
        content_extractor: HtmlContentExtractor | None = None,
        quality_gate: QualityGate | None = None,
    ) -> None:
        self._source_registry = source_registry or SourceRegistry()
        self._content_extractor = content_extractor or HtmlContentExtractor()
        self._quality_gate = quality_gate or QualityGate()
        self._checkpoints: dict[str, Checkpoint] = {}

    # ---- checkpoint API ---------------------------------------------------

    async def save_checkpoint(self, job_id: str, step: str, data: dict[str, Any]) -> bool:
        """Save a checkpoint for *job_id* at *step* with *data*."""
        self._checkpoints[job_id] = Checkpoint(job_id=job_id, step=step, data=data)
        return True

    async def verify_checkpoint(self, job_id: str) -> bool:
        """Verify that a checkpoint exists for *job_id*."""
        return job_id in self._checkpoints

    async def load_checkpoint(self, job_id: str) -> Checkpoint | None:
        """Load the checkpoint for *job_id*, or ``None``."""
        return self._checkpoints.get(job_id)

    async def clear_checkpoint(self, job_id: str) -> bool:
        """Remove the checkpoint for *job_id*."""
        if job_id in self._checkpoints:
            del self._checkpoints[job_id]
            return True
        return False

    # ---- harvest cycle ----------------------------------------------------

    async def harvest(self, source_id: str) -> list[StructuredKnowledge]:
        """Run a full harvest cycle for *source_id*.

        1. Resolve the source via the registry.
        2. Fetch raw content.
        3. Extract structured knowledge.
        4. Validate through the quality gate.
        """
        raw = await self._source_registry.resolve(source_id)
        extracted = await self._content_extractor.extract(raw)
        items = [extracted] if not isinstance(extracted, list) else extracted
        validated = await self._quality_gate.validate(items)
        return [item for item, result in zip(items, validated) if result.passed]
