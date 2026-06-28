from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import threading
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from eidos.organs.storage_dal import SQLiteError, SQLiteRelationalProvider

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "WAL mode required for ACID compliance"
Summary: "Agent File System - Layer M: Memory Fabric with ACID transactions"
Tags:
- nks
- memory-fabric
- acsd
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Agent File System ≡ Agent
# 内涵 ≝ {Agent, File, System}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, AgentFileSystem)}
# 功能 ⊢ {Agent_File, File_System, System_Init}
# =============================================================================

_log = logging.getLogger(__name__)


@dataclass
class FileNode:
    """Represents a file in AgentFS."""

    path: str
    hash: str
    size: int
    created_at: float
    modified_at: float
    content_type: str
    metadata: dict = field(default_factory=dict)


@dataclass
class OperationLog:
    """Represents an ACID operation log entry."""

    op_id: str
    operation: str  # 'write', 'delete', 'create_dir', 'snapshot'
    path: str
    snapshot_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


@dataclass
class Snapshot:
    """Represents a system state snapshot."""

    snapshot_id: str
    timestamp: float
    description: str
    root_hash: str
    metadata: dict = field(default_factory=dict)


class AgentFileSystem:
    """
    Agent File System (AgentFS) - Layer M of NKS

    Provides unified file storage with ACID transaction support, operation logging,
    and snapshot management for the Neural Knowledge System.
    """

    def __init__(self, root_dir: str, db_path: str | None = None) -> None:
        """
        Initialize AgentFS.

        Args:
            root_dir: Root directory for file storage
            db_path: Path to SQLite database for metadata (default: <root_dir>/.agentfs.db)
        """

        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

        if db_path is None:
            db_path = str(self.root_dir / ".agentfs.db")

        self.db_path = Path(db_path)
        self._db = SQLiteRelationalProvider(str(self.db_path))
        self._db_lock = threading.RLock()
        self._db.execute("PRAGMA foreign_keys=ON")
        self._init_db()
        self._deduct_metabolic_tax(amount=5.0)

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount

    def _init_db(self) -> None:
        """Initialize database schema."""
        # Files table
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                hash TEXT NOT NULL,
                size INTEGER NOT NULL,
                created_at REAL NOT NULL,
                modified_at REAL NOT NULL,
                content_type TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
        """
        )

        # Operations log (for ACID)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS operations (
                op_id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                path TEXT NOT NULL,
                snapshot_id TEXT,
                timestamp REAL NOT NULL,
                metadata TEXT NOT NULL
            )
        """
        )

        # Snapshots table
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                description TEXT NOT NULL,
                root_hash TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
        """
        )

        # Indexes
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_operations_snapshot ON operations(snapshot_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_operations_timestamp ON operations(timestamp)")

    def _compute_hash(self, data: bytes) -> str:
        """Compute SHA256 hash of data."""
        return hashlib.sha256(data).hexdigest()

    def _fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        with self._db_lock:
            return cast("dict[Any, Any] | None", self._db.fetch_one(sql, params))

    def _fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._db_lock:
            return self._db.fetch_all(sql, params)

    @contextlib.contextmanager
    def _begin_transaction(self) -> Generator:
        """
        Begin an ACID transaction.

        DAL does not expose explicit transaction handles; a dedicated provider
        connection is used per transaction to avoid cross-thread reuse on the
        shared metadata handle.

        Yields:
            Database connection for use in transaction
        """
        tx_db = SQLiteRelationalProvider(str(self.db_path))
        tx_db.connect()
        conn = tx_db._conn
        if conn is None:
            raise RuntimeError(f"failed to open AgentFS transaction database: {self.db_path}")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception:  # noqa: BLE001
            conn.rollback()
            raise
        finally:
            tx_db.disconnect()

    def write_file(
        self,
        path: str,
        content: bytes | str,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
        op_id: str | None = None,
    ) -> FileNode:
        """
        Write a file with ACID transaction support.

        Args:
            path: File path (relative to root_dir)
            content: File content (bytes or string)
            content_type: MIME type of content
            metadata: Optional metadata dictionary
            op_id: Optional operation ID for logging

        Returns:
            FileNode representing the written file

        Raises:
            ValueError: If path is invalid
            SQLiteError: If database operation fails
        """
        if metadata is None:
            metadata = {}

        if isinstance(content, str):
            content = content.encode("utf-8")

        file_path = self.root_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_hash = self._compute_hash(content)
        now = time.time()

        # Check if file already exists for update detection
        existing = self.get_file_node(path)

        with self._begin_transaction() as conn:
            # Write physical file
            with open(file_path, "wb") as f:
                f.write(content)

            # Update database
            conn.execute(
                """
                INSERT OR REPLACE INTO files
                (path, hash, size, created_at, modified_at, content_type, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    path,
                    file_hash,
                    len(content),
                    existing.created_at if existing else now,
                    now,
                    content_type,
                    json.dumps(metadata),
                ),
            )

            # Log operation
            if op_id is None:
                op_id = hashlib.sha256(f"{path}:{now}".encode()).hexdigest()[:16]

            conn.execute(
                """
                INSERT INTO operations
                (op_id, operation, path, snapshot_id, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    op_id,
                    "write",
                    path,
                    None,
                    now,
                    json.dumps(
                        {
                            "old_hash": existing.hash if existing else None,
                            "new_hash": file_hash,
                            "size": len(content),
                        }
                    ),
                ),
            )

        node = FileNode(
            path=path,
            hash=file_hash,
            size=len(content),
            created_at=existing.created_at if existing else now,
            modified_at=now,
            content_type=content_type,
            metadata=metadata,
        )

        return node

    def read_file(self, path: str) -> bytes:
        """
        Read a file.

        Args:
            path: File path (relative to root_dir)

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        file_path = self.root_dir / path
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(file_path, "rb") as f:
            return f.read()

    def delete_file(self, path: str, op_id: str | None = None) -> bool:
        """
        Delete a file with ACID transaction support.

        Args:
            path: File path (relative to root_dir)
            op_id: Optional operation ID for logging

        Returns:
            True if file was deleted, False if it didn't exist

        Raises:
            SQLiteError: If database operation fails
        """
        node = self.get_file_node(path)
        if not node:
            return False

        file_path = self.root_dir / path
        now = time.time()

        with self._begin_transaction() as conn:
            # Delete physical file
            if file_path.exists():
                file_path.unlink()

            # Remove from database
            conn.execute("DELETE FROM files WHERE path = ?", (path,))

            # Log operation
            if op_id is None:
                op_id = hashlib.sha256(f"del:{path}:{now}".encode()).hexdigest()[:16]

            conn.execute(
                """
                INSERT INTO operations
                (op_id, operation, path, snapshot_id, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (op_id, "delete", path, None, now, json.dumps({"deleted_hash": node.hash})),
            )

        return True

    def get_file_node(self, path: str) -> FileNode | None:
        """
        Get file metadata without reading content.

        Args:
            path: File path (relative to root_dir)

        Returns:
            FileNode or None if file doesn't exist
        """
        row = self._fetch_one("SELECT * FROM files WHERE path = ?", (path,))

        if row:
            return FileNode(
                path=row["path"],
                hash=row["hash"],
                size=row["size"],
                created_at=row["created_at"],
                modified_at=row["modified_at"],
                content_type=row["content_type"],
                metadata=json.loads(row["metadata"]),
            )
        return None

    def list_files(self, directory: str = "") -> list[FileNode]:
        """
        List all files in a directory.

        Args:
            directory: Directory path (relative to root_dir)

        Returns:
            List of FileNodes
        """
        # Normalize directory path (remove trailing slash)
        if directory:
            directory = directory.rstrip("/")
            # For non-root directory: match directory/% but exclude directory%/%/%
            pattern = f"{directory}/%"
            exclude_pattern = f"{directory}%/%/%"
        else:
            # For root directory: match all but exclude subdirectories (paths with >= 2 /)
            pattern = "%"
            exclude_pattern = "%/%/%"

        rows = self._fetch_all(
            """
            SELECT * FROM files
            WHERE path LIKE ?
            AND path NOT LIKE ?
            ORDER BY path
        """,
            (pattern, exclude_pattern),
        )

        return [
            FileNode(
                path=row["path"],
                hash=row["hash"],
                size=row["size"],
                created_at=row["created_at"],
                modified_at=row["modified_at"],
                content_type=row["content_type"],
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]

    def create_snapshot(self, description: str = "", metadata: dict | None = None) -> Snapshot:
        """
        Create a system state snapshot.

        Args:
            description: Human-readable description
            metadata: Optional metadata

        Returns:
            Snapshot object
        """
        if metadata is None:
            metadata = {}

        snapshot_id = hashlib.sha256(f"{time.time()}:{description}".encode()).hexdigest()[:16]
        now = time.time()

        # Compute root hash from all files
        with self._begin_transaction() as conn:
            rows = conn.execute("SELECT path, hash FROM files ORDER BY path").fetchall()

            hash_input = "|".join(f"{r['path']}:{r['hash']}" for r in rows)
            root_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            # Create snapshot record
            conn.execute(
                """
                INSERT INTO snapshots
                (snapshot_id, timestamp, description, root_hash, metadata)
                VALUES (?, ?, ?, ?, ?)
            """,
                (snapshot_id, now, description, root_hash, json.dumps(metadata)),
            )

        return Snapshot(
            snapshot_id=snapshot_id,
            timestamp=now,
            description=description,
            root_hash=root_hash,
            metadata=metadata,
        )

    def get_snapshot(self, snapshot_id: str) -> Snapshot | None:
        """
        Get a snapshot by ID.

        Args:
            snapshot_id: Snapshot identifier

        Returns:
            Snapshot or None
        """
        row = self._fetch_one("SELECT * FROM snapshots WHERE snapshot_id = ?", (snapshot_id,))

        if row:
            return Snapshot(
                snapshot_id=row["snapshot_id"],
                timestamp=row["timestamp"],
                description=row["description"],
                root_hash=row["root_hash"],
                metadata=json.loads(row["metadata"]),
            )
        return None

    def list_snapshots(self, limit: int = 100) -> list[Snapshot]:
        """
        List all snapshots.

        Args:
            limit: Maximum number of snapshots to return

        Returns:
            List of Snapshots
        """
        rows = self._fetch_all(
            """
            SELECT * FROM snapshots
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        return [
            Snapshot(
                snapshot_id=row["snapshot_id"],
                timestamp=row["timestamp"],
                description=row["description"],
                root_hash=row["root_hash"],
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]

    def get_operations_log(
        self, since: float | None = None, snapshot_id: str | None = None, limit: int = 1000
    ) -> list[OperationLog]:
        """
        Get operations log for auditing.

        Args:
            since: Unix timestamp to filter from
            snapshot_id: Optional snapshot ID to filter
            limit: Maximum number of entries

        Returns:
            List of OperationLog entries
        """
        query = "SELECT * FROM operations WHERE 1=1"
        params: list = []

        if since:
            query += " AND timestamp >= ?"
            params.append(since)

        if snapshot_id:
            query += " AND snapshot_id = ?"
            params.append(snapshot_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._fetch_all(query, tuple(params))

        return [
            OperationLog(
                op_id=row["op_id"],
                operation=row["operation"],
                path=row["path"],
                snapshot_id=row["snapshot_id"],
                timestamp=row["timestamp"],
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]

    def ping(self) -> bool:
        """Health check for AgentFS."""
        try:
            self._fetch_one("SELECT 1")
            return True
        except (SQLiteError, OSError):
            return False
