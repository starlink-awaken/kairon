from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Memory/AGENTS.md
Layer: L3
Domain: D-Memory
Summary: "BehaviorLogger — 持久化用户行为事件到 FactGraph，支持事件查询与用户活动摘要。"
BOS-URI:
  - bos://memory/behavior/log    → log_event
  - bos://memory/behavior/query  → query_events
  - bos://memory/behavior/summary → get_user_activity_summary
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Behavior Logger ≡ Module
# 内涵 ≝ {Behavior, Logger}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, BehaviorLogger)}
# 功能 ⊢ {Behavior_Logger, Init_Behavior, Validate_Logger}
# =============================================================================

import json
import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

_log = logging.getLogger(__name__)


class EventType(StrEnum):
    """用户行为事件类型枚举。"""

    TOOL_USAGE = "tool_usage"
    COMMAND_EXECUTION = "command_execution"
    NAVIGATION = "navigation"
    PREFERENCE_SIGNAL = "preference_signal"
    FEEDBACK = "feedback"


@dataclass
class BehaviorEvent:
    """用户行为事件数据类。

    Attributes:
        event_id: 事件唯一标识符 (UUID)。
        event_type: 事件类型，参见 EventType 枚举。
        event_data: 事件详细数据字典。
        timestamp: 事件发生时间 (ISO 8601 字符串)。
        session_id: 会话标识符。
        user_id: 用户标识符。
    """

    event_id: str
    event_type: EventType | str
    event_data: dict[str, Any]
    timestamp: str
    session_id: str
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        """将事件转换为字典格式。"""
        return {
            "event_id": self.event_id,
            "event_type": (self.event_type.value if isinstance(self.event_type, EventType) else self.event_type),
            "event_data": self.event_data,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BehaviorEvent:
        """从字典恢复事件对象。"""
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"])
            if data["event_type"] in [e.value for e in EventType]
            else data["event_type"],
            event_data=data["event_data"],
            timestamp=data["timestamp"],
            session_id=data["session_id"],
            user_id=data["user_id"],
        )


class BehaviorLogger:
    """用户行为日志记录器。

    将用户行为事件持久化到 FactGraph (TripleStore)，并在 FactGraph 不可用时
    回退到内存存储。提供事件记录、查询和活动摘要功能。

    BOS-URI:
        - bos://memory/behavior/log     → log_event
        - bos://memory/behavior/query  → query_events
        - bos://memory/behavior/summary → get_user_activity_summary

    Example:
        logger = BehaviorLogger()
        event = logger.log_event(EventType.TOOL_USAGE, {"tool": "grep", "pattern": "foo"})
        events = logger.query_events(event_type=EventType.TOOL_USAGE, limit=10)
        summary = logger.get_user_activity_summary("@Prime", days=7)
    """

    def __init__(self) -> None:
        self._fact_graph = None
        self._fg_available = True
        # 实例级内存回退存储（避免多实例共享状态）
        self._memory_store: list[BehaviorEvent] = []
        self._memory_lock = threading.Lock()
        self._MAX_MEMORY_STORE = 10000  # 内存存储上限
        self._try_init_fact_graph()

    def _try_init_fact_graph(self) -> None:
        """尝试初始化 FactGraph 连接。"""
        try:
            from eidos.fact_graph import get_fact_graph  # type: ignore[import-not-found]

            self._fact_graph = get_fact_graph()
            _log.info("[BehaviorLogger] FactGraph connection established.")
        except (ImportError, AttributeError, ConnectionError) as e:
            _log.warning("[BehaviorLogger] FactGraph unavailable, using in-memory fallback: %s", e)
            self._fg_available = False

    def log_event(
        self,
        event_type: EventType | str,
        event_data: dict[str, Any],
        session_id: str = "@Prime",
        user_id: str = "@Prime",
    ) -> BehaviorEvent:
        """记录用户行为事件。

        Args:
            event_type: 事件类型，参见 EventType 枚举或字符串。
            event_data: 事件详细数据字典。
            session_id: 会话标识符，默认为 "@Prime"。
            user_id: 用户标识符，默认为 "@Prime"。

        Returns:
            BehaviorEvent: 创建的行为事件对象。

        Raises:
            ValueError: event_type 无效或 event_data 为空。
        """
        # 类型归一化
        if isinstance(event_type, str):
            try:
                event_type = EventType(event_type)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid event_type '{event_type}'. Expected one of: {[e.value for e in EventType]}"
                ) from exc

        if not event_data:
            raise ValueError("event_data cannot be empty.")

        timestamp = datetime.now(UTC).isoformat()
        event_id = str(uuid.uuid4())

        event = BehaviorEvent(
            event_id=event_id,
            event_type=event_type,
            event_data=event_data,
            timestamp=timestamp,
            session_id=session_id,
            user_id=user_id,
        )

        # 持久化到 FactGraph 或回退到内存
        try:
            self._persist_to_fact_graph(event)
        except (OSError, ConnectionError, AttributeError) as e:
            _log.warning("[BehaviorLogger] Failed to persist to FactGraph, using memory: %s", e)
            self._fallback_memory_store(event)

        _log.debug(
            "[BehaviorLogger] Event logged: type=%s, user=%s, session=%s",
            event.event_type.value if isinstance(event.event_type, EventType) else event.event_type,
            user_id,
            session_id,
        )

        return event

    def _persist_to_fact_graph(self, event: BehaviorEvent) -> None:
        """将行为事件持久化到 FactGraph (TripleStore)。

        事件以三元组形式存储:
            Subject:   bos://memory/behavior/{event_id}
            Predicate: event:{event_type}
            Object:   {json serialized event_data}

        Args:
            event: 要持久化的行为事件。
        """
        if self._fact_graph is None:
            self._try_init_fact_graph()

        if self._fact_graph is None:
            raise RuntimeError("FactGraph not available.")

        event_type_str = event.event_type.value if isinstance(event.event_type, EventType) else event.event_type

        sub = f"bos://memory/behavior/{event.event_id}"
        pred = f"event:{event_type_str}"
        obj = json.dumps(event.to_dict(), ensure_ascii=False, default=str)

        metadata = {
            "user_id": event.user_id,
            "session_id": event.session_id,
            "timestamp": event.timestamp,
            "event_type": event_type_str,
        }

        self._fact_graph.add_fact(sub, pred, obj, metadata=metadata)

        _log.debug("[BehaviorLogger] Persisted to FactGraph: sub=%s, pred=%s", sub, pred)

    def _fallback_memory_store(self, event: BehaviorEvent) -> None:
        """内存回退存储（线程安全）。

        Args:
            event: 要存储的行为事件。
        """
        with self._memory_lock:
            # 超过上限时移除最旧的记录
            if len(self._memory_store) >= self._MAX_MEMORY_STORE:
                # 移除最早的一半记录
                self._memory_store = self._memory_store[self._MAX_MEMORY_STORE // 2 :]
                _log.warning("[BehaviorLogger] Memory store overflow, trimmed oldest half.")
            self._memory_store.append(event)

    def query_events(
        self,
        event_type: EventType | str | None = None,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        limit: int = 100,
    ) -> list[BehaviorEvent]:
        """查询行为事件。

        Args:
            event_type: 按事件类型过滤（可选）。
            start_time: 查询起始时间（datetime 或 ISO 8601 字符串，可选）。
            end_time: 查询结束时间（datetime 或 ISO 8601 字符串，可选）。
            limit: 返回结果上限，默认 100。

        Returns:
            list[BehaviorEvent]: 匹配条件的行为事件列表，按时间倒序排列。
        """
        events: list[BehaviorEvent] = []

        # 类型归一化
        resolved_type: EventType | None = None
        if isinstance(event_type, str) and event_type:
            try:
                resolved_type = EventType(event_type)
            except ValueError:
                resolved_type = None
        elif isinstance(event_type, EventType):
            resolved_type = event_type

        # 时间归一化
        if isinstance(start_time, str):
            try:
                start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            except ValueError:
                start_time = None
        if isinstance(end_time, str):
            try:
                end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            except ValueError:
                end_time = None

        # 优先从 FactGraph 查询
        if self._fg_available and self._fact_graph is not None:
            try:
                events = self._query_from_fact_graph(resolved_type, start_time, end_time, limit)
                if events:
                    return events
            except (OSError, ConnectionError, AttributeError) as e:
                _log.warning("[BehaviorLogger] FactGraph query failed: %s", e)
                self._fg_available = False

        # 回退到内存查询
        return self._query_from_memory(resolved_type, start_time, end_time, limit)

    def _query_from_fact_graph(
        self,
        event_type: EventType | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> list[BehaviorEvent]:
        """从 FactGraph 查询事件。

        Args:
            event_type: 事件类型过滤。
            start_time: 起始时间。
            end_time: 结束时间。
            limit: 结果上限。

        Returns:
            list[BehaviorEvent]: 查询结果列表。
        """
        if self._fact_graph is None:
            return []

        sub = "bos://memory/behavior/*"

        # 先获取所有 behavior 节点，再在内存中过滤
        if event_type is not None:
            pred = f"event:{event_type.value}"
        else:
            pred = None

        raw_results = self._fact_graph.query(sub=sub, pred=pred, obj=None)

        events: list[BehaviorEvent] = []
        for row in raw_results[:limit]:
            try:
                obj_str = row.get("obj", "")
                if obj_str:
                    event_dict = json.loads(obj_str)
                    events.append(BehaviorEvent.from_dict(event_dict))
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                _log.warning("[BehaviorLogger] Failed to parse FactGraph row: %s", e)
                continue

        # 时间过滤（已在 Triple 查询层面做初步过滤）
        events = self._filter_by_time_range(events, start_time, end_time)

        return events

    def _query_from_memory(
        self,
        event_type: EventType | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> list[BehaviorEvent]:
        """从内存存储查询事件。

        Args:
            event_type: 事件类型过滤。
            start_time: 起始时间。
            end_time: 结束时间。
            limit: 结果上限。

        Returns:
            list[BehaviorEvent]: 查询结果列表，按时间倒序排列。
        """
        with self._memory_lock:
            filtered = []
            for event in reversed(self._memory_store):
                # 类型过滤
                if event_type is not None:
                    ev_type = event.event_type.value if isinstance(event.event_type, EventType) else event.event_type
                    if ev_type != event_type.value:
                        continue

                # 时间过滤
                if self._filter_by_time_range([event], start_time, end_time):
                    filtered.append(event)

                    if len(filtered) >= limit:
                        break

            return filtered

    def _filter_by_time_range(
        self,
        events: list[BehaviorEvent],
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> list[BehaviorEvent]:
        """按时间范围过滤事件。

        Args:
            events: 待过滤的事件列表。
            start_time: 起始时间。
            end_time: 结束时间。

        Returns:
            list[BehaviorEvent]: 过滤后的事件列表。
        """
        if start_time is None and end_time is None:
            return events

        result = []
        for event in events:
            try:
                event_dt = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            except ValueError:
                continue

            if start_time is not None and event_dt < start_time:
                continue
            if end_time is not None and event_dt > end_time:
                continue

            result.append(event)

        return result

    def get_user_activity_summary(
        self,
        user_id: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """获取用户在指定时间段内的活动摘要。

        Args:
            user_id: 用户标识符。
            days: 统计天数，默认 7 天。

        Returns:
            dict[str, Any]: 活动摘要，包含：
                - user_id: 用户标识符
                - total_events: 事件总数
                - event_type_counts: 各类型事件计数
                - daily_counts: 每日事件计数
                - top_sessions: 最活跃的会话
                - time_range_days: 统计时间范围（天）
        """
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=days)

        events = self.query_events(
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            limit=10000,  # 获取足够多的事件
        )

        # 过滤指定用户
        user_events = [e for e in events if e.user_id == user_id]

        # 统计各类型事件数量
        event_type_counts: dict[str, int] = {}
        for event in user_events:
            ev_type = event.event_type.value if isinstance(event.event_type, EventType) else event.event_type
            event_type_counts[ev_type] = event_type_counts.get(ev_type, 0) + 1

        # 统计每日事件数量
        daily_counts: dict[str, int] = {}
        for event in user_events:
            try:
                event_dt = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
                day_key = event_dt.strftime("%Y-%m-%d")
                daily_counts[day_key] = daily_counts.get(day_key, 0) + 1
            except ValueError:
                continue

        # 统计最活跃会话
        session_counts: dict[str, int] = {}
        for event in user_events:
            session_counts[event.session_id] = session_counts.get(event.session_id, 0) + 1

        top_sessions: list[dict[str, Any]] = sorted(
            [{"session_id": sid, "count": cnt} for sid, cnt in session_counts.items()],
            key=lambda x: x["count"],  # type: ignore[arg-type, return-value]
            reverse=True,
        )[:5]

        summary = {
            "user_id": user_id,
            "total_events": len(user_events),
            "event_type_counts": event_type_counts,
            "daily_counts": daily_counts,
            "top_sessions": top_sessions,
            "time_range_days": days,
        }

        _log.info(
            "[BehaviorLogger] Activity summary for %s (%d days): %d events",
            user_id,
            days,
            len(user_events),
        )

        return summary

    # ------------------------------------------------------------------
    # BOS-URI 路由支持 (通过 call 方法)
    # ------------------------------------------------------------------

    def _handle_log(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理 bos://memory/behavior/log"""
        event_type = params.get("event_type")
        event_data = params.get("event_data", {})
        session_id = params.get("session_id", "@Prime")
        user_id = params.get("user_id", "@Prime")

        if not event_type:
            return {"status": "error", "message": "event_type is required."}
        if not event_data:
            return {"status": "error", "message": "event_data cannot be empty."}

        try:
            event = self.log_event(event_type, event_data, session_id, user_id)
            return {"status": "success", "event": event.to_dict()}
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def _handle_query(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理 bos://memory/behavior/query"""
        events = self.query_events(
            event_type=params.get("event_type"),
            start_time=params.get("start_time"),
            end_time=params.get("end_time"),
            limit=params.get("limit", 100),
        )
        return {"status": "success", "count": len(events), "events": [e.to_dict() for e in events]}

    def _handle_summary(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理 bos://memory/behavior/summary"""
        user_id = params.get("user_id", "@Prime")
        days = params.get("days", 7)

        summary = self.get_user_activity_summary(user_id, days)
        return {"status": "success", "summary": summary}
