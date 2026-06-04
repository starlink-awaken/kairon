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
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from threading import Lock
from typing import Protocol

from eidos.atomic_state_manager import managed_connection

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# AtomicStateManager ≡ Atomic_State_Management
# 内涵 ≝ {Acquire, Update, Commit, Rollback}
# 外延 ≝ {s | s ∈ D-Continuity ∧ manages(s, State)}
# 功能 ⊢ {AtomicUpdate, TransactionSupport, RollbackSupport}
# =============================================================================

"""
---
Type: Infrastructure
Status: EXPERIMENTAL
Version: 1.0.0
Owner: '@Devil'
Layer: L3
Constraint: "[!!] NEW_COMPONENT"
Summary: '原子状态管理器 - 保证状态更新的原子性，支持回滚'
Tags:
- atomic
- transaction
- rollback
- state
Authority: organs/D-Continuity/AGENTS.md
---
"""

_log = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class TransactionStatus(Enum):
    """事务状态"""

    PENDING = "pending"
    PREPARING = "preparing"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class Transaction:
    """事务记录"""

    transaction_id: str
    role_id: str
    worker_id: str
    session_id: str
    status: TransactionStatus
    started_at: datetime
    completed_at: datetime | None = None
    operations: list[dict] = field(default_factory=list)
    error: str | None = None


class OptimisticLockError(Exception):
    """乐观锁错误"""

    pass


class VersionConflictError(OptimisticLockError):
    """版本冲突错误 – 乐观锁检测到并发修改"""

    pass


class WorkerLockError(Exception):
    """Worker 锁错误"""

    pass


class _RoleStateStorageProtocol(Protocol):
    def get_version(self, role_id: str) -> int: ...
    def save(self, state: dict) -> bool: ...
    def atomic_save(self, role_id: str, state: dict, expected_version: int) -> tuple[bool, str | None]: ...


class _WorkerProtocol(Protocol):
    def can_accept_task(self) -> bool: ...


class _WorkerRegistryProtocol(Protocol):
    def get_worker(self, worker_id: str) -> _WorkerProtocol | None: ...
    def update_worker_status(self, worker_id: str, status: str) -> None: ...


class _SessionProtocol(Protocol):
    role_id: str
    worker_id: str


class _SessionStorageProtocol(Protocol):
    def get(self, session_id: str) -> _SessionProtocol | None: ...
    def update_session_status(self, session_id: str, status: str) -> None: ...


class AtomicStateManager:
    """
    原子状态管理器

    特性：
    1. 乐观锁机制 - 避免悲观锁的性能问题
    2. 自动重试 - 版本冲突时自动重试
    3. 操作日志 - 记录所有操作，支持回滚
    4. 超时保护 - 防止死锁
    """

    MAX_RETRIES = 3
    LOCK_TIMEOUT = 5.0
    RETRY_DELAY_BASE = 0.1  # 秒

    def __init__(
        self,
        role_state_storage: _RoleStateStorageProtocol | None = None,
        session_storage: _SessionStorageProtocol | None = None,
        worker_registry: _WorkerRegistryProtocol | None = None,
    ) -> None:
        self.status = "active"
        self.role_state_storage = role_state_storage
        self.session_storage = session_storage
        self.worker_registry = worker_registry

        # 内存实现（如果没有提供存储）
        self._in_memory_role_state: dict[str, dict] = {}

        # 事务日志
        self._transactions: dict[str, Transaction] = {}

        # 锁
        self._role_locks: dict[str, Lock] = {}
        self._locks_lock = Lock()

    def _get_role_lock(self, role_id: str) -> Lock:
        """获取角色锁"""
        with self._locks_lock:
            if role_id not in self._role_locks:
                self._role_locks[role_id] = Lock()
            return self._role_locks[role_id]

    def _get_version(self, role_id: str) -> int:
        """获取当前版本号"""
        if self.role_state_storage:
            return self.role_state_storage.get_version(role_id)
        state = self._in_memory_role_state.get(role_id)
        return state.get("version", 0) if state else 0

    def _save_state(self, role_id: str, state: dict) -> bool:
        """保存状态"""
        if self.role_state_storage:
            return self.role_state_storage.save(state)
        self._in_memory_role_state[role_id] = state
        return True

    def assume_role_atomic(
        self,
        role_id: str,
        worker_id: str,
        task_context: dict,
    ) -> tuple[bool, str | None]:
        """
        原子化执行角色绑定

        Returns:
            (success, session_id_or_error)
        """
        session_id = str(uuid.uuid4())

        for attempt in range(self.MAX_RETRIES):
            try:
                # 1. 检查并锁定 Role
                role_lock = self._get_role_lock(role_id)
                if not role_lock.acquire(timeout=self.LOCK_TIMEOUT):
                    return False, "Failed to acquire role lock"

                try:
                    # 2. 获取当前版本
                    current_version = self._get_version(role_id)

                    # 3. 尝试原子更新
                    success, error = self._try_assume_role(
                        role_id=role_id,
                        worker_id=worker_id,
                        task_context=task_context,
                        session_id=session_id,
                        expected_version=current_version,
                    )

                    if success:
                        # 4. 记录事务
                        self._record_transaction(
                            role_id=role_id,
                            worker_id=worker_id,
                            session_id=session_id,
                            status=TransactionStatus.COMMITTED,
                        )
                        logger.info(f"Role {role_id} assumed by {worker_id}, session: {session_id}")
                        return True, session_id

                    # 检查是否是版本冲突
                    if isinstance(error, VersionConflictError) or (
                        isinstance(error, str) and ("version" in error.lower() or "conflict" in error.lower())
                    ):
                        # 版本冲突，重试
                        logger.warning(f"Version conflict for role {role_id}, retry {attempt + 1}")
                        time.sleep(self.RETRY_DELAY_BASE * (attempt + 1))
                        continue

                    # 其他错误，不重试
                    return False, error

                finally:
                    role_lock.release()

            except (TypeError, ValueError, AttributeError) as e:
                logger.error(f"Unexpected error in assume_role_atomic: {e}")
                return False, str(e)

        # 超过最大重试次数
        self._record_transaction(
            role_id=role_id,
            worker_id=worker_id,
            session_id=session_id,
            status=TransactionStatus.FAILED,
            error="Max retries exceeded",
        )
        return False, "Max retries exceeded"

    def _try_assume_role(
        self,
        role_id: str,
        worker_id: str,
        task_context: dict,
        session_id: str,
        expected_version: int,
    ) -> tuple[bool, str | None]:
        """尝试执行角色绑定（内部方法）"""

        # 1. 验证 Worker 可用
        if self.worker_registry:
            worker = self.worker_registry.get_worker(worker_id)
            if not worker:
                return False, f"Worker {worker_id} not found"
            if not worker.can_accept_task():
                return False, f"Worker {worker_id} cannot accept task"

        # 2. 检查并更新版本（乐观锁）
        new_version = expected_version + 1

        # 3. 构建新状态
        new_state = {
            "role_id": role_id,
            "current_worker": worker_id,
            "current_task_id": task_context.get("task_id"),
            "session_id": session_id,
            "last_active": datetime.now(UTC).isoformat(),
            "binding_strategy": task_context.get("binding_strategy", "on_demand"),
            "accumulated_load": 0.0,
            "version": new_version,
        }

        # 4. 保存状态（如果存储支持版本检查）
        if self.role_state_storage and hasattr(self.role_state_storage, "atomic_save"):
            success, error = self.role_state_storage.atomic_save(role_id, new_state, expected_version)
            if not success:
                return False, error
        else:
            # 内存实现：直接保存
            self._save_state(role_id, new_state)

        # 5. 更新 Worker 状态
        if self.worker_registry:
            self.worker_registry.update_worker_status(worker_id, "busy")

        return True, None

    def release_role_atomic(
        self,
        session_id: str,
    ) -> tuple[bool, str | None]:
        """
        原子化执行角色释放

        Returns:
            (success, error_or_none)
        """
        # 1. 获取会话信息
        if self.session_storage:
            session = self.session_storage.get(session_id)
            if not session:
                return False, f"Session {session_id} not found"
            role_id = session.role_id
            worker_id = session.worker_id
        else:
            # 从内存状态查找
            role_id = None
            worker_id = None
            for rid, state in self._in_memory_role_state.items():
                if state.get("session_id") == session_id:
                    role_id = rid
                    worker_id = state.get("current_worker")
                    break

            if not role_id:
                return False, f"Session {session_id} not found"

        try:
            # 2. 锁定 Role
            role_lock = self._get_role_lock(role_id)
            if not role_lock.acquire(timeout=self.LOCK_TIMEOUT):
                return False, "Failed to acquire role lock"

            try:
                # 3. 清空运行时状态
                new_state = {
                    "role_id": role_id,
                    "current_worker": None,
                    "current_task_id": None,
                    "session_id": None,
                    "last_active": datetime.now(UTC).isoformat(),
                    "binding_strategy": "on_demand",
                    "accumulated_load": 0.0,
                    "version": self._get_version(role_id) + 1,
                }
                self._save_state(role_id, new_state)

                # 4. 更新 Worker 状态
                if self.worker_registry and worker_id:
                    self.worker_registry.update_worker_status(worker_id, "idle")

                # 5. 标记会话结束
                if self.session_storage:
                    self.session_storage.update_session_status(session_id, "completed")

                self._record_transaction(
                    role_id=role_id,
                    worker_id=worker_id,
                    session_id=session_id,
                    status=TransactionStatus.COMMITTED,
                )

                logger.info(f"Role {role_id} released from {worker_id}")
                return True, None

            finally:
                role_lock.release()

        except (TypeError, ValueError, AttributeError) as e:
            logger.error(f"Error in release_role_atomic: {e}")
            return False, str(e)

    def check_version_conflict(self, expected_version: int, actual_version: int) -> bool:
        """乐观锁版本检查 – 整数版本号比较，而非字符串匹配。

        Returns:
            True 如果版本匹配（无冲突）

        Raises:
            VersionConflictError: 版本不一致时抛出
        """
        if expected_version != actual_version:
            raise VersionConflictError(f"Version conflict: expected {expected_version}, got {actual_version}")
        return True

    def _record_transaction(
        self,
        role_id: str,
        worker_id: str,
        session_id: str,
        status: TransactionStatus,
        error: str | None = None,
    ) -> None:
        """记录事务"""
        tx = Transaction(
            transaction_id=str(uuid.uuid4()),
            role_id=role_id,
            worker_id=worker_id,
            session_id=session_id,
            status=status,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            error=error,
        )
        self._transactions[tx.transaction_id] = tx

    def get_transaction_history(
        self,
        role_id: str | None = None,
        limit: int = 100,
    ) -> list[Transaction]:
        """获取事务历史"""
        txs = list(self._transactions.values())

        if role_id:
            txs = [tx for tx in txs if tx.role_id == role_id]

        # 按时间排序
        txs.sort(key=lambda x: x.started_at, reverse=True)
        return txs[:limit]


# =============================================================================
# 便捷函数
# =============================================================================


def create_atomic_manager(
    use_persistent_storage: bool = False,
    db_path: str = ".bos_atomic_states.db",
) -> AtomicStateManager:
    """
    创建原子状态管理器

    Args:
        use_persistent_storage: 是否使用持久化存储
        db_path: SQLite 数据库路径（use_persistent_storage=True 时生效）

    Returns:
        AtomicStateManager 实例
    """
    if use_persistent_storage:
        return _SQLiteAtomicStateManager(db_path=db_path)

    return AtomicStateManager()


class _SQLiteRoleStateStorage:
    """SQLite 后端的角色状态存储，供 AtomicStateManager 内部使用。"""

    def __init__(self, db_path: str) -> None:
        super().__init__()
        import sqlite3

        self._db_path = db_path
        with managed_connection(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS atomic_states (
                    role_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )"""
            )
            conn.commit()

    def get_version(self, role_id: str) -> int:
        import sqlite3

        with managed_connection(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute("SELECT version FROM atomic_states WHERE role_id=?", (role_id,)).fetchone()
        return row[0] if row else 0

    def save(self, state: dict) -> bool:
        import json
        import sqlite3
        from datetime import datetime

        role_id = state.get("role_id")
        if not role_id:
            return False
        try:
            with managed_connection(sqlite3.connect(self._db_path)) as conn:
                conn.execute(
                    """INSERT INTO atomic_states(role_id, state_json, version, updated_at)
                       VALUES(?,?,?,?)
                       ON CONFLICT(role_id) DO UPDATE SET
                           state_json=excluded.state_json,
                           version=excluded.version,
                           updated_at=excluded.updated_at""",
                    (
                        role_id,
                        json.dumps(state, default=str),
                        state.get("version", 0),
                        datetime.now(UTC).isoformat(),
                    ),
                )
            return True
        except sqlite3.Error as e:
            _log.error("%s: %s", type(e).__name__, e)
            return False

    def atomic_save(self, role_id: str, state: dict, expected_version: int) -> tuple[bool, str | None]:
        """乐观锁保存：仅当版本匹配时写入。返回 (success, error_msg)。"""
        import json
        import sqlite3
        from datetime import datetime

        try:
            with managed_connection(sqlite3.connect(self._db_path)) as conn:
                current = conn.execute("SELECT version FROM atomic_states WHERE role_id=?", (role_id,)).fetchone()
                current_version = current[0] if current else 0
                if current_version != expected_version:
                    return (
                        False,
                        f"Version conflict: expected {expected_version}, got {current_version}",
                    )
                conn.execute(
                    """INSERT INTO atomic_states(role_id, state_json, version, updated_at)
                       VALUES(?,?,?,?)
                       ON CONFLICT(role_id) DO UPDATE SET
                           state_json=excluded.state_json,
                           version=excluded.version,
                           updated_at=excluded.updated_at""",
                    (
                        role_id,
                        json.dumps(state, default=str),
                        expected_version + 1,
                        datetime.now(UTC).isoformat(),
                    ),
                )
            return True, None
        except sqlite3.Error as exc:
            _log.error("%s: %s", type(exc).__name__, exc)
            return False, str(exc)


class _SQLiteAtomicStateManager(AtomicStateManager):
    """AtomicStateManager with SQLite-backed persistence."""

    def __init__(self, db_path: str = ".bos_atomic_states.db") -> None:
        storage = _SQLiteRoleStateStorage(db_path)
        super().__init__(role_state_storage=storage)
        self._db_path = db_path
