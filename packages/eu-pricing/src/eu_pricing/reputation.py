"""Reputation Ledger — decentralized reputation tracking for federation nodes.

Extracted from SharedBrain D_Economy reputation_ledger.py.
Independent of SharedBrain infrastructure.

Key concepts:
- Reputation scoring: 70% success rate + 30% average quality, SMA-based
- Sigmoid feedback: smooth reputation adjustment via positive/negative feedback
- Circuit breaker: automatic isolation when reputation drops below threshold
- IQR anomaly detection: statistical outlier identification
- Time decay: reputation decays slowly over inactivity periods
"""

from __future__ import annotations

import logging
import math
import os
import sqlite3
import time

logger = logging.getLogger(__name__)

# Circuit breaker constants
REPUTATION_CIRCUIT_THRESHOLD = 0.3
CIRCUIT_BREAK_DURATION = 3600  # 1 hour in seconds
TIME_DECAY_LAMBDA = 1e-6  # Approximately 0.1% decay per day


class ReputationLedger:
    """
    [RFC-014] 联邦节点声誉账本。
    负责记录和计算每个节点的信用等级。
    """

    def __init__(self, db_path: str = "data/db/core/reputation.db") -> None:
        self.status = "active"
        self.db_path = db_path
        # Don't create directory for in-memory databases
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # For in-memory databases, keep a persistent connection
        self._persistent_conn = None
        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:")
            self._ensure_schema_on_conn(self._persistent_conn)
        else:
            self._ensure_schema()

    def _ensure_schema_on_conn(self, conn: sqlite3.Connection) -> None:
        """Ensure schema exists on the given connection."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reputation_nodes (
                node_id         TEXT PRIMARY KEY,
                tasks_attempted INTEGER DEFAULT 0,
                tasks_completed INTEGER DEFAULT 0,
                total_quality   REAL DEFAULT 0.0,
                reputation      REAL DEFAULT 0.5,
                last_updated    REAL NOT NULL,
                circuit_open    INTEGER DEFAULT 0,
                circuit_opened_at REAL DEFAULT NULL
            )
        """)
        # Add new columns if table exists (migration)
        cursor = conn.execute("PRAGMA table_info(reputation_nodes)")
        columns = [row[1] for row in cursor.fetchall()]
        if "circuit_open" not in columns:
            conn.execute("ALTER TABLE reputation_nodes ADD COLUMN circuit_open INTEGER DEFAULT 0")
        if "circuit_opened_at" not in columns:
            conn.execute(
                "ALTER TABLE reputation_nodes ADD COLUMN circuit_opened_at REAL DEFAULT NULL"
            )
        conn.commit()

    def _ensure_schema(self) -> None:
        """Ensure schema exists for file-based databases."""
        with sqlite3.connect(self.db_path) as conn:
            self._ensure_schema_on_conn(conn)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection, handling in-memory case."""
        if self._persistent_conn is not None:
            return self._persistent_conn
        return sqlite3.connect(self.db_path)

    def __del__(self) -> None:
        """Clean up in-memory connection on deletion."""
        if self._persistent_conn is not None:
            self._persistent_conn.close()
            self._persistent_conn = None

    def report_outcome(self, node_id: str, success: bool, quality: float = 0.5) -> float:
        """记录一次执行结果并更新声誉值。"""
        now = time.time()
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM reputation_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()

        if not row:
            # 新节点初始状态
            attempted = 1
            completed = 1 if success else 0
            quality_sum = quality if success else 0.0
        else:
            attempted = row["tasks_attempted"] + 1
            completed = row["tasks_completed"] + (1 if success else 0)
            quality_sum = row["total_quality"] + (quality if success else 0.0)

        # 计算新声誉: 简单移动平均 (SMA) 思想，可后续引入贝叶斯平滑
        success_rate = completed / attempted
        avg_quality = quality_sum / completed if completed > 0 else 0.5

        # Reputation = (Success_Rate * 0.7) + (Avg_Quality * 0.3)
        new_reputation = (success_rate * 0.7) + (avg_quality * 0.3)
        # 限制在 [0.0, 1.0]
        new_reputation = max(0.0, min(1.0, new_reputation))

        # 先更新声誉（保留熔断器状态）
        conn.execute(
            """
            INSERT OR REPLACE INTO reputation_nodes
            (node_id, tasks_attempted, tasks_completed, total_quality, reputation, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (node_id, attempted, completed, quality_sum, new_reputation, now),
        )
        conn.commit()

        # 自动触发熔断器（独立的电路状态管理）
        if new_reputation < REPUTATION_CIRCUIT_THRESHOLD:
            self.trip_circuit(
                node_id,
                reason=f"Reputation {new_reputation:.3f} below threshold {REPUTATION_CIRCUIT_THRESHOLD}",
            )

        return new_reputation

    def apply_feedback(self, node_id: str, is_positive: bool) -> float:
        """
        [RFC-031] 处理来自真实世界（或关联联想）的用户反馈。
        使用 Sigmoid 函数平滑调整声誉值，代替硬编码常量演化。
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM reputation_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()

        if not row:
            # 如果节点不存在，初始化一个默认偏向的声誉
            current_rep = 0.55 if is_positive else 0.45
            attempted = 0
            completed = 0
            quality_sum = 0.0
        else:
            current_rep = row["reputation"]
            attempted = row["tasks_attempted"]
            completed = row["tasks_completed"]
            quality_sum = row["total_quality"]

        # Sigmoid 步长调整：反馈影响随极端值减弱 (防止被单次反馈刷爆或踩死)
        # delta = 0.1 * current_rep * (1 - current_rep)
        delta = 0.15 * current_rep * (1.0 - current_rep)

        if is_positive:
            new_reputation = current_rep + delta
        else:
            new_reputation = current_rep - delta

        new_reputation = max(0.01, min(0.99, new_reputation))  # 保留一点余地

        now = time.time()
        conn.execute(
            """
            INSERT OR REPLACE INTO reputation_nodes
            (node_id, tasks_attempted, tasks_completed, total_quality, reputation, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (node_id, attempted, completed, quality_sum, new_reputation, now),
        )
        conn.commit()

        logger.info(
            "[Reputation] Feedback applied to %s: %.3f -> %.3f (Positive: %s)",
            node_id,
            current_rep,
            new_reputation,
            is_positive,
        )
        return new_reputation

    def get_reputation(self, node_id: str) -> float:
        """获取特定节点的声誉值，应用时间衰减。"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM reputation_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        if not row:
            return 0.5  # 默认中庸分

        base_reputation = row["reputation"]
        last_updated = row["last_updated"]

        # 应用时间衰减：score * exp(-lambda * age)
        age = time.time() - last_updated
        if age <= 1e-3:
            return max(0.0, min(1.0, base_reputation))
        decayed_reputation = base_reputation * math.exp(-TIME_DECAY_LAMBDA * age)

        return max(0.0, min(1.0, decayed_reputation))

    def is_node_circuit_open(self, node_id: str) -> bool:
        """检查节点熔断器是否打开。

        如果熔断器打开且已超过恢复时间，则自动关闭。
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT circuit_open, circuit_opened_at FROM reputation_nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()

        if not row:
            return False  # 新节点，熔断器关闭

        if not row["circuit_open"]:
            return False  # 熔断器关闭

        # 检查是否已超过恢复时间
        if row["circuit_opened_at"]:
            time_since_open = time.time() - row["circuit_opened_at"]
            if time_since_open >= CIRCUIT_BREAK_DURATION:
                # 自动关闭熔断器
                self.reset_circuit(node_id)
                logger.info(
                    "[CIRCUIT] Auto-reset circuit for node %s after %.0fs",
                    node_id,
                    time_since_open,
                )
                return False

        return True  # 熔断器仍然打开

    def trip_circuit(self, node_id: str, reason: str = "") -> None:
        """触发节点熔断器。

        当节点声誉低于阈值时调用，将节点从候选池中隔离。
        """
        now = time.time()
        conn = self._get_connection()
        conn.execute(
            """
            UPDATE reputation_nodes
            SET circuit_open = 1, circuit_opened_at = ?
            WHERE node_id = ?
        """,
            (now, node_id),
        )
        conn.commit()

        logger.warning("[CIRCUIT] Tripped circuit for node %s: %s", node_id, reason)

    def reset_circuit(self, node_id: str) -> None:
        """手动重置节点熔断器。

        允许节点重新参与任务分配。
        """
        conn = self._get_connection()
        conn.execute(
            """
            UPDATE reputation_nodes
            SET circuit_open = 0, circuit_opened_at = NULL
            WHERE node_id = ?
        """,
            (node_id,),
        )
        conn.commit()

        logger.info("[CIRCUIT] Manually reset circuit for node %s", node_id)

    def detect_anomalies(self) -> list[str]:
        """使用IQR方法检测声誉异常值。

        返回异常节点ID列表（声誉在 Q1 - 1.5*IQR 或 Q3 + 1.5*IQR 之外）。
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT node_id, reputation FROM reputation_nodes").fetchall()

        if len(rows) < 4:  # IQR需要至少4个数据点
            return []

        reputations = [row["reputation"] for row in rows]
        node_ids = [row["node_id"] for row in rows]

        # 计算四分位数
        sorted_reps = sorted(reputations)
        n = len(sorted_reps)

        q1_idx = n // 4
        q3_idx = (3 * n) // 4

        q1 = sorted_reps[q1_idx]
        q3 = sorted_reps[q3_idx]
        iqr = q3 - q1

        # 异常值边界
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        # 识别异常节点
        anomalies = []
        for i, rep in enumerate(reputations):
            if rep < lower_bound or rep > upper_bound:
                anomalies.append(node_ids[i])

        return anomalies

    def list_top_nodes(self, limit: int = 10) -> list[dict]:
        """返回声誉最高的 N 个节点。"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM reputation_nodes ORDER BY reputation DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
