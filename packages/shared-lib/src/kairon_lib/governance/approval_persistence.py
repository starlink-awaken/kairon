# ---
# domain: D-Governance
# layer: organ
# status: active
# ---
from __future__ import annotations

"""SQLite persistence seam for ApprovalRouter."""

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .approval_router import ApprovalRequest, Decision


class ApprovalPersistence:
    """Own the optional SQLite lifecycle for ApprovalRouter state."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_conn: sqlite3.Connection | None = None
        if db_path is not None:
            self._init_db(db_path)

    @property
    def enabled(self) -> bool:
        return self._db_conn is not None

    def _init_db(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_requests (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                requester TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                committee_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_decisions (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                approver TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES approval_requests(id)
            )
            """
        )
        conn.commit()
        self._db_conn = conn

    def insert_request(self, request: ApprovalRequest) -> None:
        if self._db_conn is None:
            return
        self._db_conn.execute(
            """
            INSERT OR IGNORE INTO approval_requests
                (id, type, payload, requester, status, committee_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.id,
                request.type,
                json.dumps(request.payload),
                request.requester,
                request.status,
                request.committee_id,
                request.created_at.isoformat(),
                request.updated_at.isoformat(),
            ),
        )
        self._db_conn.commit()

    def update_request(self, request: ApprovalRequest) -> None:
        if self._db_conn is None:
            return
        self._db_conn.execute(
            """
            UPDATE approval_requests
            SET status=?, committee_id=?, updated_at=?
            WHERE id=?
            """,
            (
                request.status,
                request.committee_id,
                request.updated_at.isoformat(),
                request.id,
            ),
        )
        self._db_conn.commit()

    def insert_decision(self, decision: Decision) -> None:
        if self._db_conn is None:
            return
        self._db_conn.execute(
            """
            INSERT OR IGNORE INTO approval_decisions
                (id, request_id, decision, reason, approver, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                decision.id,
                decision.request_id,
                decision.decision,
                decision.reason,
                decision.approver,
                decision.created_at.isoformat(),
            ),
        )
        self._db_conn.commit()

    def close(self) -> None:
        if self._db_conn is None:
            return
        self._db_conn.close()
        self._db_conn = None
