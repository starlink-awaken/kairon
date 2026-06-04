"""Iris Sync Engine — bidirectional Obsidian ↔ WPS Note synchronization.

Phase C components:
  - IdMapping: Persistent obsidian_path ↔ wpsnote_id mapping
  - FormatConverter: Markdown ↔ XML format conversion
  - ChangeTracker: Detects what changed on each side
  - ConflictResolver: Handles conflicting edits
  - SyncEngine: Orchestrator that ties everything together
"""

from iris.sync.changes import Change, ChangeTracker, ChangeType  # type: ignore[import-not-found]
from iris.sync.conflict import Conflict, ConflictResolver  # type: ignore[import-not-found]
from iris.sync.engine import SyncEngine  # type: ignore[import-not-found]
from iris.sync.engine import SyncResult as EngineSyncResult
from iris.sync.format import FormatConverter  # type: ignore[import-not-found]
from iris.sync.id_map import IdMapping  # type: ignore[import-not-found]

__all__ = [
    "IdMapping",
    "FormatConverter",
    "ChangeTracker",
    "Change",
    "ChangeType",
    "Conflict",
    "ConflictResolver",
    "SyncEngine",
    "EngineSyncResult",
]
