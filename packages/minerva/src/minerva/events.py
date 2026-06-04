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
# Events ≝ Module
# 内涵 ≝ {Events}
# 外延 ≝ {e | e ∈ Minerva ∧ implements(e, Events)}
# 功能 ⊢ {Init_Events, Execute_Events, Validate_Events}
# =============================================================================

"""
Knowledge Sync Events — 知识同步事件定义

定义知识变更事件类型，用于实时同步架构。
迁移自 SharedBrain D_Harvest/integration/events.py
"""

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

# =============================================================================
# 事件类型常量
# =============================================================================


class KnowledgeEventType:
    """知识事件类型常量"""

    CREATED = "knowledge_created"
    UPDATED = "knowledge_updated"
    DELETED = "knowledge_deleted"
    BATCH_CREATED = "knowledge_batch_created"


# =============================================================================
# BOSEvent 降级定义 (知识领域专属，字段含默认值)
# =============================================================================
# KnowledgeEvent 需要字段默认值来支持便捷子类化（不传递所有父类参数）。
# 共享 kairon_lib.events.BOSEvent 所有字段均为必需，因此此处定义为本地副本。
# 两个 BOSEvent 在结构上兼容（相同的字段名和类型），可通过转换函数互通。


@dataclass
class BOSEvent:
    """知识领域 BOSEvent — 字段含默认值以支持便捷子类化。"""

    event_type: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid4()))


# =============================================================================
# 知识同步事件
# =============================================================================


@dataclass
class KnowledgeEvent(BOSEvent):
    """
    知识变更事件基类

    Attributes:
        event_type: 事件类型（KnowledgeEventType常量）
        source: 事件源（固定为"knowledge_store"）
        payload: 事件载荷，包含知识详情
        timestamp: 事件时间戳
        event_id: 事件唯一ID
    """

    event_type: str = "knowledge_event"
    source: str = "knowledge_store"


@dataclass
class KnowledgeCreatedEvent(KnowledgeEvent):
    """知识创建事件"""

    event_type: str = KnowledgeEventType.CREATED

    def __init__(
        self,
        item_id: int,
        uri: str,
        title: str,
        quality_score: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            event_type=KnowledgeEventType.CREATED,
            payload={
                "item_id": item_id,
                "uri": uri,
                "title": title,
                "quality_score": quality_score,
                "metadata": metadata or {},
            },
        )


@dataclass
class KnowledgeUpdatedEvent(KnowledgeEvent):
    """知识更新事件"""

    event_type: str = KnowledgeEventType.UPDATED

    def __init__(
        self,
        item_id: int,
        uri: str,
        title: str,
        quality_score: float,
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            event_type=KnowledgeEventType.UPDATED,
            payload={
                "item_id": item_id,
                "uri": uri,
                "title": title,
                "quality_score": quality_score,
                "changes": changes or {},
                "metadata": metadata or {},
            },
        )


@dataclass
class KnowledgeDeletedEvent(KnowledgeEvent):
    """知识删除事件"""

    event_type: str = KnowledgeEventType.DELETED

    def __init__(
        self,
        item_id: int,
        uri: str,
    ) -> None:
        super().__init__(
            event_type=KnowledgeEventType.DELETED,
            payload={
                "item_id": item_id,
                "uri": uri,
            },
        )


@dataclass
class KnowledgeBatchCreatedEvent(KnowledgeEvent):
    """批量知识创建事件"""

    event_type: str = KnowledgeEventType.BATCH_CREATED

    def __init__(
        self,
        items: list[dict[str, Any]],
    ) -> None:
        super().__init__(
            event_type=KnowledgeEventType.BATCH_CREATED,
            payload={
                "count": len(items),
                "items": items,
            },
        )


# =============================================================================
# 工厂函数
# =============================================================================


def create_knowledge_event(event_type: str, **kwargs: Any) -> KnowledgeEvent:
    """
    工厂函数：创建知识事件

    Args:
        event_type: 事件类型（KnowledgeEventType常量）
        **kwargs: 事件特定参数

    Returns:
        对应的KnowledgeEvent子类实例

    Raises:
        ValueError: 如果event_type无效
    """
    event_classes: dict[str, type[KnowledgeEvent]] = {
        KnowledgeEventType.CREATED: KnowledgeCreatedEvent,
        KnowledgeEventType.UPDATED: KnowledgeUpdatedEvent,
        KnowledgeEventType.DELETED: KnowledgeDeletedEvent,
        KnowledgeEventType.BATCH_CREATED: KnowledgeBatchCreatedEvent,
    }

    event_class = event_classes.get(event_type)
    if event_class is None:
        raise ValueError(f"Unknown event type: {event_type}")

    return event_class(**kwargs)  # type: ignore[call-arg]


__all__ = [
    "KnowledgeEvent",
    "KnowledgeEventType",
    "KnowledgeCreatedEvent",
    "KnowledgeUpdatedEvent",
    "KnowledgeDeletedEvent",
    "KnowledgeBatchCreatedEvent",
    "create_knowledge_event",
]
