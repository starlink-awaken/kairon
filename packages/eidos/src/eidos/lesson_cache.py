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
# Lesson Cache ≡ Module
# 内涵 ≝ {Lesson, Cache}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, LessonCache)}
# 功能 ⊢ {Lesson_Cache, Init_Lesson, Validate_Cache}
# =============================================================================

# ---
# domain: D-Memory
# layer: organ
# status: active
# ---

import logging
import uuid
from typing import Any

from eidos.models import Lesson  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# L2 LessonCache (BOS-URI backed)
# ---------------------------------------------------------------------------


class LessonCache:
    """
    L2教训缓存 - 通过BOS-URI持久化

    遵循LAYER_AUTHORITY:
    - 不直接import nucleus组件
    - 通过BOS-URI协议通信: bos://memory/lesson/{id}
    """

    def __init__(self, ttl: int = 86400) -> None:
        """
        初始化L2教训缓存

        Args:
            ttl: 生存时间(秒), 默认24小时
        """
        self.ttl = ttl
        self._local_cache: dict[str, Lesson] = {}  # 本地热缓存
        self._uri_resolver = None  # 延迟初始化

    def _get_resolver(self) -> Any:
        """获取BOS-URI解析器(延迟初始化)"""
        if self._uri_resolver is None:
            # 动态导入避免违反LAYER_AUTHORITY
            from nucleus.Z_Microkernel.organs.uri_router import get_router  # type: ignore[import-not-found]

            self._uri_resolver = get_router()
        return self._uri_resolver

    async def get(self, query: str) -> Lesson | None:
        """
        获取教训

        Args:
            query: 查询字符串

        Returns:
            Lesson对象或None
        """
        # 先查本地热缓存
        lesson = self._local_cache.get(query)
        if lesson:
            lesson.access_count += 1
            return lesson

        # 通过BOS-URI查询持久化存储
        try:
            resolver = self._get_resolver()
            # 添加action到URI路径中
            uri = f"bos://memory/lesson/{query}?action=read"
            handler = await resolver.resolve(uri)

            if handler:
                result = await handler(uri) if callable(handler) else handler
                if result and result.get("status") == "ok":
                    data = result.get("data")
                    if data:
                        lesson = Lesson.from_dict(data)
                        self._local_cache[query] = lesson
                        return lesson
        except (AttributeError, ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            _log.warning(f"L2 LessonCache BOS-URI query failed: {exc}")

        return None

    async def set(self, lesson: Lesson) -> bool:
        """
        存储教训

        Args:
            lesson: Lesson对象

        Returns:
            是否成功
        """
        # 更新本地缓存
        self._local_cache[lesson.query] = lesson

        # 通过BOS-URI持久化 (简化实现: 仅本地缓存)
        # Stub: BOS-URI write operation deferred
        _log.debug(f"[LessonCache] Stored lesson locally: {lesson.lesson_id}")
        return True

    async def extract_lesson_from_error(self, query: str, error: Exception, context: dict[str, Any]) -> Lesson:
        """
        从错误中提取教训 (op5: 失败原子化)

        Args:
            query: 原始查询
            error: 异常对象
            context: 上下文信息

        Returns:
            提取的Lesson对象
        """
        # ErrorAtomizer integration (op5) — currently produces minimal placeholders.
        lesson = Lesson(
            lesson_id=str(uuid.uuid4())[:8],
            query=query,
            failure_pattern={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
            },
            solution={
                "avoidance_strategy": "",  # populated when ErrorAtomizer is wired (op5)
                "workaround": "",
            },
        )
        await self.set(lesson)
        return lesson
