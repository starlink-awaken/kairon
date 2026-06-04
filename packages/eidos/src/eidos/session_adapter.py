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
from enum import Enum
from typing import Protocol

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# EnhancedSessionAdapter ≡ Session_Adaptor
# 内涵 ≝ {EnhancedSession, RoleWorkerSession, Convert}
# 外延 ≝ {a | a ∈ D-Memory ∧ maps(a, ES, RWS)}
# 功能 ⊢ {ToRoleWorkerSession, ToEnhancedSession}
# =============================================================================

"""
---
Type: Infrastructure
Status: EXPERIMENTAL
Version: 1.0.0
Owner: '@Devil'
Layer: L3
Constraint: "[!!] ADAPTER_PATTERN"
Summary: 'EnhancedSession ↔ RoleWorkerSession 双向适配器'
Tags:
- adapter
- session
- conversion
Authority: organs/D-Memory/AGENTS.md
---
"""

_log = logging.getLogger(__name__)
try:
    from .enhanced_session import EnhancedSession, SessionStatus
    from .session_storage import RoleWorkerSession, SessionStorage  # type: ignore[import-not-found]
except ImportError:
    from organs.D_Memory.organs.enhanced_session import (  # type: ignore[no-redef, import-not-found]
        EnhancedSession,
        SessionStatus,
    )
    from organs.D_Memory.organs.session_storage import (  # type: ignore[no-redef, import-not-found]
        RoleWorkerSession,
        SessionStorage,
    )


class EnhancedSessionAdapter:
    """
    EnhancedSession ↔ RoleWorkerSession 适配器

    用途：
    1. 将 EnhancedSession 转换为 RoleWorkerSession 以持久化到 SQLite
    2. 将 RoleWorkerSession 转换回 EnhancedSession 以便业务使用
    """

    @staticmethod
    def to_role_worker_session(session: EnhancedSession) -> RoleWorkerSession:
        """
        EnhancedSession → RoleWorkerSession

        Args:
            session: EnhancedSession 实例

        Returns:
            RoleWorkerSession 实例
        """
        if not session:
            raise ValueError("Session cannot be None")

        return RoleWorkerSession(
            session_id=session.session_id,
            role_id=session.role_id,
            worker_id=session.worker_id,
            started_at=session.started_at,
            last_active=session.last_active,
            state_snapshot=session.working_data,
            memory_context_dump=session.memory_snapshot,
            status=session.status.value if isinstance(session.status, Enum) else str(session.status),
        )

    @staticmethod
    def to_enhanced_session(
        rws: RoleWorkerSession,
        task_context: dict | None = None,
    ) -> EnhancedSession:
        """
        RoleWorkerSession → EnhancedSession

        Args:
            rws: RoleWorkerSession 实例
            task_context: 可选的 task_context 字典

        Returns:
            EnhancedSession 实例
        """
        if not rws:
            raise ValueError("RoleWorkerSession cannot be None")

        # 转换状态
        status = SessionStatus.PREPARING
        try:
            if rws.status:
                status = SessionStatus(rws.status)
        except (ValueError, AttributeError):
            pass

        session = EnhancedSession(
            session_id=rws.session_id,
            role_id=rws.role_id,
            worker_id=rws.worker_id,
            started_at=rws.started_at,
            last_active=rws.last_active,
            status=status,
            working_data=rws.state_snapshot or {},
            memory_snapshot=rws.memory_context_dump or {},
            task_context=task_context,
        )

        # 缺失字段使用默认值
        session.persistence_version = 1
        session.checkpoint_enabled = True

        return session

    @staticmethod
    def to_role_worker_sessions(sessions: list[EnhancedSession]) -> list[RoleWorkerSession]:
        """
        批量转换 EnhancedSession → RoleWorkerSession

        Args:
            sessions: EnhancedSession 列表

        Returns:
            RoleWorkerSession 列表
        """
        return [EnhancedSessionAdapter.to_role_worker_session(s) for s in sessions]

    @staticmethod
    def to_enhanced_sessions(
        rw_sessions: list[RoleWorkerSession],
    ) -> list[EnhancedSession]:
        """
        批量转换 RoleWorkerSession → EnhancedSession

        Args:
            rw_sessions: RoleWorkerSession 列表

        Returns:
            EnhancedSession 列表
        """
        return [EnhancedSessionAdapter.to_enhanced_session(rws) for rws in rw_sessions]


class UnifiedSessionStorage(Protocol):
    """统一会话存储接口"""

    def create(self, session: EnhancedSession) -> bool: ...

    def get(self, session_id: str) -> EnhancedSession | None: ...

    def update(self, session: EnhancedSession) -> bool: ...

    def delete(self, session_id: str) -> bool: ...

    def get_by_role(self, role_id: str) -> list[EnhancedSession]: ...

    def get_by_worker(self, worker_id: str) -> list[EnhancedSession]: ...

    def get_active_sessions(self) -> list[EnhancedSession]: ...


class SQLiteSessionStorageAdapter:
    """
    SQLite 存储适配器 - 实现统一接口

    适配 EnhancedSession 与现有 SessionStorage
    """

    def __init__(self, db_path: str) -> None:
        if not SessionStorage:
            raise ImportError("SessionStorage not available")
        self._storage = SessionStorage(db_path)

    def create(self, session: EnhancedSession) -> bool:
        """创建会话"""
        if not session:
            return False
        try:
            rws = EnhancedSessionAdapter.to_role_worker_session(session)
            self._storage.create(rws)
            return True
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return False

    def get(self, session_id: str) -> EnhancedSession | None:
        """获取会话"""
        try:
            rws = self._storage.get(session_id)
            if not rws:
                return None

            task_context = self._get_task_context(session_id)
            return EnhancedSessionAdapter.to_enhanced_session(rws, task_context)
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return None

    def update(self, session: EnhancedSession) -> bool:
        """更新会话"""
        if not session:
            return False
        try:
            rws = EnhancedSessionAdapter.to_role_worker_session(session)
            return self._storage.update(rws)
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return False

    def delete(self, session_id: str) -> bool:
        """删除会话"""
        try:
            return self._storage.delete(session_id)
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return False

    def get_by_role(self, role_id: str) -> list[EnhancedSession]:
        """按角色获取"""
        try:
            sessions = self._storage.list_sessions(role_id=role_id)
            return EnhancedSessionAdapter.to_enhanced_sessions(sessions)
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return []

    def get_by_worker(self, worker_id: str) -> list[EnhancedSession]:
        """按 Worker 获取"""
        try:
            sessions = self._storage.list_sessions(worker_id=worker_id)
            return EnhancedSessionAdapter.to_enhanced_sessions(sessions)
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return []

    def get_active_sessions(self) -> list[EnhancedSession]:
        """获取活跃会话"""
        try:
            sessions = self._storage.list_sessions(status="active")
            return EnhancedSessionAdapter.to_enhanced_sessions(sessions)
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return []

    def _get_task_context(self, session_id: str) -> dict | None:
        """获取任务上下文（可选扩展）"""
        return None
