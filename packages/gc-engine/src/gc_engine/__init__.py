"""GC Engine — garbage collection, memory excretion, distillation."""

from gc_engine.archiver import (
    ArchiveEntry,
    ArchiveManager,
    ArchivePolicy,
    StorageTier,
    TieredStorage,
)
from gc_engine.distillation import DistillationEngine
from gc_engine.excretion import MemoryExcretionPipeline
from gc_engine.gc_core import GCEngine, GCStats
from gc_engine.lifecycle import DecayConfig, LifecycleManager, LifecycleRecord
from gc_engine.retention import RetentionPolicy

__all__ = [
    "ArchiveEntry",
    "ArchiveManager",
    "ArchivePolicy",
    "DecayConfig",
    "DistillationEngine",
    "GCEngine",
    "GCStats",
    "LifecycleManager",
    "LifecycleRecord",
    "MemoryExcretionPipeline",
    "RetentionPolicy",
    "StorageTier",
    "TieredStorage",
]
