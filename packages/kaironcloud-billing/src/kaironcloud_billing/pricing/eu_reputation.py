"""Reputation Ledger — decentralized reputation tracking for federation nodes.

Key concepts:
- Reputation scoring: 70% success rate + 30% average quality, SMA-based
- Sigmoid feedback: smooth reputation adjustment via positive/negative feedback
- Circuit breaker: automatic isolation when reputation drops below threshold
- IQR anomaly detection: statistical outlier identification
- Time decay: reputation decays slowly over inactivity periods

Merged from eu-pricing package into kaironcloud-billing pricing subpackage.
"""

from __future__ import annotations

import logging
import math
import os
import sqlite3
import time

logger = logging.getLogger(__name__)

REPUTATION_CIRCUIT_THRESHOLD = 0.3
CIRCUIT_BREAK_DURATION = 3600
TIME_DECAY_LAMBDA = 1e-6


class ReputationLedger:
    """Federated node reputation ledger with circuit breaker support."""

    def __init__(self, db_path: str = "data/db/core/reputation.db") -> None:
        self.status = "active"
        self.db_path = db_path
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._persistent_conn = None
        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:")
            self._ensure_schema_on_conn(self._persistent_conn)
        else:
            self._ensure_schema()

    def _ensure_schema_on_conn(self, conn: sqlite3.Connection) -> None:
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
        cursor = conn.execute("PRAGMA table_info(reputation_nodes)")
        columns = [row[1] for row in cursor.fetchall()]
        if "circuit_open" not in columns:
            conn.execute("ALTER TABLE reputation_nodes ADD COLUMN circuit_open INTEGER DEFAULT 0")
        if "circuit_opened_at" not in columns:
            conn.execute("ALTER TABLE reputation_nodes ADD COLUMN circuit_opened_at REAL DEFAULT NULL")
        conn.commit()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            self._ensure_schema_on_conn(conn)

    def _get_connection(self) -> sqlite3.Connection:
        if self._persistent_conn is not None:
            return self._persistent_conn
        return sqlite3.connect(self.db_path)

    def __del__(self) -> None:
        if self._persistent_conn is not None:
            self._persistent_conn.close()
            self._persistent_conn = None

    def report_outcome(self, node_id: str, success: bool, quality: float = 0.5) -> float:
        now = time.time()
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM reputation_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()

        if not row:
            attempted = 1
            completed = 1 if success else 0
            quality_sum = quality if success else 0.0
        else:
            attempted = row["tasks_attempted"] + 1
            completed = row["tasks_completed"] + (1 if success else 0)
            quality_sum = row["total_quality"] + (quality if success else 0.0)

        success_rate = completed / attempted
        avg_quality = quality_sum / completed if completed > 0 else 0.5
        new_reputation = max(0.0, min(1.0, (success_rate * 0.7) + (avg_quality * 0.3)))

        conn.execute(
            """INSERT OR REPLACE INTO reputation_nodes
            (node_id, tasks_attempted, tasks_completed, total_quality, reputation, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (node_id, attempted, completed, quality_sum, new_reputation, now),
        )
        conn.commit()

        if new_reputation < REPUTATION_CIRCUIT_THRESHOLD:
            self.trip_circuit(
                node_id,
                reason=f"Reputation {new_reputation:.3f} below threshold {REPUTATION_CIRCUIT_THRESHOLD}",
            )

        return new_reputation

    def apply_feedback(self, node_id: str, is_positive: bool) -> float:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM reputation_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()

        if not row:
            current_rep = 0.55 if is_positive else 0.45
            attempted = 0
            completed = 0
            quality_sum = 0.0
        else:
            current_rep = row["reputation"]
            attempted = row["tasks_attempted"]
            completed = row["tasks_completed"]
            quality_sum = row["total_quality"]

        delta = 0.15 * current_rep * (1.0 - current_rep)
        new_reputation = current_rep + delta if is_positive else current_rep - delta
        new_reputation = max(0.01, min(0.99, new_reputation))

        now = time.time()
        conn.execute(
            """INSERT OR REPLACE INTO reputation_nodes
            (node_id, tasks_attempted, tasks_completed, total_quality, reputation, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (node_id, attempted, completed, quality_sum, new_reputation, now),
        )
        conn.commit()

        logger.info(
            "[Reputation] Feedback applied to %s: %.3f -> %.3f (Positive: %s)",
            node_id, current_rep, new_reputation, is_positive,
        )
        return new_reputation

    def get_reputation(self, node_id: str) -> float:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM reputation_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        if not row:
            return 0.5
        base_reputation = row["reputation"]
        last_updated = row["last_updated"]
        age = time.time() - last_updated
        if age <= 1e-3:
            return max(0.0, min(1.0, base_reputation))
        decayed = base_reputation * math.exp(-TIME_DECAY_LAMBDA * age)
        return max(0.0, min(1.0, decayed))

    def is_node_circuit_open(self, node_id: str) -> bool:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT circuit_open, circuit_opened_at FROM reputation_nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if not row or not row["circuit_open"]:
            return False
        if row["circuit_opened_at"]:
            if time.time() - row["circuit_opened_at"] >= CIRCUIT_BREAK_DURATION:
                self.reset_circuit(node_id)
                return False
        return True

    def trip_circuit(self, node_id: str, reason: str = "") -> None:
        now = time.time()
        conn = self._get_connection()
        conn.execute(
            "UPDATE reputation_nodes SET circuit_open = 1, circuit_opened_at = ? WHERE node_id = ?",
            (now, node_id),
        )
        conn.commit()
        logger.warning("[CIRCUIT] Tripped circuit for node %s: %s", node_id, reason)

    def reset_circuit(self, node_id: str) -> None:
        conn = self._get_connection()
        conn.execute(
            "UPDATE reputation_nodes SET circuit_open = 0, circuit_opened_at = NULL WHERE node_id = ?",
            (node_id,),
        )
        conn.commit()
        logger.info("[CIRCUIT] Manually reset circuit for node %s", node_id)

    def detect_anomalies(self) -> list[str]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT node_id, reputation FROM reputation_nodes").fetchall()
        if len(rows) < 4:
            return []
        reputations = [row["reputation"] for row in rows]
        node_ids = [row["node_id"] for row in rows]
        sorted_reps = sorted(reputations)
        n = len(sorted_reps)
        q1 = sorted_reps[n // 4]
        q3 = sorted_reps[(3 * n) // 4]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return [node_ids[i] for i, rep in enumerate(reputations) if rep < lower or rep > upper]

    def list_top_nodes(self, limit: int = 10) -> list[dict]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM reputation_nodes ORDER BY reputation DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
