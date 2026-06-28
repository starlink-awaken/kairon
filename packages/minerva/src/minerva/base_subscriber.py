from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# BaseSubscriber ≝ Module
# 内涵 ≝ {BaseSubscriber, IKnowledgeSubscriber}
# 外延 ≝ {e | e ∈ Minerva ∧ implements(e, BaseSubscriber)}
# 功能 ⊢ {Base_Subscriber, Init_Subscriber, Validate_Subscriber}
# =============================================================================

"""
Knowledge Subscribers — 知识事件订阅者协议

定义订阅者接口，用于接收知识变更通知。
迁移自 SharedBrain D_Harvest/integration/subscribers/__init__.py
"""

import asyncio
import logging
from abc import ABC, abstractmethod

from minerva.events import KnowledgeEvent

_log = logging.getLogger(__name__)


# =============================================================================
# 订阅者协议
# =============================================================================


class IKnowledgeSubscriber(ABC):
    """
    知识事件订阅者接口

    所有订阅者必须实现此接口以接收知识变更事件。
    """

    @abstractmethod
    async def on_knowledge_created(self, event: KnowledgeEvent) -> None:
        """处理知识创建事件"""
        ...

    @abstractmethod
    async def on_knowledge_updated(self, event: KnowledgeEvent) -> None:
        """处理知识更新事件"""
        ...

    @abstractmethod
    async def on_knowledge_deleted(self, event: KnowledgeEvent) -> None:
        """处理知识删除事件"""
        ...

    @abstractmethod
    async def on_knowledge_batch(self, event: KnowledgeEvent) -> None:
        """处理批量知识事件"""
        ...

    @property
    @abstractmethod
    def subscriber_id(self) -> str:
        """返回订阅者唯一标识符"""
        ...

    async def on_event(self, event: KnowledgeEvent) -> None:
        """
        通用事件处理器（路由到具体方法）

        Args:
            event: 任意KnowledgeEvent实例
        """
        try:
            event_type = event.event_type

            if event_type == "knowledge_created":
                await self.on_knowledge_created(event)
            elif event_type == "knowledge_updated":
                await self.on_knowledge_updated(event)
            elif event_type == "knowledge_deleted":
                await self.on_knowledge_deleted(event)
            elif event_type == "knowledge_batch_created":
                await self.on_knowledge_batch(event)
            else:
                _log.warning(f"[{self.subscriber_id}] Unknown event type: {event_type}")

        except Exception as exc:  # noqa: BLE001
            _log.error(f"[{self.subscriber_id}] Failed to handle event {event.event_id}: {exc}", exc_info=True)
            raise


# =============================================================================
# 基础订阅者实现
# =============================================================================


class BaseSubscriber(IKnowledgeSubscriber):
    """
    基础订阅者实现

    提供默认的空实现，子类可选择性重写。
    """

    def __init__(self, subscriber_id: str | None = None) -> None:
        self._id: str = subscriber_id or self.__class__.__name__

    @property
    def subscriber_id(self) -> str:
        return self._id

    async def on_knowledge_created(self, event: KnowledgeEvent) -> None:
        """默认：记录日志"""
        _log.debug(f"[{self.subscriber_id}] Knowledge created: {event.payload.get('uri')}")

    async def on_knowledge_updated(self, event: KnowledgeEvent) -> None:
        """默认：记录日志"""
        _log.debug(f"[{self.subscriber_id}] Knowledge updated: {event.payload.get('uri')}")

    async def on_knowledge_deleted(self, event: KnowledgeEvent) -> None:
        """默认：记录日志"""
        _log.debug(f"[{self.subscriber_id}] Knowledge deleted: {event.payload.get('uri')}")

    async def on_knowledge_batch(self, event: KnowledgeEvent) -> None:
        """默认：分解为单独事件处理"""
        items = event.payload.get("items", [])
        _log.debug(f"[{self.subscriber_id}] Batch of {len(items)} items received")


# =============================================================================
# 订阅者注册表
# =============================================================================


class SubscriberRegistry:
    """
    订阅者注册表

    管理所有活跃的订阅者，支持添加、移除和通知。
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, IKnowledgeSubscriber] = {}
        self._lock = asyncio.Lock()

    def register(self, subscriber: IKnowledgeSubscriber) -> None:
        """
        注册订阅者

        Args:
            subscriber: 订阅者实例

        Raises:
            ValueError: 如果subscriber_id已存在
        """
        sub_id = subscriber.subscriber_id
        if sub_id in self._subscribers:
            raise ValueError(f"Subscriber {sub_id} already registered")

        self._subscribers[sub_id] = subscriber
        _log.info(f"Registered subscriber: {sub_id}")

    def unregister(self, subscriber_id: str) -> IKnowledgeSubscriber | None:
        """
        注销订阅者

        Args:
            subscriber_id: 订阅者ID

        Returns:
            被注销的订阅者，不存在则返回None
        """
        subscriber = self._subscribers.pop(subscriber_id, None)
        if subscriber:
            _log.info(f"Unregistered subscriber: {subscriber_id}")
        return subscriber

    def get_subscriber(self, subscriber_id: str) -> IKnowledgeSubscriber | None:
        """获取指定订阅者"""
        return self._subscribers.get(subscriber_id)

    def list_subscribers(self) -> list[str]:
        """返回所有订阅者ID列表"""
        return list(self._subscribers.keys())

    @property
    def count(self) -> int:
        """返回订阅者数量"""
        return len(self._subscribers)


__all__ = [
    "IKnowledgeSubscriber",
    "BaseSubscriber",
    "SubscriberRegistry",
]
