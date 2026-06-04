"""Tests for kairon_lib.audit_trail — AuditTrail."""

import pytest
from kairon_lib.audit_trail import (
    AuditTrail,
    AuditEntry,
    AuditSeverity,
    OperationType,
    ComplianceReport,
)


class TestAuditTrail:
    """Tests for AuditTrail."""

    @pytest.fixture
    def trail(self, tmp_path):
        db = str(tmp_path / "test_audit.db")
        return AuditTrail(db_path=db)

    def test_log_and_get(self, trail):
        entry = trail.log_operation(
            OperationType.POLICY_CREATED,
            actor="@Prime",
            target="policy/rbac",
            changes={"role": "admin", "effect": "allow"},
            severity=AuditSeverity.INFO,
        )
        assert entry.id is not None
        assert entry.operation_type == OperationType.POLICY_CREATED
        assert entry.actor == "@Prime"
        assert entry.target == "policy/rbac"
        assert entry.changes["role"] == "admin"
        assert entry.severity == AuditSeverity.INFO

    def test_get_entry_by_id(self, trail):
        entry = trail.log_operation(
            OperationType.VOTE_CAST, actor="@Builder", target="rfc/001", changes={"vote": "approve"}
        )
        fetched = trail.get_entry(entry.id)
        assert fetched is not None
        assert fetched.id == entry.id
        assert fetched.actor == "@Builder"

    def test_get_nonexistent_entry(self, trail):
        assert trail.get_entry("ghost-id") is None

    def test_get_history_by_target(self, trail):
        trail.log_operation(OperationType.POLICY_UPDATED, actor="@Sage", target="policy/rbac", changes={"x": "1"})
        trail.log_operation(OperationType.POLICY_UPDATED, actor="@Devil", target="policy/rbac", changes={"y": "2"})
        trail.log_operation(OperationType.POLICY_CREATED, actor="@Prime", target="policy/other", changes={"z": "3"})

        history = trail.get_history(target="policy/rbac")
        assert len(history) == 2

    def test_get_history_by_actor(self, trail):
        trail.log_operation(OperationType.POLICY_EXECUTED, actor="@Builder", target="t/1", changes={"a": 1})
        trail.log_operation(OperationType.POLICY_EXECUTED, actor="@Builder", target="t/2", changes={"b": 2})
        trail.log_operation(OperationType.VOTE_CAST, actor="@Sage", target="t/3", changes={"c": 3})

        history = trail.get_history(actor="@Builder")
        assert len(history) == 2

    def test_get_history_empty(self, trail):
        assert trail.get_history() == []

    def test_search_entries(self, trail):
        trail.log_operation(
            OperationType.PERMISSION_GRANTED, actor="@Prime", target="res/doc", changes={"role": "reader"}
        )
        trail.log_operation(
            OperationType.PERMISSION_REVOKED, actor="@Prime", target="res/doc", changes={"role": "reader"}
        )
        results = trail.search_entries("reader")
        assert len(results) == 2

    def test_search_entries_no_match(self, trail):
        trail.log_operation(OperationType.CUSTOM, actor="@Bot", target="sys/log", changes={"msg": "hello"})
        assert trail.search_entries("nonexistent") == []

    def test_generate_report(self, trail):
        for i in range(5):
            trail.log_operation(
                OperationType.POLICY_CREATED,
                actor="@Builder" if i % 2 == 0 else "@Sage",
                target=f"policy/{i}",
                changes={"idx": i},
            )
        report = trail.generate_report()
        assert isinstance(report, ComplianceReport)
        assert report.total_entries == 5
        assert report.operation_counts.get("policy_created", 0) == 5

    def test_generate_report_empty(self, trail):
        report = trail.generate_report()
        assert report.total_entries == 0
        assert report.operation_counts == {}

    def test_purge_old_entries(self, trail):
        trail.log_operation(OperationType.CUSTOM, actor="@Cleaner", target="old/data", changes={"keep": False})
        trail.purge_old_entries(days=0)
        assert trail.get_history() == []

    def test_log_with_metadata_and_correlation(self, trail):
        entry = trail.log_operation(
            OperationType.CONSENSUS_REACHED,
            actor="@Committee",
            target="rfc/042",
            changes={"result": "approved"},
            severity=AuditSeverity.CRITICAL,
            metadata={"voters": 5},
            correlation_id="corr-123",
        )
        assert entry.severity == AuditSeverity.CRITICAL
        assert entry.metadata == {"voters": 5}
        assert entry.correlation_id == "corr-123"

    def test_severity_filter_in_report(self, trail):
        trail.log_operation(OperationType.AUTO_EXECUTED, actor="@System", target="t/1", changes={})
        trail.log_operation(
            OperationType.AUTO_EXECUTED,
            actor="@System",
            target="t/2",
            changes={},
            severity=AuditSeverity.ERROR,
        )
        report = trail.generate_report()
        assert report.total_entries == 2
        assert len(report.critical_events) >= 1
