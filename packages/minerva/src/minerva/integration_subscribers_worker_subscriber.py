from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Worker Subscriber ≡ Worker
# 内涵 ≝ {Worker, Subscriber}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, WorkerSubscriber)}
# 功能 ⊢ {Worker_Subscriber, Init_Worker, Validate_Subscriber}
# =============================================================================

# ---
# domain: D-Harvest
# layer: integration
# status: active
# version: 1.0.0
# ---
"""
Worker Subscriber — 通知Workers有新知识可用

订阅知识变更事件，触发Workers缓存失效。
使用防抖机制避免频繁通知。
"""

import asyncio
import logging
import time
from typing import Any

from minerva.base_subscriber import BaseSubscriber
from minerva.events import KnowledgeEvent

_log = logging.getLogger(__name__)

# =============================================================================
# 缓存失效通知
# =============================================================================


class CacheInvalidationNotifier:
    """
    缓存失效通知器

    负责向所有Workers发送缓存失效信号。
    """

    def __init__(self, debounce_seconds: float = 5.0) -> None:
        """
        初始化通知器

        Args:
            debounce_seconds: 防抖时间（秒），在此时间内的多次变更合并为一次通知
        """
        self._debounce_seconds = debounce_seconds
        self._last_notification = 0.0
        self._pending = False
        self._lock = asyncio.Lock()
        self._notify_task: asyncio.Task | None = None

    async def notify(self, force: bool = False) -> None:
        """
        发送缓存失效通知

        Args:
            force: 是否强制发送（忽略防抖）
        """
        async with self._lock:
            now = time.time()

            # 检查防抖
            if not force and (now - self._last_notification) < self._debounce_seconds:
                self._pending = True
                _log.debug("Debouncing cache invalidation notification")
                return

            # 重置状态
            self._pending = False
            self._last_notification = now

        # 执行通知
        await self._send_notification()

    async def _send_notification(self) -> None:
        """
        执行实际的通知发送

        这里通过共享 EventBus 发送缓存失效事件。
        Workers订阅此事件来失效其本地缓存。

        使用 :data:`kairon_lib.events.get_global_event_bus` 而非直接
        importlib 路径，避免对 D-Execution 的硬依赖。
        """
        try:
            from kairon_lib.events import get_global_event_bus, make_event

            bus = get_global_event_bus()
            if bus is None:
                _log.debug("Global EventBus not yet registered — skipping cache invalidation")
                return

            event = make_event(
                event_type="knowledge_cache_invalidated",
                source="knowledge_sync",
                payload={
                    "timestamp": time.time(),
                    "reason": "new_knowledge_available",
                },
            )
            bus.publish(event)

            _log.info("Sent cache invalidation notification to workers")

        except ImportError as exc:
            _log.warning("kairon_lib.events unavailable for cache invalidation: %s", exc)

    async def flush_pending(self) -> None:
        """刷新待处理的通知"""
        async with self._lock:
            if self._pending:
                self._pending = False
                self._last_notification = time.time()

        await self._send_notification()


# =============================================================================
# Workers订阅者
# =============================================================================


class WorkerSubscriber(BaseSubscriber):
    """
    Workers订阅者

    监听知识变更事件，触发Workers缓存失效。

    使用示例：
        subscriber = WorkerSubscriber()
        bus.subscribe(subscriber)
    """

    def __init__(
        self,
        debounce_seconds: float = 5.0,
        notify_on_batch: bool = False,
    ) -> None:
        """
        初始化订阅者

        Args:
            debounce_seconds: 防抖时间（秒）
            notify_on_batch: 是否在批量事件时也通知
        """
        super().__init__("WorkerSubscriber")
        self._notifier = CacheInvalidationNotifier(debounce_seconds)
        self._notify_on_batch = notify_on_batch

        # 统计
        self._events_received = 0
        self._notifications_sent = 0

    async def on_knowledge_created(self, event: KnowledgeEvent) -> None:
        """处理知识创建事件 - 触发缓存失效"""
        self._events_received += 1
        await self._notifier.notify()
        _log.debug(f"[{self.subscriber_id}] Knowledge created event received: {event.payload.get('uri')}")

    async def on_knowledge_updated(self, event: KnowledgeEvent) -> None:
        """处理知识更新事件 - 触发缓存失效"""
        self._events_received += 1
        await self._notifier.notify()
        _log.debug(f"[{self.subscriber_id}] Knowledge updated event received: {event.payload.get('uri')}")

    async def on_knowledge_deleted(self, event: KnowledgeEvent) -> None:
        """处理知识删除事件 - 触发缓存失效"""
        self._events_received += 1
        await self._notifier.notify(force=True)  # 删除事件强制通知
        _log.debug(f"[{self.subscriber_id}] Knowledge deleted event received: {event.payload.get('uri')}")

    async def on_knowledge_batch(self, event: KnowledgeEvent) -> None:
        """处理批量事件 - 可选通知"""
        self._events_received += event.payload.get("count", 0)

        if self._notify_on_batch:
            await self._notifier.notify(force=True)
            _log.debug(f"[{self.subscriber_id}] Batch event received, forcing notification")
        else:
            _log.debug(
                f"[{self.subscriber_id}] Batch event received ({event.payload.get('count')} items), notification pending"
            )

    # -------------------------------------------------------------------------
    # 公共API
    # -------------------------------------------------------------------------

    async def flush(self) -> None:
        """刷新待处理的通知"""
        await self._notifier.flush_pending()
        self._notifications_sent += 1

    def get_stats(self) -> dict[str, Any]:
        """获取订阅者统计信息"""
        return {
            "subscriber_id": self.subscriber_id,
            "events_received": self._events_received,
            "notifications_sent": self._notifications_sent,
            "pending_notification": self._notifier._pending,
            "debounce_seconds": self._notifier._debounce_seconds,
        }


__all__ = ["WorkerSubscriber", "CacheInvalidationNotifier"]
