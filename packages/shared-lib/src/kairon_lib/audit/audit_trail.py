from __future__ import annotations

"""
---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Updated: 2026-03-17
Authority: 4
Keywords: [audit, trail, log, history, compliance, governance, sqlite]
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# AuditTrail ≡ Organ
# 内涵 ≝ {entry_id, operation_type, actor, target, changes, timestamp, severity}
# 外延 ≝ {a | a ∈ D-Governance ∧ audit_entry(a)}
# 功能 ⊢ {LogOperation, GetHistory, GenerateReport, GetEntry, SearchEntries,
#          GetChangesByActor, GetChangesByTarget, PurgeOldEntries}
# =============================================================================

import json
import logging
import sqlite3
import threading
import uuid

# Local governance types (adapted from Z-Core law layer via facade pattern)
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path


class DecisionStatus(Enum):
    """Possible outcomes of a governance decision."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


@dataclass
class DecisionResult:
    """The outcome of a governance decision."""

    request_id: str
    status: DecisionStatus
    reason: str = ""
    decided_by: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


from typing import Any

from kairon_lib._compat import managed_connection

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OperationType enum
# ---------------------------------------------------------------------------


class OperationType(StrEnum):
    """Type of governance operation being audited."""

    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_DELETED = "policy_deleted"
    POLICY_EXECUTED = "policy_executed"
    VOTE_CAST = "vote_cast"
    CONSENSUS_REACHED = "consensus_reached"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ROLE_INHERITED = "role_inherited"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    AUTO_EXECUTED = "auto_executed"
    EXECUTION_ROLLED_BACK = "execution_rolled_back"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# AuditSeverity enum
# ---------------------------------------------------------------------------


class AuditSeverity(StrEnum):
    """Severity level of audit entries."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# AuditEntry dataclass
# ---------------------------------------------------------------------------


@dataclass
class AuditEntry:
    """Represents a single audit trail entry."""

    id: str
    operation_type: OperationType
    actor: str  # User or system that performed the operation
    target: str  # Resource or object affected
    changes: dict[str, object]  # What changed
    timestamp: str
    severity: AuditSeverity
    metadata: dict[str, object] | None = None  # Additional context
    correlation_id: str | None = None  # Link related operations

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "operation_type": self.operation_type.value,
            "actor": self.actor,
            "target": self.target,
            "changes": self.changes,
            "timestamp": self.timestamp,
            "severity": self.severity.value,
            "metadata": self.metadata,
            "correlation_id": self.correlation_id,
        }


# ---------------------------------------------------------------------------
# ChangeDelta dataclass
# ---------------------------------------------------------------------------


@dataclass
class ChangeDelta:
    """Represents a specific change within an audit entry."""

    field: str
    old_value: Any
    new_value: Any


# ---------------------------------------------------------------------------
# ComplianceReport dataclass
# ---------------------------------------------------------------------------


@dataclass
class ComplianceReport:
    """Generated compliance report from audit trail."""

    report_id: str
    start_date: str
    end_date: str
    total_entries: int
    operation_counts: dict[str, int]
    top_actors: list[tuple[str, int]]
    critical_events: list[AuditEntry]
    generated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_entries": self.total_entries,
            "operation_counts": self.operation_counts,
            "top_actors": [{"actor": actor, "count": count} for actor, count in self.top_actors],
            "critical_events": [e.to_dict() for e in self.critical_events],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# AuditTrail
# ---------------------------------------------------------------------------


class AuditTrail:
    """Governance audit trail for compliance and accountability.

    Implements :class:`IDecisionAuditor` from Z-Core/L2-Law.

    Records all governance operations with full change history.
    Supports querying by actor, target, time range, and operation type.

    SQLite at ``data/db/organs/governance/audit_trail.db``.
    Thread-safe; uses a per-instance Lock.

    BOS-URI endpoints
    -----------------
    ``bos://governance/audit/log``     — log an operation
    ``bos://governance/audit/history`` — get change history
    ``bos://governance/audit/report``  — generate compliance report
    ``bos://governance/audit/search``  — search audit entries
    """

    _DEFAULT_DB: str = "data/db/organs/governance/audit_trail.db"
    _lock: threading.Lock

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        _log.debug("[AuditTrail] db=%s", self._db_path)

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
                CREATE TABLE IF NOT EXISTS audit_entries (
                    id                TEXT PRIMARY KEY,
                    operation_type    TEXT NOT NULL,
                    actor             TEXT NOT NULL,
                    target            TEXT NOT NULL,
                    changes_json      TEXT NOT NULL DEFAULT '{}',
                    timestamp         TEXT NOT NULL,
                    severity          TEXT NOT NULL DEFAULT 'info',
                    metadata_json     TEXT,
                    correlation_id    TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_operation ON audit_entries(operation_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor    ON audit_entries(actor)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_target   ON audit_entries(target)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_entries(timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_entries(severity)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_entries(correlation_id)")
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _row_to_entry(self, row: sqlite3.Row) -> AuditEntry:
        return AuditEntry(
            id=row["id"],
            operation_type=OperationType(row["operation_type"]),
            actor=row["actor"],
            target=row["target"],
            changes=json.loads(row["changes_json"]),
            timestamp=row["timestamp"],
            severity=AuditSeverity(row["severity"]),
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else None,
            correlation_id=row["correlation_id"],
        )

    # ------------------------------------------------------------------
    # Public API: Logging
    # ------------------------------------------------------------------

    def log_operation(
        self,
        operation_type: OperationType,
        actor: str,
        target: str,
        changes: dict[str, object],
        severity: AuditSeverity = AuditSeverity.INFO,
        metadata: dict[str, object] | None = None,
        correlation_id: str | None = None,
    ) -> AuditEntry:
        """Log a governance operation to the audit trail."""
        entry_id = str(uuid.uuid4())
        now = self._now()

        entry = AuditEntry(
            id=entry_id,
            operation_type=operation_type,
            actor=actor,
            target=target,
            changes=changes,
            timestamp=now,
            severity=severity,
            metadata=metadata,
            correlation_id=correlation_id,
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_entries
                    (id, operation_type, actor, target, changes_json, timestamp, severity, metadata_json, correlation_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.operation_type.value,
                    entry.actor,
                    entry.target,
                    json.dumps(entry.changes),
                    entry.timestamp,
                    entry.severity.value,
                    json.dumps(entry.metadata) if entry.metadata else None,
                    entry.correlation_id,
                ),
            )
            conn.commit()

        _log.debug(
            "[AuditTrail] logged %s by %s on %s",
            operation_type.value,
            actor,
            target,
        )
        return entry

    def log_change(
        self,
        operation_type: OperationType,
        actor: str,
        target: str,
        field: str,
        old_value: Any,
        new_value: Any,
        severity: AuditSeverity = AuditSeverity.INFO,
        correlation_id: str | None = None,
    ) -> AuditEntry:
        """Convenience method to log a single field change."""
        changes = {"field": field, "old": old_value, "new": new_value}
        return self.log_operation(
            operation_type=operation_type,
            actor=actor,
            target=target,
            changes=changes,
            severity=severity,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Public API: Querying
    # ------------------------------------------------------------------

    def get_entry(self, entry_id: str) -> AuditEntry | None:
        """Retrieve a single audit entry by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM audit_entries WHERE id = ?", (entry_id,)).fetchone()

        if row is None:
            return None
        return self._row_to_entry(row)

    def get_history(
        self,
        target: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get change history for a specific target."""
        clauses: list[str] = ["target = ?"]
        params: list = [target]

        if start_date is not None:
            clauses.append("timestamp >= ?")
            params.append(start_date)
        if end_date is not None:
            clauses.append("timestamp <= ?")
            params.append(end_date)

        where = "WHERE " + " AND ".join(clauses)
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM audit_entries {where} ORDER BY timestamp DESC LIMIT ?",
                params,
            ).fetchall()

        return [self._row_to_entry(r) for r in rows]

    def search_entries(
        self,
        operation_type: OperationType | None = None,
        actor: str | None = None,
        target: str | None = None,
        severity: AuditSeverity | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        correlation_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Search audit entries with multiple filters."""
        clauses: list[str] = []
        params: list = []

        if operation_type is not None:
            clauses.append("operation_type = ?")
            params.append(operation_type.value)
        if actor is not None:
            clauses.append("actor = ?")
            params.append(actor)
        if target is not None:
            clauses.append("target = ?")
            params.append(target)
        if severity is not None:
            clauses.append("severity = ?")
            params.append(severity.value)
        if start_date is not None:
            clauses.append("timestamp >= ?")
            params.append(start_date)
        if end_date is not None:
            clauses.append("timestamp <= ?")
            params.append(end_date)
        if correlation_id is not None:
            clauses.append("correlation_id = ?")
            params.append(correlation_id)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM audit_entries {where} ORDER BY timestamp DESC LIMIT ?",
                params,
            ).fetchall()

        return [self._row_to_entry(r) for r in rows]

    def get_changes_by_actor(self, actor: str, limit: int = 100) -> list[AuditEntry]:
        """Get all changes made by a specific actor."""
        return self.search_entries(actor=actor, limit=limit)

    def get_changes_by_target(self, target: str, limit: int = 100) -> list[AuditEntry]:
        """Get all changes to a specific target."""
        return self.search_entries(target=target, limit=limit)

    # ------------------------------------------------------------------
    # Public API: Reporting
    # ------------------------------------------------------------------

    def generate_report(self, start_date: str, end_date: str | None = None) -> ComplianceReport:
        """Generate a compliance report for a date range."""
        if end_date is None:
            end_date = self._now()

        # Get all entries in range
        entries = self.search_entries(start_date=start_date, end_date=end_date, limit=10000)

        # Count operations by type
        operation_counts: dict[str, int] = {}
        for entry in entries:
            op_type = entry.operation_type.value
            operation_counts[op_type] = operation_counts.get(op_type, 0) + 1

        # Count operations by actor
        actor_counts: dict[str, int] = {}
        for entry in entries:
            actor_counts[entry.actor] = actor_counts.get(entry.actor, 0) + 1

        top_actors = sorted(actor_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Filter critical events
        critical_events = [e for e in entries if e.severity in (AuditSeverity.ERROR, AuditSeverity.CRITICAL)]

        report = ComplianceReport(
            report_id=str(uuid.uuid4()),
            start_date=start_date,
            end_date=end_date,
            total_entries=len(entries),
            operation_counts=operation_counts,
            top_actors=top_actors,
            critical_events=critical_events,
            generated_at=self._now(),
        )

        _log.info(
            "[AuditTrail] generated report %s: %d entries from %s to %s",
            report.report_id,
            len(entries),
            start_date,
            end_date,
        )
        return report

    # ------------------------------------------------------------------
    # Public API: Maintenance
    # ------------------------------------------------------------------

    def purge_old_entries(self, before_date: str) -> int:
        """Delete audit entries older than the specified date.

        Use with caution - this permanently removes audit records.
        Returns the number of deleted entries.
        """
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM audit_entries WHERE timestamp < ?", (before_date,))
            conn.commit()

        deleted = cursor.rowcount
        _log.warning("[AuditTrail] purged %d entries before %s", deleted, before_date)
        return deleted

    def get_statistics(self) -> dict[str, object]:
        """Get statistics about the audit trail."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM audit_entries").fetchone()[0]

            operation_counts = conn.execute(
                "SELECT operation_type, COUNT(*) as count FROM audit_entries GROUP BY operation_type"
            ).fetchall()

            severity_counts = conn.execute(
                "SELECT severity, COUNT(*) as count FROM audit_entries GROUP BY severity"
            ).fetchall()

            oldest = conn.execute("SELECT MIN(timestamp) FROM audit_entries").fetchone()[0]

            newest = conn.execute("SELECT MAX(timestamp) FROM audit_entries").fetchone()[0]

        return {
            "total_entries": total,
            "operation_counts": {row["operation_type"]: row["count"] for row in operation_counts},
            "severity_counts": {row["severity"]: row["count"] for row in severity_counts},
            "oldest_entry": oldest,
            "newest_entry": newest,
        }

    # ------------------------------------------------------------------
    # IDecisionAuditor adapter methods
    # ------------------------------------------------------------------

    _STATUS_MAP: dict[str, DecisionStatus] = {
        "policy_executed": DecisionStatus.APPROVED,
        "consensus_reached": DecisionStatus.APPROVED,
        "permission_granted": DecisionStatus.APPROVED,
        "permission_revoked": DecisionStatus.REJECTED,
        "conflict_detected": DecisionStatus.ESCALATED,
        "execution_rolled_back": DecisionStatus.REJECTED,
    }

    def _entry_to_decision(self, entry: AuditEntry) -> DecisionResult:
        status = self._STATUS_MAP.get(entry.operation_type.value, DecisionStatus.PENDING)
        return DecisionResult(
            request_id=entry.id,
            status=status,
            reason=entry.changes.get("reason", entry.operation_type.value),
            decided_by=entry.actor,
            metadata=entry.changes,
        )

    def record_decision(self, result: DecisionResult) -> str:
        """Persist a decision result. Returns the audit record ID.

        Satisfies :meth:`IDecisionAuditor.record_decision`.
        """
        entry = self.log_operation(
            operation_type=OperationType.CUSTOM,
            actor=result.decided_by or "system",
            target=result.request_id,
            changes={"reason": result.reason, "status": result.status.value, **result.metadata},
            severity=AuditSeverity.INFO,
        )
        return entry.id

    def query_decisions(self, filters: dict[str, object]) -> list[DecisionResult]:
        """Query stored decisions matching the given filters.

        Satisfies :meth:`IDecisionAuditor.query_decisions`.
        """
        entries = self.search_entries(
            actor=filters.get("actor"),
            target=filters.get("target"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            limit=filters.get("limit", 100),
        )
        return [self._entry_to_decision(e) for e in entries]

    def get_decision(self, decision_id: str) -> DecisionResult | None:
        """Retrieve a single decision by its ID.

        Satisfies :meth:`IDecisionAuditor.get_decision`.
        """
        entry = self.get_entry(decision_id)
        if entry is None:
            return None
        return self._entry_to_decision(entry)
