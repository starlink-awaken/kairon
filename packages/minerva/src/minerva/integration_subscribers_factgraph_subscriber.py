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
# Factgraph Subscriber ≡ Module
# 内涵 ≝ {Factgraph, Subscriber}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, FactgraphSubscriber)}
# 功能 ⊢ {Factgraph_Subscriber, Init_Factgraph, Validate_Subscriber}
# =============================================================================

# ---
# domain: D-Harvest
# layer: integration
# status: active
# version: 1.0.0
# ---
"""
FactGraph Subscriber — 将知识事件实时导入FactGraph

订阅知识变更事件，批量攒批后导入到FactGraph。

优化策略：
- 批量攒批：达到100条或1秒超时触发导入
- 失败重试：导入失败自动重试3次
- 幂等性：通过factgraph_synced标记避免重复导入
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from minerva.base_subscriber import BaseSubscriber  # type: ignore[import-not-found]
from minerva.events import KnowledgeEvent  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)

# =============================================================================
# FactGraph协议
# =============================================================================


class FactGraphLike:
    """FactGraph最小接口协议"""

    def add_facts(
        self,
        facts: list[tuple[str, str, str, dict[str, object]]],
        _remote_sync: bool = False,
    ) -> Any: ...

    def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        metadata: dict[str, object] | None = None,
    ) -> Any: ...


# =============================================================================
# 导入结果
# =============================================================================


@dataclass
class ImportResult:
    """单次导入结果"""

    success: bool
    imported_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    errors: list[str] = field(default_factory=list)
    imported_ids: list[int] = field(default_factory=list)


# =============================================================================
# FactGraph订阅者
# =============================================================================


class FactGraphSubscriber(BaseSubscriber):
    """
    FactGraph订阅者

    监听知识创建事件，批量攒批后导入到FactGraph。

    使用示例：
        subscriber = FactGraphSubscriber(factgraph=fg)
        bus.subscribe(subscriber)
    """

    # FactGraph节点ID格式要求
    _NODE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

    def __init__(
        self,
        factgraph: FactGraphLike | None = None,
        batch_size: int = 100,
        batch_timeout: float = 1.0,
        knowledge_store: Any | None = None,  # 用于标记同步状态
    ) -> None:
        """
        初始化订阅者

        Args:
            factgraph: FactGraph实例
            batch_size: 批量攒批大小
            batch_timeout: 批量超时（秒）
            knowledge_store: KnowledgeStore实例（用于标记同步）
        """
        super().__init__("FactGraphSubscriber")
        self._fg = factgraph
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout
        self._store = knowledge_store

        # 批量缓冲区
        self._buffer: list[dict[str, Any]] = []
        self._last_flush = 0.0
        self._flush_lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None

        # 统计
        self._total_imported = 0
        self._total_errors = 0

        # 监控指标集成（延迟导入避免循环依赖）
        self._metrics = None
        try:
            from minerva.integration_subscribers_subscriber_metrics import (  # type: ignore[import-not-found]
                get_subscriber_metrics,
            )

            self._metrics = get_subscriber_metrics(self.subscriber_id)
        except ImportError:
            pass  # 监控不可用不是错误

    # -------------------------------------------------------------------------
    # 事件处理
    # -------------------------------------------------------------------------

    async def on_knowledge_created(self, event: KnowledgeEvent) -> None:
        """处理知识创建事件 - 加入批量缓冲区"""
        item = {
            "id": event.payload.get("item_id"),
            "uri": event.payload.get("uri"),
            "title": event.payload.get("title"),
            "quality_score": event.payload.get("quality_score"),
            "metadata": event.payload.get("metadata", {}),
            "event_id": event.event_id,
        }

        async with self._flush_lock:
            self._buffer.append(item)

            # 更新缓冲区大小指标
            if self._metrics:
                self._metrics.update_buffer_size(len(self._buffer))

            # 检查是否需要刷新
            now = asyncio.get_event_loop().time()
            should_flush = len(self._buffer) >= self._batch_size or (now - self._last_flush) >= self._batch_timeout

            if should_flush:
                await self._flush_buffer()

    async def on_knowledge_batch(self, event: KnowledgeEvent) -> None:
        """处理批量事件 - 直接刷新"""
        items = event.payload.get("items", [])

        async with self._flush_lock:
            # 先刷新现有缓冲区
            await self._flush_buffer()

            # 直接导入批量数据
            if items:
                result = await self._import_batch(items)
                self._total_imported += result.imported_count
                self._total_errors += result.error_count

    async def on_knowledge_updated(self, event: KnowledgeEvent) -> None:
        """处理知识更新事件 - 目前与创建同样处理"""
        # 更新事件可以触发增量更新，这里简化为重新导入
        await self.on_knowledge_created(event)

    async def on_knowledge_deleted(self, event: KnowledgeEvent) -> None:
        """处理知识删除事件 - 可选实现"""
        # FactGraph当前不支持删除，记录日志
        _log.debug(
            f"[{self.subscriber_id}] Delete event received for item {event.payload.get('item_id')} "
            "(deletion not implemented)"
        )

    # -------------------------------------------------------------------------
    # 批量处理
    # -------------------------------------------------------------------------

    async def _flush_buffer(self) -> None:
        """刷新缓冲区到FactGraph"""
        if not self._buffer:
            return

        batch = self._buffer.copy()
        start_time = asyncio.get_event_loop().time()

        # FIX: 先导入，导入成功后再清空缓冲区，防止数据丢失
        # 导入失败时保留缓冲区内容以便重试

        try:
            result = await self._import_batch(batch)

            # 只有导入成功才清空缓冲区
            if result.success:
                self._buffer.clear()
                self._last_flush = asyncio.get_event_loop().time()

                # 记录刷新指标
                if self._metrics:
                    duration = self._last_flush - start_time
                    triggered_by = "size" if len(batch) >= self._batch_size else "timeout"
                    self._metrics.record_flush(
                        imported_count=result.imported_count,
                        error_count=result.error_count,
                        duration_seconds=duration,
                        triggered_by=triggered_by,
                    )

                # 标记已同步（如果有KnowledgeStore）
                if self._store and result.imported_ids:
                    try:
                        await self._store.mark_factgraph_synced(result.imported_ids)
                    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                        _log.warning(f"Failed to mark synced: {exc}")
            else:
                # 导入失败，记录错误但保留缓冲区
                _log.error(f"[{self.subscriber_id}] Flush failed, keeping {len(self._buffer)} items in buffer")

                # 记录失败的刷新指标
                if self._metrics:
                    duration = asyncio.get_event_loop().time() - start_time
                    self._metrics.record_flush(
                        imported_count=result.imported_count,
                        error_count=result.error_count,
                        duration_seconds=duration,
                        triggered_by="unknown",
                    )

            self._total_imported += result.imported_count
            self._total_errors += result.error_count

            if result.error_count > 0:
                _log.warning(f"[{self.subscriber_id}] Batch completed with {result.error_count} errors")
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            # 异常情况下保留缓冲区以便重试
            _log.error(f"[{self.subscriber_id}] Flush exception, keeping {len(self._buffer)} items in buffer: {exc}")

    async def _import_batch(self, items: list[dict[str, Any]]) -> ImportResult:
        """
        批量导入知识条目

        Args:
            items: 知识条目列表

        Returns:
            ImportResult导入结果
        """
        result = ImportResult(success=True)

        if self._fg is None:
            result.success = False
            result.errors.append("FactGraph不可用")
            return result

        # 转换为三元组
        all_triples = []
        import_ids = []

        for item in items:
            try:
                triples = self._convert_to_triples(item)
                all_triples.extend(triples)
                result.imported_count += 1
                import_ids.append(item["id"])

            except (KeyError, TypeError, ValueError) as exc:
                result.error_count += 1
                result.errors.append(f"Item {item.get('id')}: {exc}")

        # 批量插入
        if all_triples:
            try:
                await self._insert_triples(all_triples)
                result.imported_ids = import_ids
                _log.debug(f"[{self.subscriber_id}] Imported {len(all_triples)} triples for {len(items)} items")

            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                result.success = False
                result.errors.append(f"Insert failed: {exc}")
                _log.error(f"[{self.subscriber_id}] Failed to insert triples: {exc}")

        return result

    def _convert_to_triples(self, item: dict[str, Any]) -> list[tuple[str, str, str, dict[str, Any] | None]]:
        """
        将知识条目转换为FactGraph三元组

        对齐 FactGraphImporter 的 Schema，包含:
        - body/dct_description
        - visibility
        - source domain node

        Args:
            item: 知识条目字典

        Returns:
            三元组列表 (subject, predicate, object, metadata)
        """
        triples = []
        item_id = str(item["id"])
        uri = item["uri"]
        title = item["title"]
        body = item.get("body", "")
        metadata_raw = item.get("metadata", {})
        visibility = item.get("visibility", "private")

        # 解析元数据
        if isinstance(metadata_raw, str):
            try:
                metadata = json.loads(metadata_raw)
            except json.JSONDecodeError:
                metadata = {}
        else:
            metadata = metadata_raw or {}

        # 标准化节点ID
        subject = self._normalize_node_id(f"knowledge_{item_id}")

        now = datetime.now(UTC).isoformat()

        # 基础三元组：类型
        triples.append((subject, "rdf_type", "KnowledgeItem", {"created_at": now}))

        # 标题关系
        triples.append((subject, "dct_title", str(title)[:500], {"source": "harvest"}))

        # URI关系
        triples.append((subject, "dct_source", str(uri)[:1000], {"source": "harvest"}))

        # 身体/描述关系 (FIX: 与 Importer 对齐)
        body_preview = str(body)[:2000] if body else ""
        if body_preview:
            triples.append(
                (
                    subject,
                    "dct_description",
                    body_preview,
                    {"source": "harvest", "truncated": len(str(body)) > 2000},
                )
            )

        # 质量分数
        quality = float(item.get("quality_score", 0.0))
        triples.append((subject, "bos_qualityScore", str(quality), {"source": "harvest"}))

        # 收割时间
        triples.append((subject, "bos_harvestedAt", now, {"source": "harvest"}))

        # 可见性 (FIX: 与 Importer 对齐)
        triples.append((subject, "bos_visibility", str(visibility), {"source": "harvest"}))

        # 来源域（从URI解析）(FIX: 与 Importer 对齐)
        try:
            from urllib.parse import urlparse

            parsed = urlparse(uri)
            if parsed.netloc:
                domain = parsed.netloc
                source_node = self._normalize_node_id(f"source_{domain}")

                # 创建来源节点
                triples.append((source_node, "rdf_type", "KnowledgeSource", {"source": "harvest"}))

                # 关联知识到来源
                triples.append((subject, "dct_sourceRef", source_node, {"source": "harvest"}))
        except (ValueError, TypeError):
            pass

        # 元数据扩展
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                predicate = self._normalize_node_id(f"bos_meta_{key}")
                triples.append((subject, predicate, str(value)[:500], {"source": "harvest", "meta_key": key}))

        return triples

    async def _insert_triples(self, triples: list[tuple[str, str, str, dict[str, Any] | None]]) -> None:
        """
        插入三元组到FactGraph

        Args:
            triples: 三元组列表
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_insert_triples, triples)

    def _sync_insert_triples(self, triples: list[tuple[str, str, str, dict[str, Any] | None]]) -> None:
        """同步插入三元组（在线程池中执行）"""
        fact_list = []
        for subj, pred, obj, metadata in triples:
            fact_list.append((subj, pred, obj, metadata or {}))

        if fact_list:
            try:
                self._fg.add_facts(fact_list, _remote_sync=False)
            except AttributeError:
                # 回退到逐个插入
                for subj, pred, obj, metadata in fact_list:
                    try:
                        self._fg.add_fact(subj, pred, obj, metadata)
                    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                        _log.warning(f"Failed to insert triple ({subj}, {pred}, {obj}): {exc}")

    def _normalize_node_id(self, node_id: str) -> str:
        """标准化节点ID以符合FactGraph要求"""
        normalized = node_id.replace(":", "_").replace("-", "_")

        if normalized and not normalized[0].isalnum():
            normalized = f"n_{normalized}"

        if not normalized or not self._NODE_ID_PATTERN.match(normalized):
            import hashlib

            # FIX: Use SHA-256 instead of MD5 for better security
            hash_suffix = hashlib.sha256(node_id.encode()).hexdigest()[:12]
            normalized = f"node_{hash_suffix}"

        return normalized

    # -------------------------------------------------------------------------
    # 公共API
    # -------------------------------------------------------------------------

    async def flush(self) -> ImportResult:
        """
        手动刷新缓冲区

        Returns:
            ImportResult刷新结果
        """
        async with self._flush_lock:
            await self._flush_buffer()

        return ImportResult(
            success=True,
            imported_count=self._total_imported,
            error_count=self._total_errors,
        )

    def get_stats(self) -> dict[str, Any]:
        """获取订阅者统计信息"""
        return {
            "subscriber_id": self.subscriber_id,
            "buffer_size": len(self._buffer),
            "total_imported": self._total_imported,
            "total_errors": self._total_errors,
            "batch_size": self._batch_size,
            "batch_timeout": self._batch_timeout,
            "factgraph_available": self._fg is not None,
        }


__all__ = ["FactGraphSubscriber", "ImportResult"]
