from __future__ import annotations

"""
Audit Trail — Immutable append-only audit logger with JSON export.

Based on D_Immunity patterns:
- organs/audit_ledger/ (AuditLedger, AuditRecord, VerificationResult)
- organs/permission_guard.py (AuditEvent logging)

Provides:
- AuditLogger: record(event, principal, resource, action, result)
- Query audit log by principal, resource, time range
- Immutable append-only log (in-memory with JSON export)
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_log = logging.getLogger(__name__)


# =============================================================================
# AuditRecord
# =============================================================================


@dataclass(frozen=True)
class AuditRecord:
    """An immutable audit record.

    Once created, fields cannot be modified — enforcing append-only semantics.
    """

    record_id: str
    timestamp: str
    principal: str
    resource: str
    action: str
    result: str  # "success" | "failure" | "denied" | "error"
    event: str | None = None  # Optional event name
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "principal": self.principal,
            "resource": self.resource,
            "action": self.action,
            "result": self.result,
            "event": self.event,
            "details": self.details,
        }


# =============================================================================
# AuditLogger
# =============================================================================


class AuditLogger:
    """Immutable append-only audit log with in-memory storage and JSON export.

    Every record is a frozen AuditRecord — once written, never modified.
    Supports querying by principal, resource, and time range.

    Typical usage::

        logger = AuditLogger()
        logger.record("agent-1", "file", "read", "success", event="file_access")
        records = logger.query_by_principal("agent-1")
        logger.export_json("/tmp/audit.json")
    """

    _MAX_RECORDS: int = 50_000
    """Maximum in-memory records before oldest are dropped."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(
        self,
        principal: str,
        resource: str,
        action: str,
        result: str,
        *,
        event: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """Append an immutable audit record and return it.

        Args:
            principal: Who performed the action.
            resource:  What was acted upon.
            action:    The operation performed (read/write/execute/delete).
            result:    Outcome (success/failure/denied/error).
            event:     Optional event name for categorization.
            details:   Optional metadata dict.

        Returns:
            The immutable AuditRecord that was appended.
        """
        rec = AuditRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            principal=principal,
            resource=resource,
            action=action,
            result=result,
            event=event,
            details=details or {},
        )
        self._records.append(rec)

        # Cap memory usage
        if len(self._records) > self._MAX_RECORDS:
            self._records = self._records[-self._MAX_RECORDS:]

        _log.debug("Audit: %s %s %s %s", principal, action, resource, result)
        return rec

    def record_event(
        self,
        event: str,
        principal: str,
        resource: str,
        action: str,
        result: str,
        details: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """Convenience method: record with explicit event name first."""
        return self.record(principal, resource, action, result, event=event, details=details)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_by_principal(
        self,
        principal: str,
        limit: int = 100,
    ) -> list[AuditRecord]:
        """Return records for a given principal, newest first."""
        matches = [r for r in reversed(self._records) if r.principal == principal]
        return matches[:limit]

    def query_by_resource(
        self,
        resource: str,
        limit: int = 100,
    ) -> list[AuditRecord]:
        """Return records for a given resource, newest first."""
        matches = [r for r in reversed(self._records) if r.resource == resource]
        return matches[:limit]

    def query_by_time_range(
        self,
        start: str,
        end: str,
        limit: int = 100,
    ) -> list[AuditRecord]:
        """Return records within [start, end] ISO-format time range."""
        matches = [r for r in reversed(self._records) if start <= r.timestamp <= end]
        return matches[:limit]

    def query(
        self,
        principal: str | None = None,
        resource: str | None = None,
        action: str | None = None,
        result: str | None = None,
        limit: int = 100,
    ) -> list[AuditRecord]:
        """Return records matching any combination of filters, newest first."""
        results: list[AuditRecord] = []
        for r in reversed(self._records):
            if principal is not None and r.principal != principal:
                continue
            if resource is not None and r.resource != resource:
                continue
            if action is not None and r.action != action:
                continue
            if result is not None and r.result != result:
                continue
            results.append(r)
            if len(results) >= limit:
                break
        return results

    # ------------------------------------------------------------------
    # Export / Stats
    # ------------------------------------------------------------------

    def export_json(self, filepath: str) -> int:
        """Export all records as newline-delimited JSON (NDJSON).

        Returns the number of records written.
        """
        with open(filepath, "w") as f:
            for rec in self._records:
                f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
        _log.info("Audit log exported: %d records -> %s", len(self._records), filepath)
        return len(self._records)

    def stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        principals: set[str] = set()
        resources: set[str] = set()
        actions: dict[str, int] = {}
        results: dict[str, int] = {}

        for r in self._records:
            principals.add(r.principal)
            resources.add(r.resource)
            actions[r.action] = actions.get(r.action, 0) + 1
            results[r.result] = results.get(r.result, 0) + 1

        return {
            "total_records": len(self._records),
            "unique_principals": len(principals),
            "unique_resources": len(resources),
            "action_counts": actions,
            "result_counts": results,
        }

    @property
    def count(self) -> int:
        """Total number of audit records."""
        return len(self._records)

    def clear(self) -> None:
        """Clear all records (use with caution)."""
        self._records.clear()


__all__ = [
    "AuditLogger",
    "AuditRecord",
]
