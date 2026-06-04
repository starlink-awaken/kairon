from __future__ import annotations

"""
---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Updated: 2026-03-08
Authority: 4
Keywords: [audit, query, sqlite, governance, events, cross-domain]
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# AuditQueryEngine ≡ Organ
# 内涵 ≝ {id, event_type, domain, actor, payload, timestamp, severity}
# 外延 ≝ {a | a ∈ D-Governance ∧ audit_event(a)}
# 功能 ⊢ {Record, Query, Get, Count, Purge}
# =============================================================================

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kairon_lib._compat import managed_connection

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------

SEVERITY_INFO = "INFO"
SEVERITY_WARN = "WARN"
SEVERITY_ERROR = "ERROR"

_VALID_SEVERITIES: frozenset[str] = frozenset({SEVERITY_INFO, SEVERITY_WARN, SEVERITY_ERROR})

# ---------------------------------------------------------------------------
# AuditEvent dataclass
# ---------------------------------------------------------------------------


@dataclass
class AuditEvent:
    """Represents a single cross-domain audit event."""

    id: str
    event_type: str  # "adr_created", "gate_review", "phase_transition", "error_occurred", …
    domain: str  # which B-OS domain produced the event
    actor: str  # role or system that triggered it
    payload: dict  # arbitrary event details
    timestamp: str  # ISO-8601 UTC
    severity: str  # "INFO" | "WARN" | "ERROR"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "domain": self.domain,
            "actor": self.actor,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "severity": self.severity,
        }


# ---------------------------------------------------------------------------
# AuditQueryEngine
# ---------------------------------------------------------------------------


class AuditQueryEngine:
    """Cross-domain audit log: record and query system events.

    SQLite at ``data/db/organs/governance/audit.db``.
    Supports time-range, domain, event_type, severity filters.
    Thread-safe; uses a per-instance Lock.

    BOS-URI endpoints
    -----------------
    ``bos://governance/audit/record``  — record a new event
    ``bos://governance/audit/query``   — query events with filters
    """

    _DEFAULT_DB: str = "data/db/organs/governance/audit.db"
    _lock: threading.Lock

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        _log.debug("[AuditQueryEngine] db=%s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return managed_connection(conn)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id          TEXT PRIMARY KEY,
                    event_type  TEXT NOT NULL,
                    domain      TEXT NOT NULL,
                    actor       TEXT NOT NULL DEFAULT 'system',
                    payload     TEXT NOT NULL DEFAULT '{}',
                    timestamp   TEXT NOT NULL,
                    severity    TEXT NOT NULL DEFAULT 'INFO'
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_domain    ON audit_events(domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_type      ON audit_events(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_severity  ON audit_events(severity)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp)")
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _row_to_event(self, row: sqlite3.Row) -> AuditEvent:
        return AuditEvent(
            id=row["id"],
            event_type=row["event_type"],
            domain=row["domain"],
            actor=row["actor"],
            payload=json.loads(row["payload"]),
            timestamp=row["timestamp"],
            severity=row["severity"],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        event_type: str,
        domain: str,
        actor: str,
        payload: dict,
        severity: str = SEVERITY_INFO,
    ) -> AuditEvent:
        """Record a new audit event and return it."""
        if severity not in _VALID_SEVERITIES:
            _log.warning("[AuditQueryEngine] Unknown severity '%s', defaulting to INFO", severity)
            severity = SEVERITY_INFO

        event = AuditEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            domain=domain,
            actor=actor,
            payload=payload,
            timestamp=self._now(),
            severity=severity,
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (id, event_type, domain, actor, payload, timestamp, severity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.event_type,
                    event.domain,
                    event.actor,
                    json.dumps(event.payload),
                    event.timestamp,
                    event.severity,
                ),
            )
            conn.commit()
        _log.debug("[AuditQueryEngine] recorded event %s type=%s domain=%s", event.id, event_type, domain)
        return event

    def query(
        self,
        *,
        domain: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        since: str | None = None,
        limit: int = 50,
    ) -> list[AuditEvent]:
        """Query audit events with optional filters.

        Parameters
        ----------
        domain:     filter by domain (exact match)
        event_type: filter by event_type (exact match)
        severity:   filter by severity level
        since:      ISO-8601 timestamp lower-bound (inclusive)
        limit:      maximum number of results (default 50)
        """
        clauses: list[str] = []
        params: list = []

        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if severity is not None:
            clauses.append("severity = ?")
            params.append(severity)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM audit_events {where} ORDER BY timestamp DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get(self, event_id: str) -> AuditEvent | None:
        """Return a single event by id, or *None* if not found."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM audit_events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_event(row)

    def count(self, domain: str | None = None) -> int:
        """Count events, optionally scoped to a domain."""
        if domain is not None:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) FROM audit_events WHERE domain = ?", (domain,)).fetchone()
        else:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()
        return row[0] if row else 0

    def purge_before(self, timestamp: str) -> int:
        """Delete all events with timestamp < *timestamp*.

        Returns the number of deleted rows.
        """
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM audit_events WHERE timestamp < ?", (timestamp,))
            conn.commit()
        deleted = cur.rowcount
        _log.debug("[AuditQueryEngine] purged %d events before %s", deleted, timestamp)
        return deleted
