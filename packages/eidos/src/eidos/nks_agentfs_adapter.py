from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: '[!!] AUTO_ADDED_METADATA'
Summary: 'Auto-generated metadata for agentfs_adapter.py'
Tags:
- auto-metadata
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Agentfs Adapter ≡ Agent
# 内涵 ≝ {Agentfs, Adapter}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, AgentfsAdapter)}
# 功能 ⊢ {Agentfs_Adapter, Init_Agentfs, Validate_Adapter}
# =============================================================================

from pathlib import Path

from eidos.nks_agent_file_system import (  # type: ignore[import-not-found]
    AgentFileSystem,
    FileNode,
    OperationLog,
    Snapshot,
)


class AgentFSAdapter:
    """
    Adapter wrapping AgentFileSystem for NKS pipeline integration.

    Provides a clean delegate facade over AgentFileSystem, handling
    initialization and exposing the full file-system API surface.
    """

    def __init__(
        self,
        root_dir: str | Path,
        db_path: str | Path | None = None,
    ) -> None:
        self._fs = AgentFileSystem(str(root_dir), str(db_path) if db_path else None)

    # --- File operations (delegate to AgentFileSystem) ---

    def write_file(
        self,
        path: str,
        content: bytes | str,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
        op_id: str | None = None,
    ) -> FileNode:
        return self._fs.write_file(path, content, content_type, metadata, op_id)

    def read_file(self, path: str) -> bytes:
        return self._fs.read_file(path)

    def delete_file(self, path: str, op_id: str | None = None) -> bool:
        return self._fs.delete_file(path, op_id)

    def get_file_node(self, path: str) -> FileNode | None:
        return self._fs.get_file_node(path)

    def list_files(self, directory: str = "") -> list[FileNode]:
        return self._fs.list_files(directory)

    # --- Snapshot / audit ---

    def create_snapshot(self, description: str = "", metadata: dict | None = None) -> Snapshot:
        return self._fs.create_snapshot(description, metadata)

    def get_snapshot(self, snapshot_id: str) -> Snapshot | None:
        return self._fs.get_snapshot(snapshot_id)

    def list_snapshots(self, limit: int = 100) -> list[Snapshot]:
        return self._fs.list_snapshots(limit)

    def get_operations_log(
        self,
        since: float | None = None,
        snapshot_id: str | None = None,
        limit: int = 1000,
    ) -> list[OperationLog]:
        return self._fs.get_operations_log(since, snapshot_id, limit)

    # --- Health ---

    def ping(self) -> bool:
        return self._fs.ping()
