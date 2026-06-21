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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol


class EnergyLedger(Protocol):
    """Protocol for cross-organ energy ledger."""

    def get_balance(self) -> float: ...
    def deduct_usage(self, agent_id: str, operation: str, ref_id: str, usage: dict | None = None) -> float: ...


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# SessionEnergyTracker ≡ Session_Energy_System
# 内涵 ≝ {Budget, Charge, Track, Report}
# 外延 ≝ {e | e ∈ D-Economy ∧ tracks(e, SessionEnergy)}
# 功能 ⊢ {Charge, Reserve, Release, Close}
# =============================================================================

"""
---
Type: Infrastructure
Status: EXPERIMENTAL
Version: 1.0.0
Owner: '@Devil'
Layer: L3
Constraint: "[!!] ENERGY_TRACKING"
Summary: '会话能量追踪器 - Role-Worker 会话能量核算'
Tags:
- energy
- tracking
- economy
Authority: organs/D-Memory/AGENTS.md
---
"""

_log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# 异常定义
# =============================================================================


class SessionEnergyError(Exception):
    """基础异常"""

    pass


class InsufficientEnergyError(SessionEnergyError):
    """能量不足"""

    def __init__(self, remaining: float, required: float, operation: str) -> None:
        self.remaining = remaining
        self.required = required
        self.operation = operation
        super().__init__(f"Insufficient energy for {operation}: have {remaining}, need {required}")


class SessionEnergyClosedError(SessionEnergyError):
    """会话已关闭"""

    pass


class SessionAlreadyExistsError(SessionEnergyError):
    """会话已存在"""

    pass


# =============================================================================
# 操作成本枚举
# =============================================================================


class OperationCost(Enum):
    """会话操作能量成本"""

    SESSION_CREATE = 10.0
    SESSION_UPDATE = 1.0
    SESSION_RESUME = 5.0
    SESSION_END = 2.0
    CHECKPOINT_CREATE = 5.0
    CHECKPOINT_RESTORE = 3.0
    TASK_EXECUTE = 20.0
    TASK_SWITCH = 8.0
    MEMORY_WRITE = 0.5
    MEMORY_READ = 0.1


# =============================================================================
# 会话能量追踪器
# =============================================================================


@dataclass
class SessionEnergyTracker:
    """会话能量追踪器"""

    session_id: str
    agent_id: str
    budget: float = 1000.0
    warning_threshold: float = 0.8

    ledger: EnergyLedger | None = None
    consumed: float = 0.0
    reserved: float = 0.0
    operations: dict[str, int] = field(default_factory=dict)
    _closed: bool = False

    def charge(
        self,
        operation: str,
        usage: dict | None = None,
    ) -> float:
        """扣费"""

        if self._closed:
            raise SessionEnergyClosedError("Session is closed")

        # 计算成本
        cost = self._calculate_cost(operation, usage)

        # 检查本地预算（会话级别控制）
        local_balance = self.get_balance()
        if local_balance < cost:
            raise InsufficientEnergyError(
                remaining=local_balance,
                required=cost,
                operation=operation,
            )

        # 调用账本扣费（如果可用）
        actual_cost = cost
        if self.ledger:
            try:
                # Ledger 返回扣费后的余额，不是消耗量
                # 我们需要计算实际消耗量
                ledger_balance_before = self.ledger.get_balance()
                self.ledger.deduct_usage(
                    agent_id=self.agent_id,
                    operation=f"SESSION_{operation.upper()}",
                    ref_id=self.session_id,
                    usage=usage,
                )
                ledger_balance_after = self.ledger.get_balance()
                actual_cost = ledger_balance_before - ledger_balance_after
            except (TypeError, ValueError, AttributeError, RuntimeError) as e:
                logger.warning(f"Ledger deduction failed: {e}, using local cost")
                actual_cost = cost

        self.consumed += actual_cost
        self.operations[operation] = self.operations.get(operation, 0) + 1

        # 检查告警
        if local_balance <= self.budget * (1 - self.warning_threshold):
            self._on_warning(local_balance)

        return actual_cost

    def reserve(self, amount: float) -> bool:
        """预留能量"""

        remaining = self.get_balance()
        if remaining < amount:
            return False

        self.reserved += amount
        return True

    def release(self, amount: float) -> None:
        """释放预留"""
        self.reserved = max(0, self.reserved - amount)

    def get_balance(self) -> float:
        """获取剩余预算"""
        return self.budget - self.consumed - self.reserved

    def get_usage_ratio(self) -> float:
        """获取使用比例"""
        return self.consumed / self.budget if self.budget > 0 else 1.0

    def close(self) -> dict[str, Any]:
        """关闭会话 - 返回结算报告"""

        # 先扣费，后标记关闭
        try:
            self.charge("SESSION_END")
        except InsufficientEnergyError:
            # 即使能量不足也允许关闭
            pass

        self._closed = True

        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "budget": self.budget,
            "consumed": self.consumed,
            "balance": self.get_balance(),
            "operations": dict(self.operations),
            "closed_at": datetime.now(UTC).isoformat(),
        }

    def _calculate_cost(
        self,
        operation: str,
        usage: dict | None,
    ) -> float:
        """计算操作成本"""

        # 优先使用预定义成本
        try:
            cost = OperationCost[operation.upper()].value
        except (KeyError, AttributeError):
            cost = 1.0  # 默认成本

        # 如果有 usage，按照 token 计算
        if usage and any("tokens" in k for k in usage):
            total_tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            cost = max(cost, total_tokens * 0.001)

        return cost

    def _on_warning(self, remaining: float) -> None:
        """告警回调"""
        logger.warning(
            f"Session {self.session_id} energy low: {remaining}/{self.budget} (threshold: {self.warning_threshold})"
        )


# =============================================================================
# 会话能量管理器
# =============================================================================


class SessionEnergyManager:
    """会话能量管理器 - 跨会话调度"""

    def __init__(self, ledger: EnergyLedger | None = None) -> None:
        self.ledger = ledger
        self._trackers: dict[str, SessionEnergyTracker] = {}

    def create_tracker(
        self,
        session_id: str,
        agent_id: str,
        budget: float = 1000.0,
        warning_threshold: float = 0.8,
    ) -> SessionEnergyTracker:
        """创建会话能量追踪器"""

        if session_id in self._trackers:
            raise SessionAlreadyExistsError(session_id)

        tracker = SessionEnergyTracker(
            session_id=session_id,
            agent_id=agent_id,
            ledger=self.ledger,
            budget=budget,
            warning_threshold=warning_threshold,
        )

        tracker.charge("SESSION_CREATE")
        self._trackers[session_id] = tracker

        return tracker

    def get_tracker(self, session_id: str) -> SessionEnergyTracker | None:
        """获取追踪器"""
        return self._trackers.get(session_id)

    def close_tracker(self, session_id: str) -> dict | None:
        """关闭追踪器"""

        tracker = self._trackers.pop(session_id, None)
        if not tracker:
            return None

        return tracker.close()

    def get_total_consumed(self) -> float:
        """获取总消耗"""
        return sum(t.consumed for t in self._trackers.values())

    def get_total_budget(self) -> float:
        """获取总预算"""
        return sum(t.budget for t in self._trackers.values())

    def get_all_sessions(self) -> list[dict[str, Any]]:
        """获取所有会话状态"""
        return [
            {
                "session_id": t.session_id,
                "consumed": t.consumed,
                "budget": t.budget,
                "balance": t.get_balance(),
                "usage_ratio": t.get_usage_ratio(),
            }
            for t in self._trackers.values()
        ]

    def get_low_energy_sessions(self) -> list[str]:
        """获取低能量会话"""
        return [t.session_id for t in self._trackers.values() if t.get_usage_ratio() >= t.warning_threshold]
