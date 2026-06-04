from __future__ import annotations

"""
SQLite persistence seam for ApprovalRouter.

Provides the ``ApprovalPersistence`` class that owns the optional SQLite
lifecycle for ``ApprovalRouter`` request and decision state.
"""

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .approval_router import ApprovalRequest, Decision


class ApprovalPersistence:
    """Own the optional SQLite lifecycle for ApprovalRouter state.

    When no *db_path* is given all methods are no-ops, keeping the
    router usable in pure in-memory mode.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_conn: sqlite3.Connection | None = None
        if db_path is not None:
            self._init_db(db_path)

    @property
    def enabled(self) -> bool:
        """``True`` when a SQLite connection is active."""
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
                reason TEXT,
                approver TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES approval_requests(id)
            )
            """
        )
        self._db_conn = conn

    # ------------------------------------------------------------------
    # Request CRUD
    # ------------------------------------------------------------------

    def insert_request(self, request: ApprovalRequest) -> None:
        """Persist a new approval request."""
        if not self._db_conn:
            return
        self._db_conn.execute(
            """
            INSERT OR REPLACE INTO approval_requests
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
        """Update an existing request's status / committee / timestamp."""
        if not self._db_conn:
            return
        self._db_conn.execute(
            """
            UPDATE approval_requests
            SET status = ?, committee_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (request.status, request.committee_id, request.updated_at.isoformat(), request.id),
        )
        self._db_conn.commit()

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        """Fetch a single request as a plain dict, or ``None``."""
        if not self._db_conn:
            return None
        row = self._db_conn.execute(
            "SELECT id, type, payload, requester, status, committee_id, created_at, updated_at "
            "FROM approval_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "type": row[1],
            "payload": json.loads(row[2]),
            "requester": row[3],
            "status": row[4],
            "committee_id": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

    # ------------------------------------------------------------------
    # Decision CRUD
    # ------------------------------------------------------------------

    def insert_decision(self, decision: Decision) -> None:
        """Persist a decision record."""
        if not self._db_conn:
            return
        self._db_conn.execute(
            """
            INSERT OR REPLACE INTO approval_decisions
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

    def get_decisions(self, request_id: str) -> list[dict[str, Any]]:
        """Return all decisions for *request_id*, ordered chronologically."""
        if not self._db_conn:
            return []
        rows = self._db_conn.execute(
            "SELECT id, request_id, decision, reason, approver, created_at "
            "FROM approval_decisions WHERE request_id = ? ORDER BY created_at ASC",
            (request_id,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "request_id": r[1],
                "decision": r[2],
                "reason": r[3],
                "approver": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the SQLite connection if open."""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None
