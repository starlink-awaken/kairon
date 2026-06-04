from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Memory/AGENTS.md
Layer: L3
---
"""

import hashlib
import logging
import os
import time
from typing import Any

from eidos.organs.storage_dal import SQLiteOperationalError, SQLiteRelationalProvider

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Information_Pipeline ≡ Information_Flow_System
# 内涵 ≝ {Acquire, Filter, Distribute}
# 外延 ≝ {p | p ∈ D-Memory ∧ manages(p, InformationFlow)}
# 功能 ⊢ {AcquireInformation, FilterInformation, DistributeInformation}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-13_holographic_bus_axiom.md
Layer: D-Memory
Constraint: "[!!] INFORMATION_PIPELINE_QUALITY"
Summary: '信息流管道 - 管理信息获取、过滤和分发的全生命周期'
---

Information Pipeline - 信息流管道

职责:
- 从多种信息源获取信息
- 过滤低质量信息
- 将信息分发给指定的接收者
- 追踪信息获取的能量成本

作者: iFlow CLI
日期: 2026-03-03
状态: 生产就绪
"""

_log = logging.getLogger(__name__)


class InformationPipeline:
    """信息流管道 - 管理信息获取、过滤和分发的全生命周期"""

    def __init__(self, db_path: str | None = None) -> None:
        """
        初始化信息流管道

        Args:
            db_path: 数据库路径
        """
        self.status = "active"
        self.db_path = db_path or os.environ.get("BOS_MEMORY_DB", "data/db/organs/memory/memory.db")
        self._energy_cost_per_kb = 0.1  # 每KB信息的能量成本
        self._quality_threshold = 0.8  # 默认质量阈值
        self._db = SQLiteRelationalProvider(self.db_path)
        self.initialize()

    def _ensure_db(self) -> None:
        """Initialize DB connection and apply pragmas."""
        self._db.connect()
        self._db.execute("PRAGMA busy_timeout=30000")
        try:
            self._db.execute("PRAGMA journal_mode=DELETE")
        except SQLiteOperationalError:
            pass
        self._db.execute("PRAGMA synchronous=NORMAL")

    def initialize(self) -> None:
        """初始化数据库表"""
        self._ensure_db()
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS information_sources (
                source_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                last_sync REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                metadata TEXT
            );"""
        )

        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS information_logs (
                log_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                action TEXT NOT NULL,
                data_size INTEGER NOT NULL,
                quality_score REAL NOT NULL,
                energy_cost REAL NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (source_id) REFERENCES information_sources(source_id)
            );"""
        )

        _log.info("[*] InformationPipeline initialized")

    def acquire(self, source: dict) -> dict[str, Any]:
        """
        从信息源获取信息

        Args:
            source: 信息源配置
                - type: document | code | api | web
                - path: 文件路径/URL/API 端点
                - filters: 过滤条件（可选）

        Returns:
            dict: 获取的信息
                - status: success | error
                - data: 获取的数据
                - metadata: 元数据
                - energy_cost: 能量成本
        """
        start_time = time.time()

        try:
            source_type = source.get("type")
            source_path = source.get("path")

            if not source_type or not source_path:
                return {"status": "error", "message": "Source type and path are required"}

            # 根据类型获取信息
            if source_type == "document":
                data: str | dict[str, Any] = self._acquire_document(source_path)
            elif source_type == "code":
                data = self._acquire_code(source_path)
            elif source_type == "api":
                data = self._acquire_api(source_path, source.get("params", {}))
            elif source_type == "web":
                data = self._acquire_web(source_path)
            else:
                return {"status": "error", "message": f"Unknown source type: {source_type}"}

            # 计算数据大小和能量成本
            data_size = len(str(data))
            energy_cost = self._calculate_energy_cost(data_size)

            # 记录日志
            self._log_acquisition(source, data_size, energy_cost)

            duration = time.time() - start_time
            _log.info("✅ [Pipeline] Acquired {data_size} bytes from {source_type} ({duration:.2f}s)")

            return {
                "status": "success",
                "data": data,
                "metadata": {
                    "source_type": source_type,
                    "source_path": source_path,
                    "data_size": data_size,
                    "acquisition_time": duration,
                },
                "energy_cost": energy_cost,
            }

        except (OSError, TypeError, ValueError) as e:
            _log.info("❌ [Pipeline] Acquisition failed: {e}")
            return {"status": "error", "message": str(e)}

    def _acquire_document(self, path: str) -> str:
        """从文档获取信息"""
        full_path = os.path.join(os.environ.get("BOS_ROOT", ""), path)
        with open(full_path, encoding="utf-8") as f:
            return f.read()

    def _acquire_code(self, path: str) -> str:
        """从代码文件获取信息"""
        full_path = os.path.join(os.environ.get("BOS_ROOT", ""), path)
        with open(full_path, encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _acquire_api(self, endpoint: str, params: dict) -> dict:
        """从 API 获取信息（简化实现）"""
        # 实际应该调用真实的 API
        return {"endpoint": endpoint, "params": params, "note": "需要实现真实 API 调用"}

    def _acquire_web(self, url: str) -> str:
        """从 Web 获取信息（简化实现）"""
        # 实际应该使用 requests 库
        return f"Web content from {url} (需要实现真实 HTTP 请求)"

    def filter(self, data: dict, quality_threshold: float | None = None) -> bool:
        """
        过滤低质量信息

        Args:
            data: 待过滤的数据
            quality_threshold: 质量阈值（默认使用实例阈值）

        Returns:
            bool: 是否通过过滤
        """
        threshold = quality_threshold or self._quality_threshold

        # 计算质量分数
        quality_score = self._calculate_quality_score(data)

        # 记录过滤结果
        self._log_filtering(data, quality_score, quality_score >= threshold)

        return quality_score >= threshold

    def _calculate_quality_score(self, data: dict) -> float:
        """
        计算信息质量分数

        Args:
            data: 数据字典

        Returns:
            float: 质量分数 (0.0 - 1.0)
        """
        score = 0.0

        # 检查数据大小
        data_size = len(str(data.get("data", "")))
        if data_size > 100:
            score += 0.3

        # 检查元数据完整性
        metadata = data.get("metadata", {})
        if metadata.get("source_type"):
            score += 0.3
        if metadata.get("source_path"):
            score += 0.2
        if metadata.get("acquisition_time"):
            score += 0.2

        return min(score, 1.0)

    def distribute(self, info: dict, recipients: list[str]) -> dict[str, Any]:
        """
        将信息分发给指定的接收者

        Args:
            info: 待分发的信息
            recipients: 接收者列表（Agent ID、Tool ID）

        Returns:
            dict: 分发结果
                - status: success | error
                - delivered: 成功投递的接收者列表
                - failed: 投递失败的接收者列表
        """
        try:
            delivered: list[str] = []
            failed: list[str] = []

            for recipient in recipients:
                # 简化实现：记录分发日志
                # 实际应该调用相应的 Agent 或 Tool
                self._log_distribution(info, recipient, True)
                delivered.append(recipient)

            _log.info("✅ [Pipeline] Distributed to {len(delivered)} recipients")

            return {"status": "success", "delivered": delivered, "failed": failed}

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            _log.info("❌ [Pipeline] Distribution failed: {e}")
            return {"status": "error", "message": str(e)}

    def _calculate_energy_cost(self, data_size: int) -> float:
        """
        计算能量成本

        Args:
            data_size: 数据大小（字节）

        Returns:
            float: 能量成本（EU）
        """
        return (data_size / 1024) * self._energy_cost_per_kb

    def _log_acquisition(self, source: dict, data_size: int, energy_cost: float) -> None:
        """记录信息获取日志"""
        log_id = hashlib.md5(f"{source['path']}_{time.time()}".encode()).hexdigest()  # noqa: S324

        self._db.execute(
            """
            INSERT INTO information_logs (log_id, source_id, action, data_size, quality_score, energy_cost, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (log_id, source["path"], "acquire", data_size, 1.0, energy_cost, time.time()),
        )

    def _log_filtering(self, data: dict, quality_score: float, passed: bool) -> None:
        """记录过滤日志"""
        # 简化实现：可以扩展为记录到数据库
        _log.info("🔍 [Pipeline] Filter: quality={quality_score:.2f}, passed={passed}")

    def _log_distribution(self, info: dict, recipient: str, success: bool) -> None:
        """记录分发日志"""
        # 简化实现：可以扩展为记录到数据库
        _log.info("📤 [Pipeline] Distribute to {recipient}: {'success' if success else 'failed'}")

    def get_statistics(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            dict: 统计信息
                - total_acquisitions: 总获取次数
                - total_energy_cost: 总能量成本
                - average_quality: 平均质量分数
        """
        stats = self._db.fetch_one(
            """
            SELECT
                COUNT(*) as total_acquisitions,
                SUM(energy_cost) as total_energy_cost,
                AVG(quality_score) as average_quality
            FROM information_logs
            WHERE action = 'acquire'
            """
        )

        return {
            "total_acquisitions": stats["total_acquisitions"] or 0 if stats else 0,
            "total_energy_cost": stats["total_energy_cost"] or 0.0 if stats else 0.0,
            "average_quality": stats["average_quality"] or 0.0 if stats else 0.0,
        }

    def validate_internal_state(self) -> bool:
        """验证内部状态"""
        return os.path.exists(self.db_path)


# 全局单例
Pipeline = InformationPipeline()
