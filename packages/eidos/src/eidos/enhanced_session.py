from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# EnhancedSession ≡ Role_Worker_Session
# 内涵 ≝ {session_id, role, worker, task, memory}
# 外延 ≝ {s | s ∈ D-Execution ∧ runtime_context(s, Role, Worker)}
# 功能 ⊢ {ManageContext, EnableCheckpoint, SupportFailover}
# =============================================================================

"""
---
Type: Infrastructure
Status: EXPERIMENTAL
Version: 1.0.0
Owner: '@Devil'
Layer: L3
Constraint: "[!!] NEW_COMPONENT"
Summary: '增强会话 - 完整的运行时上下文，支持持久化和故障转移'
Tags:
- session
- context
- checkpoint
- failover
Authority: organs/D-Memory/AGENTS.md
---
"""

_log = logging.getLogger(__name__)


# Define a Protocol for cross-organ TaskContext
class _TaskContextProtocol(Protocol):
    """Protocol matching the cross-organ TaskContext interface."""

    def to_dict(self) -> dict[str, object]: ...

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> _TaskContextProtocol: ...


try:
    TaskContext: type[_TaskContextProtocol] = __import__(  # type: ignore[no-redef]
        "organs.D_Execution.organs.task_context", fromlist=["TaskContext"]
    ).TaskContext
except ImportError:
    TaskContext: type[_TaskContextProtocol] = _TaskContextProtocol  # type: ignore[no-redef]


class SessionStatus(Enum):
    """会话状态"""

    PREPARING = "preparing"  # 准备中
    ACTIVE = "active"  # 活跃
    SUSPENDED = "suspended"  # 暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    RECOVERED = "recovered"  # 已恢复（从故障中）


@dataclass
class MemorySnapshot:
    """记忆快照"""

    working_memory: dict = field(default_factory=dict)
    episodic_memory: list[dict] = field(default_factory=list)
    semantic_memory: dict = field(default_factory=dict)
    relationship_memory: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "working_memory": self.working_memory,
            "episodic_memory": self.episodic_memory,
            "semantic_memory": self.semantic_memory,
            "relationship_memory": self.relationship_memory,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemorySnapshot:
        return cls(
            working_memory=data.get("working_memory", {}),
            episodic_memory=data.get("episodic_memory", []),
            semantic_memory=data.get("semantic_memory", {}),
            relationship_memory=data.get("relationship_memory", {}),
        )


@dataclass
class EnhancedSession:
    """
    增强会话 - 完整的运行时上下文

    特点：
    1. 包含完整的任务上下文
    2. 支持内存快照
    3. 支持检查点
    4. 支持状态持久化
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role_id: str = ""
    worker_id: str = ""

    # 任务上下文（使用 dict 避免循环导入）
    task_context: dict | None = None

    # 状态
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_active: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: SessionStatus = SessionStatus.PREPARING

    # 内存上下文
    memory_snapshot: dict = field(default_factory=dict)
    working_data: dict = field(default_factory=dict)

    # 持久化状态
    persistence_version: int = 1
    checkpoint_enabled: bool = True
    last_checkpoint: datetime | None = None

    # 元数据
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "role_id": self.role_id,
            "worker_id": self.worker_id,
            "task_context": self.task_context,
            "started_at": self.started_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "status": self.status.value,
            "memory_snapshot": self.memory_snapshot,
            "working_data": self.working_data,
            "persistence_version": self.persistence_version,
            "checkpoint_enabled": self.checkpoint_enabled,
            "last_checkpoint": self.last_checkpoint.isoformat() if self.last_checkpoint else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnhancedSession:
        started_at = data.get("started_at")
        if started_at:
            if started_at.endswith("Z"):
                started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            else:
                started_at = datetime.fromisoformat(started_at)

        last_active = data.get("last_active")
        if last_active:
            if last_active.endswith("Z"):
                last_active = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
            else:
                last_active = datetime.fromisoformat(last_active)

        last_checkpoint = data.get("last_checkpoint")
        if last_checkpoint:
            if last_checkpoint.endswith("Z"):
                last_checkpoint = datetime.fromisoformat(last_checkpoint.replace("Z", "+00:00"))
            else:
                last_checkpoint = datetime.fromisoformat(last_checkpoint)

        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            role_id=data.get("role_id", ""),
            worker_id=data.get("worker_id", ""),
            task_context=data.get("task_context"),
            started_at=started_at or datetime.now(UTC),
            last_active=last_active or datetime.now(UTC),
            status=SessionStatus(data.get("status", "preparing")),
            memory_snapshot=data.get("memory_snapshot", {}),
            working_data=data.get("working_data", {}),
            persistence_version=data.get("persistence_version", 1),
            checkpoint_enabled=data.get("checkpoint_enabled", True),
            last_checkpoint=last_checkpoint,
            metadata=data.get("metadata", {}),
        )

    def is_active(self) -> bool:
        """检查会话是否活跃"""
        return self.status == SessionStatus.ACTIVE

    def update_activity(self) -> None:
        """更新最后活跃时间"""
        self.last_active = datetime.now(UTC)

    def create_checkpoint(self) -> bool:
        """创建检查点"""
        if not self.checkpoint_enabled:
            return False

        self.last_checkpoint = datetime.now(UTC)
        self.persistence_version += 1
        return True

    def get_task_context(self) -> _TaskContextProtocol | None:
        """获取任务上下文对象"""
        if self.task_context and TaskContext:
            return TaskContext.from_dict(self.task_context)
        return None

    def set_task_context(self, context: _TaskContextProtocol) -> None:
        """设置任务上下文"""
        if context:
            self.task_context = context.to_dict()


# =============================================================================
# 会话存储接口
# =============================================================================


class SessionStorage(Protocol):
    """会话存储接口"""

    def create(self, session: EnhancedSession) -> bool: ...

    def get(self, session_id: str) -> EnhancedSession | None: ...

    def update(self, session: EnhancedSession) -> bool: ...

    def delete(self, session_id: str) -> bool: ...

    def get_by_role(self, role_id: str) -> list[EnhancedSession]: ...

    def get_by_worker(self, worker_id: str) -> list[EnhancedSession]: ...

    def get_active_sessions(self) -> list[EnhancedSession]: ...


# =============================================================================
# 内存实现
# =============================================================================


class InMemorySessionStorage:
    """内存版会话存储"""

    def __init__(self) -> None:
        self._sessions: dict[str, EnhancedSession] = {}

    def create(self, session: EnhancedSession) -> bool:
        if session.session_id in self._sessions:
            return False
        self._sessions[session.session_id] = session
        return True

    def get(self, session_id: str) -> EnhancedSession | None:
        return self._sessions.get(session_id)

    def update(self, session: EnhancedSession) -> bool:
        if session.session_id not in self._sessions:
            return False
        self._sessions[session.session_id] = session
        return True

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_by_role(self, role_id: str) -> list[EnhancedSession]:
        return [s for s in self._sessions.values() if s.role_id == role_id]

    def get_by_worker(self, worker_id: str) -> list[EnhancedSession]:
        return [s for s in self._sessions.values() if s.worker_id == worker_id]

    def get_active_sessions(self) -> list[EnhancedSession]:
        return [s for s in self._sessions.values() if s.status in [SessionStatus.ACTIVE, SessionStatus.PREPARING]]
