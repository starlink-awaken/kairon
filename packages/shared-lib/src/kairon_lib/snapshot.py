"""
Filesystem-based snapshot manager for workspace state capture and rollback.

Extracted from SharedBrain D_Harness organ (snapshot/snapshot_manager.py).
All SharedBrain organ dependencies removed; standalone.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


# =============================================================================
# Enums & dataclasses
# =============================================================================


class StorageBackend(Enum):
    FILE = "file"
    SQLITE = "sqlite"
    MEMORY = "memory"
    REFLINK = "reflink"
    HARDLINK = "hardlink"
    COPY = "copy"


@dataclass
class SnapshotInfo:
    """Metadata record for a single snapshot."""

    snapshot_id: str
    source_path: str
    snapshot_path: str
    created_at: float
    metadata: dict[str, Any] = field(default_factory=dict)
    backend: StorageBackend = StorageBackend.FILE

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "source_path": self.source_path,
            "snapshot_path": self.snapshot_path,
            "created_at": self.created_at,
            "backend": self.backend.value,
            "metadata": self.metadata,
        }


# =============================================================================
# SnapshotManager
# =============================================================================


class SnapshotManager:
    """Filesystem-based snapshot manager.

    Each snapshot is stored as a directory under ``<base_path>/<snapshot_id>/``
    containing:

    - A copy of the source directory tree (or a single file copy).
    - A ``_meta.json`` file with snapshot metadata.
    """

    _META_FILE = "_meta.json"

    def __init__(
        self,
        base_path: str,
        backend: StorageBackend | str | None = None,
        **_: Any,
    ) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        if isinstance(backend, str):
            try:
                self.backend = StorageBackend(backend.lower())
            except ValueError:
                self.backend = StorageBackend.COPY
        else:
            self.backend = backend or StorageBackend.COPY

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def create_snapshot(
        self,
        source_path: str | Path,
        metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> SnapshotInfo:
        """Copy *source_path* into a new snapshot directory and return its info."""
        snapshot_id = str(uuid.uuid4())
        snap_dir = self.base_path / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)

        src = Path(source_path)
        data_dir = snap_dir / "data"

        try:
            if src.is_dir():
                shutil.copytree(str(src), str(data_dir))
            elif src.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(data_dir / src.name))
            else:
                data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            _log.warning("Snapshot copy failed for %s: %s", source_path, exc)

        created_at = time.time()
        meta = {
            "snapshot_id": snapshot_id,
            "source_path": str(source_path),
            "snapshot_path": str(data_dir),
            "created_at": created_at,
            "metadata": metadata or {},
        }
        (snap_dir / self._META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")

        return SnapshotInfo(
            snapshot_id=snapshot_id,
            source_path=str(source_path),
            snapshot_path=str(data_dir),
            created_at=created_at,
            metadata=metadata or {},
            backend=self.backend,
        )

    def rollback(
        self,
        snapshot_id: str,
        target_path: str | None = None,
        force: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        """Restore files from a previously created snapshot."""
        snap_dir = self.base_path / snapshot_id
        if not snap_dir.exists():
            return {"success": False, "error": f"Snapshot {snapshot_id!r} not found"}

        meta = self._read_meta(snap_dir)
        restore_to = Path(target_path or meta.get("source_path", str(snap_dir / "restored")))
        data_dir = Path(meta.get("snapshot_path") or snap_dir / "data")

        try:
            if data_dir.is_dir():
                if restore_to.exists() and force:
                    if restore_to.is_dir():
                        shutil.rmtree(str(restore_to))
                    else:
                        restore_to.unlink()

                if not restore_to.exists():
                    shutil.copytree(str(data_dir), str(restore_to))
                else:
                    for item in data_dir.rglob("*"):
                        rel = item.relative_to(data_dir)
                        dst = restore_to / rel
                        if item.is_dir():
                            dst.mkdir(parents=True, exist_ok=True)
                        else:
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(str(item), str(dst))
        except OSError as exc:
            return {"success": False, "error": str(exc), "snapshot_id": snapshot_id}

        return {
            "success": True,
            "snapshot_id": snapshot_id,
            "restored_to": str(restore_to),
        }

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Remove a snapshot directory and its metadata."""
        snap_dir = self.base_path / snapshot_id
        if snap_dir.exists():
            shutil.rmtree(str(snap_dir))
            return True
        return False

    def list_snapshots(self) -> list[str]:
        """Return a list of all available snapshot IDs."""
        return [
            d.name
            for d in self.base_path.iterdir()
            if d.is_dir() and (d / self._META_FILE).exists()
        ]

    def close(self) -> None:
        """No-op close for interface compatibility."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_meta(self, snap_dir: Path) -> dict[str, Any]:
        """Read and parse the metadata file for a snapshot."""
        meta_file = snap_dir / self._META_FILE
        if not meta_file.exists():
            return {}
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return {}


# =============================================================================
# Legacy alias for organic compatibility
# =============================================================================

OptimizedSnapshotManager = SnapshotManager

__all__ = [
    "StorageBackend",
    "SnapshotInfo",
    "SnapshotManager",
    "OptimizedSnapshotManager",
]
