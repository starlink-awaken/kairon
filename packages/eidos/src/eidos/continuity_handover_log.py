from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Summary: 'Handover logging for federated node transitions.'
Authority: organs/D-Continuity/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Handover Log ≡ Module
# 内涵 ≝ {Handover, Log}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, HandoverLog)}
# 功能 ⊢ {Handover_Log, Init_Handover, Validate_Log}
# =============================================================================

import json
import logging
import os
import sqlite3
import time
import uuid
from typing import Any

_log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)


class HandoverLog:
    """
    [TRK-013] 联邦节点交接日志

    记录节点间的 Baton（交接棒）传递事件，用于追踪任务在手写节点间的流转。
    """

    def __init__(self, db_path: str = "data/db/core/handover.db") -> None:
        """初始化交接日志

        Args:
            db_path: SQLite 数据库路径
        """
        self.status = "active"
        self.db_path = db_path
        # 处理 :memory: 特殊路径
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """确保数据库 schema 存在"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS handovers (
                    id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    source_node TEXT NOT NULL,
                    target_node TEXT NOT NULL,
                    baton_contents TEXT,
                    metadata TEXT,
                    created_at REAL NOT NULL
                )
            """)

            # 创建索引以加速查询
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source_node
                ON handovers(source_node)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_target_node
                ON handovers(target_node)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON handovers(timestamp)
            """)

            conn.commit()

    def record_handover(
        self,
        source_node: str,
        target_node: str,
        baton_contents: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """记录一次交接事件

        Args:
            source_node: 源节点 ID
            target_node: 目标节点 ID
            baton_contents: Baton 内容（任务上下文）
            metadata: 可选的元数据

        Returns:
            交接记录 ID
        """
        now = time.time()
        handover_id = f"handover_{int(now * 1000)}_{uuid.uuid4().hex}_{source_node}_{target_node}"

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO handovers
                (id, timestamp, source_node, target_node, baton_contents, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    handover_id,
                    now,
                    source_node,
                    target_node,
                    json.dumps(baton_contents),
                    json.dumps(metadata or {}),
                    now,
                ),
            )
            conn.commit()

        logger.info(
            f"[TRK-013] 交接记录: {source_node} -> {target_node} "
            f"(id: {handover_id}, baton_keys: {list(baton_contents.keys())})"
        )

        return handover_id

    def query_handover_history(
        self,
        node_id: str | None = None,
        limit: int = 100,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> list[dict[str, Any]]:
        """查询交接历史

        Args:
            node_id: 可选的节点 ID，过滤该节点相关的交接
            limit: 最大返回记录数
            start_time: 可选的起始时间
            end_time: 可选的结束时间

        Returns:
            交接记录列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT * FROM handovers WHERE 1=1"
            params: list[Any] = []

            if node_id:
                query += " AND (source_node = ? OR target_node = ?)"
                params.extend([node_id, node_id])

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_handover(self, node_id: str) -> dict[str, Any] | None:
        """获取指定节点的最新交接记录

        Args:
            node_id: 节点 ID

        Returns:
            最新交接记录，如果不存在则返回 None
        """
        history = self.query_handover_history(node_id=node_id, limit=1)
        return history[0] if history else None

    def get_handover_chain(self, initial_node: str, max_depth: int = 10) -> list[dict[str, Any]]:
        """构建交接链

        从初始节点开始，追踪完整的交接路径。

        Args:
            initial_node: 初始节点 ID
            max_depth: 最大追踪深度

        Returns:
            交接链列表，按时间顺序排列
        """
        chain: list[dict[str, Any]] = []
        current_node = initial_node
        visited = set()

        for _ in range(max_depth):
            if current_node in visited:
                break  # 避免循环
            visited.add(current_node)

            # 查找从当前节点发出的交接
            history = self.query_handover_history(
                node_id=current_node,
                limit=1,
            )

            if not history:
                break  # 没有更多交接

            latest = history[0]

            # 确保这是从当前节点发出的交接
            if latest["source_node"] != current_node:
                break

            chain.append(latest)
            current_node = latest["target_node"]

        return chain
