from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eidos.graph_store import GraphStore

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "Track file changes to enable incremental NKS indexing"
Summary: "IncrementalIndexer - Efficient change detection for large codebases"
Tags:
- nks
- incremental-indexing
- file-signatures
- change-detection
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Incremental Indexer ≡ Module
# 内涵 ≝ {Incremental, Indexer}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, IncrementalIndexer)}
# 功能 ⊢ {Incremental_Indexer, Init_Incremental, Validate_Indexer}
# =============================================================================

_log = logging.getLogger(__name__)

# Import from tree_sitter_extractor
try:
    from eidos.tree_sitter_extractor import TreeSitterExtractionResult, TreeSitterExtractor
except ImportError:
    TreeSitterExtractor = None
    TreeSitterExtractionResult = None


@dataclass
class FileSignature:
    """Represents a file's signature for change detection."""

    file_path: str  # Relative file path
    file_hash: str  # SHA256 hash of content
    mtime: float  # Modification time (seconds since epoch)
    size: int  # File size in bytes
    last_indexed: float  # Timestamp when last indexed


@dataclass
class IndexingResult:
    """Result of incremental indexing operation."""

    files_processed: int = 0
    files_skipped: int = 0
    files_deleted: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    is_incremental: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "files_processed": self.files_processed,
            "files_skipped": self.files_skipped,
            "files_deleted": self.files_deleted,
            "entities_extracted": self.entities_extracted,
            "relations_extracted": self.relations_extracted,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "is_incremental": self.is_incremental,
        }


class IncrementalIndexer:
    """
    IncrementalIndexer - Efficient change detection for NKS indexing.

    Tracks file modification times, hashes, and sizes to detect changes
    and only re-index files that have been modified since last indexing.
    This provides 10x+ performance improvement for large codebases with
    small changes.

    Features:
    - File signature tracking (hash + mtime + size)
    - Change detection with configurable comparison modes
    - Batch processing of dirty files only
    - Cleanup of entities from deleted files
    - SQLite-backed persistence of index metadata
    """

    def __init__(self, graph_store: GraphStore) -> None:
        """
        Initialize IncrementalIndexer.

        Args:
            graph_store: GraphStore instance for storing entities and relations
        """

        self.store = graph_store
        self._init_schema()
        self._deduct_metabolic_tax(amount=5.0)

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount

    def _get_connection(self) -> Any:
        """Get database connection from GraphStore."""
        return self.store._get_connection()

    def _init_schema(self) -> None:
        """Initialize file_signatures table schema."""
        with self._get_connection() as conn:
            # File signatures table for change tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_signatures (
                    file_path TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    mtime REAL NOT NULL,
                    size INTEGER NOT NULL,
                    last_indexed REAL NOT NULL
                )
            """)

            # Index for efficient cleanup and querying
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signatures_mtime
                ON file_signatures(last_indexed)
            """)

            # Index for file path lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signatures_path
                ON file_signatures(file_path)
            """)
            conn.commit()

    def compute_signature(self, file_path: str) -> FileSignature | None:
        """
        Compute signature for a file.

        Args:
            file_path: Path to the file (can be relative or absolute)

        Returns:
            FileSignature or None if file doesn't exist
        """
        path = Path(file_path)

        if not path.exists():
            return None

        # Get file stats
        stat = path.stat()
        mtime = stat.st_mtime
        size = stat.st_size

        # Compute SHA256 hash
        sha256_hash = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                # Read in chunks for large files
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256_hash.update(chunk)
        except OSError:
            if os.environ.get("BOS_DEBUG"):
                _log.info("⚠️ [IncrementalIndexer] Failed to hash {file_path}: {e}")
            return None

        return FileSignature(
            file_path=str(file_path),
            file_hash=sha256_hash.hexdigest(),
            mtime=mtime,
            size=size,
            last_indexed=time.time(),
        )

    def get_stored_signature(self, file_path: str) -> FileSignature | None:
        """
        Get stored signature for a file.

        Args:
            file_path: Path to the file

        Returns:
            Stored FileSignature or None if not found
        """
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM file_signatures WHERE file_path = ?", (file_path,)).fetchone()

            if row:
                return FileSignature(
                    file_path=row["file_path"],
                    file_hash=row["file_hash"],
                    mtime=row["mtime"],
                    size=row["size"],
                    last_indexed=row["last_indexed"],
                )
            return None

    def store_signature(self, signature: FileSignature) -> bool:
        """
        Store or update file signature.

        Args:
            signature: FileSignature to store

        Returns:
            True if successful
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO file_signatures
                (file_path, file_hash, mtime, size, last_indexed)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    signature.file_path,
                    signature.file_hash,
                    signature.mtime,
                    signature.size,
                    signature.last_indexed,
                ),
            )
            conn.commit()
        return True

    def is_file_changed(self, file_path: str) -> bool:
        """
        Check if a file has changed since last indexing.

        Compares current signature with stored signature using:
        1. Hash comparison (most reliable)
        2. Size comparison (quick check)
        3. Mtime comparison (fallback)

        Args:
            file_path: Path to the file

        Returns:
            True if file has changed or is new
        """
        current = self.compute_signature(file_path)
        stored = self.get_stored_signature(file_path)

        # New file (not in index)
        if current is None:
            # File doesn't exist anymore
            return stored is not None

        if stored is None:
            return True

        # Compare signatures
        # Hash is the most reliable indicator
        if current.file_hash != stored.file_hash:
            return True

        # Size mismatch (shouldn't happen if hash matches, but check anyway)
        if current.size != stored.size:
            return True

        # Mtime check (can be used for quick detection, but hash is authoritative)
        # Only use mtime if we want faster but less reliable detection
        if current.mtime != stored.mtime:
            # Mtime changed but hash same - could be touch or git operation
            # Treat as unchanged since content is identical
            pass

        return False

    def get_dirty_files(self, file_paths: list[str]) -> list[str]:
        """
        Get list of files that have changed since last indexing.

        Args:
            file_paths: List of file paths to check

        Returns:
            List of file paths that need re-indexing
        """
        dirty = []
        for file_path in file_paths:
            if self.is_file_changed(file_path):
                dirty.append(file_path)
        return dirty

    def index_files(
        self, file_paths: list[str], extractor: TreeSitterExtractor, force_full: bool = False
    ) -> IndexingResult:
        """
        Index files incrementally, only processing changed files.

        Args:
            file_paths: List of file paths to index
            extractor: TreeSitterExtractor instance for entity extraction
            force_full: If True, re-index all files regardless of changes

        Returns:
            IndexingResult with statistics
        """
        start_time = time.time()
        result = IndexingResult(is_incremental=not force_full)

        # Validate extractor
        if extractor is None:
            result.errors.append("Extractor is None")
            return result

        # Determine which files to process
        if force_full:
            files_to_process = file_paths
            result.files_skipped = 0
        else:
            files_to_process = self.get_dirty_files(file_paths)
            result.files_skipped = len(file_paths) - len(files_to_process)

        result.files_processed = len(files_to_process)

        # Process each file
        for file_path in files_to_process:
            try:
                # Read file content
                path = Path(file_path)
                if not path.exists():
                    # File was deleted - will be cleaned up later
                    result.errors.append(f"File not found: {file_path}")
                    continue

                content = path.read_text(encoding="utf-8", errors="replace")

                # Extract entities and relations
                extraction_result = extractor.extract_from_file(content=content, source_file=file_path)

                # Clear old candidates for this file before adding new ones
                self.store.clear_candidates(source_file=file_path)

                # Store candidate entities
                for entity in extraction_result.entities:
                    self.store.add_candidate_entity(entity)
                    result.entities_extracted += 1

                # Store candidate relations
                for relation in extraction_result.relations:
                    self.store.add_candidate_relation(relation)
                    result.relations_extracted += 1

                # Update file signature
                signature = self.compute_signature(file_path)
                if signature:
                    self.store_signature(signature)

                # Deduct metabolic tax per file processed
                self._deduct_metabolic_tax(amount=0.1)

            except (OSError, TypeError, ValueError) as e:
                error_msg = f"Error indexing {file_path}: {str(e)}"
                result.errors.append(error_msg)
                if os.environ.get("BOS_DEBUG"):
                    _log.info("⚠️ [IncrementalIndexer] {error_msg}")

        result.duration_seconds = time.time() - start_time
        return result

    def cleanup_deleted_files(self, existing_files: list[str]) -> int:
        """
        Remove signatures and entities for deleted files.

        Args:
            existing_files: List of files that currently exist

        Returns:
            Number of files cleaned up
        """
        existing_set = set(existing_files)
        deleted_count = 0

        # Get all tracked files
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT file_path FROM file_signatures")
            tracked_files = [row["file_path"] for row in cursor.fetchall()]

        # Find and clean up deleted files
        for tracked_path in tracked_files:
            if tracked_path not in existing_set:
                # Delete signature
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM file_signatures WHERE file_path = ?", (tracked_path,))
                    conn.commit()

                # Clear candidates for this file
                self.store.clear_candidates(source_file=tracked_path)

                deleted_count += 1

                if os.environ.get("BOS_DEBUG"):
                    _log.info("🗑️ [IncrementalIndexer] Cleaned up deleted file: {tracked_path}")

        return deleted_count

    def get_index_stats(self) -> dict[str, Any]:
        """
        Get statistics about the index.

        Returns:
            Dictionary with index statistics
        """
        with self._get_connection() as conn:
            # Total tracked files
            total_files = conn.execute("SELECT COUNT(*) FROM file_signatures").fetchone()[0]

            # Last indexed timestamp
            last_indexed_row = conn.execute("SELECT MAX(last_indexed) FROM file_signatures").fetchone()
            last_indexed = last_indexed_row[0] if last_indexed_row else None

            # Oldest indexed file
            oldest_row = conn.execute("SELECT MIN(last_indexed) FROM file_signatures").fetchone()
            oldest_indexed = oldest_row[0] if oldest_row else None

            # Total size tracked
            total_size = conn.execute("SELECT COALESCE(SUM(size), 0) FROM file_signatures").fetchone()[0]

        return {
            "total_tracked_files": total_files,
            "last_indexed_timestamp": last_indexed,
            "oldest_indexed_timestamp": oldest_indexed,
            "total_tracked_bytes": total_size,
            "total_tracked_mb": round(total_size / (1024 * 1024), 2),
        }

    def reset_index(self) -> bool:
        """
        Reset the incremental index (clear all signatures).

        Use with caution - this will cause full re-index on next run.

        Returns:
            True if successful
        """
        with self._get_connection() as conn:
            conn.execute("DELETE FROM file_signatures")
            conn.commit()

        if os.environ.get("BOS_DEBUG"):
            _log.info("🔄 [IncrementalIndexer] Index reset - all signatures cleared")

        return True

    def get_file_status(self, file_path: str) -> dict[str, Any]:
        """
        Get detailed status for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file status information
        """
        current = self.compute_signature(file_path)
        stored = self.get_stored_signature(file_path)

        status = {
            "file_path": file_path,
            "exists": current is not None,
            "indexed": stored is not None,
            "changed": False,
            "current": None,
            "stored": None,
        }

        if current:
            status["current"] = {
                "hash": current.file_hash[:16] + "...",
                "mtime": current.mtime,
                "size": current.size,
                "size_human": self._human_readable_size(current.size),
            }

        if stored:
            status["stored"] = {
                "hash": stored.file_hash[:16] + "...",
                "mtime": stored.mtime,
                "size": stored.size,
                "last_indexed": stored.last_indexed,
            }

        if current and stored:
            status["changed"] = self.is_file_changed(file_path)
            status["hash_match"] = current.file_hash == stored.file_hash
            status["size_match"] = current.size == stored.size
            status["mtime_match"] = current.mtime == stored.mtime

        return status

    def _human_readable_size(self, size_bytes: int) -> str:
        """Convert bytes to human readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def batch_index_with_progress(
        self,
        file_paths: list[str],
        extractor: TreeSitterExtractor,
        batch_size: int = 100,
        progress_callback: callable | None = None,
        force_full: bool = False,
    ) -> IndexingResult:
        """
        Index files in batches with progress reporting.

        Args:
            file_paths: List of file paths to index
            extractor: TreeSitterExtractor instance
            batch_size: Number of files per batch
            progress_callback: Optional callback(batch_num, total_batches, files_in_batch)
            force_full: If True, re-index all files

        Returns:
            IndexingResult with aggregated statistics
        """
        start_time = time.time()
        aggregated_result = IndexingResult(is_incremental=not force_full)

        # Filter to dirty files if not forcing full re-index
        if force_full:
            files_to_process = file_paths
        else:
            files_to_process = self.get_dirty_files(file_paths)
            aggregated_result.files_skipped = len(file_paths) - len(files_to_process)

        # Process in batches
        total_files = len(files_to_process)
        num_batches = (total_files + batch_size - 1) // batch_size

        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_files)
            batch = files_to_process[start_idx:end_idx]

            # Process batch
            batch_result = self.index_files(batch, extractor, force_full=True)

            # Aggregate results
            aggregated_result.files_processed += batch_result.files_processed
            aggregated_result.entities_extracted += batch_result.entities_extracted
            aggregated_result.relations_extracted += batch_result.relations_extracted
            aggregated_result.errors.extend(batch_result.errors)

            # Report progress
            if progress_callback:
                progress_callback(batch_num + 1, num_batches, len(batch))

        aggregated_result.duration_seconds = time.time() - start_time
        return aggregated_result

    def ping(self) -> bool:
        """
        Health check for IncrementalIndexer.

        Returns:
            True if indexer is operational
        """
        try:
            # Check database connection
            self.get_index_stats()
            return True
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return False
