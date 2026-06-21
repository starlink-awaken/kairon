from __future__ import annotations

import logging

_log = logging.getLogger(__name__)
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
# Subscriber Metrics ≡ Module
# 内涵 ≝ {Subscriber, Metrics}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, SubscriberMetrics)}
# 功能 ⊢ {Subscriber_Metrics, Init_Subscriber, Validate_Metrics}
# =============================================================================

# ---
# domain: D-Harvest
# layer: integration.subscribers
# status: active
# version: 1.0.0
# ---
"""
FactGraphSubscriber 监控指标集成

将 FactGraphSubscriber 的批处理统计暴露到 Prometheus监控系统。
"""

import logging

from minerva.observability.metrics_collector import get_global_collector

_logger = logging.getLogger(__name__)


class FactGraphSubscriberMetrics:
    """FactGraphSubscriber 监控指标发布器"""

    # 指标名称常量
    BUFFER_SIZE = "factgraph_subscriber_buffer_size"
    TOTAL_IMPORTED = "factgraph_subscriber_imported_total"
    TOTAL_ERRORS = "factgraph_subscriber_errors_total"
    FLUSH_DURATION = "factgraph_subscriber_flush_duration_seconds"
    FLUSH_SIZE = "factgraph_subscriber_flush_size"

    def __init__(self, subscriber_id: str) -> None:
        self._collector = get_global_collector()
        self._subscriber_id = subscriber_id

    def update_buffer_size(self, buffer_size: int) -> None:
        """更新缓冲区大小指标"""
        try:
            self._collector.set(
                self.BUFFER_SIZE,
                float(buffer_size),
                labels={"component": "factgraph_subscriber", "subscriber_id": self._subscriber_id},
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            _log.warning(f"Failed to update buffer size metric: {exc}")

    def record_flush(
        self,
        imported_count: int,
        error_count: int,
        duration_seconds: float,
        triggered_by: str,
    ) -> None:
        """
        记录批次刷新统计

        Args:
            imported_count: 成功导入的条目数
            error_count: 失败的条目数
            duration_seconds: 刷新耗时
            triggered_by: 触发原因 ("size" 或 "timeout")
        """
        try:
            total = imported_count + error_count

            # 记录刷新大小
            self._collector.observe(
                self.FLUSH_SIZE,
                float(total),
                labels={
                    "component": "factgraph_subscriber",
                    "subscriber_id": self._subscriber_id,
                    "triggered_by": triggered_by,
                },
            )

            # 记录刷新耗时
            self._collector.observe(
                self.FLUSH_DURATION,
                duration_seconds,
                labels={
                    "component": "factgraph_subscriber",
                    "subscriber_id": self._subscriber_id,
                    "triggered_by": triggered_by,
                },
            )

            # 更新计数器
            if imported_count > 0:
                self._collector.inc(
                    self.TOTAL_IMPORTED,
                    float(imported_count),
                    labels={
                        "component": "factgraph_subscriber",
                        "subscriber_id": self._subscriber_id,
                        "status": "success",
                    },
                )

            if error_count > 0:
                self._collector.inc(
                    self.TOTAL_ERRORS,
                    float(error_count),
                    labels={
                        "component": "factgraph_subscriber",
                        "subscriber_id": self._subscriber_id,
                        "status": "failed",
                    },
                )

            _logger.debug(
                f"[{self._subscriber_id}] Flush metrics: "
                f"imported={imported_count}, errors={error_count}, "
                f"duration={duration_seconds:.3f}s, triggered_by={triggered_by}"
            )

        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            _logger.warning(f"[{self._subscriber_id}] Failed to record flush metrics: {exc}")


# 全局单例字典（每个订阅者一个实例）
_subscriber_metrics: dict[str, FactGraphSubscriberMetrics] = {}


def get_subscriber_metrics(subscriber_id: str) -> FactGraphSubscriberMetrics:
    """获取订阅者指标发布器（每个订阅者一个实例）"""
    global _subscriber_metrics
    if subscriber_id not in _subscriber_metrics:
        _subscriber_metrics[subscriber_id] = FactGraphSubscriberMetrics(subscriber_id)
    return _subscriber_metrics[subscriber_id]


__all__ = ["FactGraphSubscriberMetrics", "get_subscriber_metrics"]
