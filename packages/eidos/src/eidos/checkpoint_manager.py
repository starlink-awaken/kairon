from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""

import copy
import json
import logging
import sys
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from eidos.organs.storage_dal import SQLiteError, SQLiteRelationalProvider  # type: ignore[import-not-found]

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# CheckpointManager ≡ Session_Checkpoint_System
# 内涵 ≝ {Checkpoint, Policy, Storage, Recovery}
# 外延 ≝ {c | c ∈ D-Memory ∧ manages(c, Checkpoints)}
# 功能 ⊢ {CreateCheckpoint, RestoreCheckpoint, Cleanup}
# =============================================================================

"""
---
Type: Infrastructure
Status: EXPERIMENTAL
Version: 1.0.0
Owner: '@Devil'
Layer: L3
Constraint: "[!!] CHECKPOINT_SYSTEM"
Summary: '会话检查点管理 - 支持多策略和持久化'
Tags:
- checkpoint
- persistence
- recovery
Authority: organs/D-Memory/AGENTS.md
---
"""

_log = logging.getLogger(__name__)
_log = logging.getLogger(__name__)

try:
    from eidos.enhanced_session import EnhancedSession  # type: ignore[import-not-found]
except ImportError:
    from eidos.organs.enhanced_session import EnhancedSession  # type: ignore[no-redef, import-not-found]


class CheckpointPolicy(Protocol):
    """检查点策略接口"""

    def should_create_checkpoint(self, session: EnhancedSession) -> bool: ...


@dataclass
class SessionCheckpoint:
    """会话检查点"""

    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    version: int = 1

    working_data: dict = field(default_factory=dict)
    memory_snapshot: dict = field(default_factory=dict)
    task_context: dict | None = None

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    size_bytes: int = 0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "version": self.version,
            "working_data": self.working_data,
            "memory_snapshot": self.memory_snapshot,
            "task_context": self.task_context,
            "created_at": self.created_at.isoformat(),
            "size_bytes": self.size_bytes,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionCheckpoint:
        created_at = data.get("created_at")
        if created_at:
            if isinstance(created_at, str):
                if created_at.endswith("Z"):
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                else:
                    created_at = datetime.fromisoformat(created_at)

        return cls(
            checkpoint_id=data.get("checkpoint_id", str(uuid.uuid4())),
            session_id=data.get("session_id", ""),
            version=data.get("version", 1),
            working_data=data.get("working_data", {}),
            memory_snapshot=data.get("memory_snapshot", {}),
            task_context=data.get("task_context"),
            created_at=created_at or datetime.now(UTC),
            size_bytes=data.get("size_bytes", 0),
            description=data.get("description", ""),
        )


class TimedPolicy:
    """定时检查点策略"""

    def __init__(self, interval_seconds: int = 60) -> None:
        super().__init__()
        self.interval = interval_seconds

    def should_create_checkpoint(self, session: EnhancedSession) -> bool:
        if not session.last_checkpoint:
            return True

        elapsed = (datetime.now(UTC) - session.last_checkpoint).total_seconds()
        return elapsed >= self.interval


class OperationPolicy:
    """操作计数检查点策略"""

    def __init__(self, interval: int = 10) -> None:
        super().__init__()
        self.interval = interval

    def should_create_checkpoint(self, session: EnhancedSession) -> bool:
        return session.persistence_version % self.interval == 0


class MemoryPolicy:
    """内存阈值检查点策略"""

    def __init__(self, threshold_mb: float = 10.0) -> None:
        super().__init__()
        self.threshold_bytes = threshold_mb * 1024 * 1024

    def should_create_checkpoint(self, session: EnhancedSession) -> bool:
        size = sys.getsizeof(session.working_data) + sys.getsizeof(session.memory_snapshot)
        return size >= self.threshold_bytes


class HybridPolicy:
    """混合检查点策略 - 默认"""

    def __init__(
        self,
        interval_seconds: int = 60,
        operation_interval: int = 10,
        memory_threshold_mb: float = 10.0,
    ) -> None:
        super().__init__()
        self.timed = TimedPolicy(interval_seconds)
        self.operation = OperationPolicy(operation_interval)
        self.memory = MemoryPolicy(memory_threshold_mb)

    def should_create_checkpoint(self, session: EnhancedSession) -> bool:
        return (
            self.timed.should_create_checkpoint(session)
            or self.operation.should_create_checkpoint(session)
            or self.memory.should_create_checkpoint(session)
        )


class CheckpointStorage(Protocol):
    """检查点存储接口"""

    def save(self, checkpoint: SessionCheckpoint) -> bool: ...

    def get(self, checkpoint_id: str) -> SessionCheckpoint | None: ...

    def get_latest(self, session_id: str) -> SessionCheckpoint | None: ...

    def list(self, session_id: str) -> list[SessionCheckpoint]: ...

    def delete(self, checkpoint_id: str) -> bool: ...


class SQLiteCheckpointStorage:
    """SQLite 检查点存储"""

    def __init__(self, db_path: str) -> None:
        super().__init__()
        self.db_path = db_path
        self._db = SQLiteRelationalProvider(self.db_path)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库"""
        self._db.connect()
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """
                CREATE TABLE IF NOT EXISTS session_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    working_data TEXT,
                    memory_snapshot TEXT,
                    task_context TEXT,
                    created_at TEXT NOT NULL,
                    size_bytes INTEGER,
                    description TEXT
                )
            """
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_checkpoint_session ON session_checkpoints(session_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_checkpoint_created ON session_checkpoints(created_at)")

    def save(self, checkpoint: SessionCheckpoint) -> bool:
        """保存检查点"""
        try:
            self._db.execute(
                """
                    INSERT INTO session_checkpoints (
                        checkpoint_id, session_id, version, working_data,
                        memory_snapshot, task_context, created_at, size_bytes, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.checkpoint_id,
                    checkpoint.session_id,
                    checkpoint.version,
                    json.dumps(checkpoint.working_data),
                    json.dumps(checkpoint.memory_snapshot),
                    json.dumps(checkpoint.task_context) if checkpoint.task_context else None,
                    checkpoint.created_at.isoformat(),
                    checkpoint.size_bytes,
                    checkpoint.description,
                ),
            )
            return True
        except SQLiteError:
            return False

    def get(self, checkpoint_id: str) -> SessionCheckpoint | None:
        """获取检查点"""
        try:
            row = self._db.fetch_one(
                "SELECT * FROM session_checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            )
            if not row:
                return None
            return self._row_to_checkpoint(row)
        except SQLiteError:
            return None

    def get_latest(self, session_id: str) -> SessionCheckpoint | None:
        """获取最新检查点"""
        try:
            row = self._db.fetch_one(
                """
                    SELECT * FROM session_checkpoints
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """,
                (session_id,),
            )
            if not row:
                return None
            return self._row_to_checkpoint(row)
        except SQLiteError:
            return None

    def list(self, session_id: str) -> list[SessionCheckpoint]:
        """列出检查点"""
        try:
            rows = self._db.fetch_all(
                """
                    SELECT * FROM session_checkpoints
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                """,
                (session_id,),
            )
            return [self._row_to_checkpoint(row) for row in rows]
        except SQLiteError:
            return []

    def delete(self, checkpoint_id: str) -> bool:
        """删除检查点"""
        try:
            self._db.execute(
                "DELETE FROM session_checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            )
            return True
        except SQLiteError:
            return False

    def _row_to_checkpoint(self, row: Mapping[str, object] | object) -> SessionCheckpoint:
        """行转检查点"""
        data: dict[str, object] = row if isinstance(row, dict) else dict(row) if isinstance(row, Mapping) else {}

        return SessionCheckpoint(
            checkpoint_id=cast(str, data["checkpoint_id"]),
            session_id=cast(str, data["session_id"]),
            version=cast(int, data["version"]),
            working_data=json.loads(cast(str, data["working_data"])) if data["working_data"] else {},
            memory_snapshot=json.loads(cast(str, data["memory_snapshot"])) if data["memory_snapshot"] else {},
            task_context=json.loads(cast(str, data["task_context"])) if data["task_context"] else None,
            created_at=datetime.fromisoformat(cast(str, data["created_at"])),
            size_bytes=cast(int, data.get("size_bytes", 0)),
            description=cast(str, data.get("description", "")),
        )


class CheckpointManager:
    """会话检查点管理器"""

    def __init__(
        self,
        storage: CheckpointStorage,
        policy: CheckpointPolicy | None = None,
        max_checkpoints: int = 10,
    ) -> None:
        self.storage = storage
        self.policy = policy or HybridPolicy()
        self.max_checkpoints = max_checkpoints

    def maybe_create_checkpoint(
        self,
        session: EnhancedSession,
        force: bool = False,
        description: str = "",
    ) -> SessionCheckpoint | None:
        """可能创建检查点"""

        if not force and not self.policy.should_create_checkpoint(session):
            return None

        return self._create_checkpoint(session, description)

    def _create_checkpoint(
        self,
        session: EnhancedSession,
        description: str = "",
    ) -> SessionCheckpoint:
        """创建检查点"""

        checkpoint = SessionCheckpoint(
            checkpoint_id=str(uuid.uuid4()),
            session_id=session.session_id,
            version=session.persistence_version,
            working_data=copy.deepcopy(session.working_data),
            memory_snapshot=copy.deepcopy(session.memory_snapshot),
            task_context=copy.deepcopy(session.task_context),
            created_at=datetime.now(UTC),
            size_bytes=sys.getsizeof(session.working_data) + sys.getsizeof(session.memory_snapshot),
            description=description,
        )

        self.storage.save(checkpoint)

        session.last_checkpoint = checkpoint.created_at
        session.persistence_version += 1

        self._cleanup_old_checkpoints(session.session_id)

        return checkpoint

    def restore_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str | None = None,
    ) -> dict | None:
        """恢复检查点"""

        if checkpoint_id:
            checkpoint = self.storage.get(checkpoint_id)
        else:
            checkpoint = self.storage.get_latest(session_id)

        if not checkpoint:
            return None

        return {
            "working_data": checkpoint.working_data,
            "memory_snapshot": checkpoint.memory_snapshot,
            "task_context": checkpoint.task_context,
            "restored_at": datetime.now(UTC),
            "checkpoint_id": checkpoint.checkpoint_id,
            "version": checkpoint.version,
        }

    def _cleanup_old_checkpoints(self, session_id: str) -> None:
        """清理旧检查点"""

        checkpoints = self.storage.list(session_id)

        if len(checkpoints) > self.max_checkpoints:
            to_delete = checkpoints[self.max_checkpoints :]
            for cp in to_delete:
                self.storage.delete(cp.checkpoint_id)

    def get_checkpoint_count(self, session_id: str) -> int:
        """获取检查点数量"""
        return len(self.storage.list(session_id))
