"""Tests for kairon_lib.approval_observability — ApprovalObservability."""

from kairon_lib.approval_observability import ApprovalObservability


class MockAuditTrail:
    def __init__(self):
        self.operations = []

    def log_operation(self, **kwargs):
        self.operations.append(kwargs)


class TestApprovalObservability:
    def test_emit_request_submitted(self):
        obs = ApprovalObservability()
        # Should not raise — EventBus is unavailable
        obs.emit_request_submitted(request_id="r1", request_type="delete", requester="alice")

    def test_emit_decision_recorded_approved(self):
        obs = ApprovalObservability()
        obs.emit_decision_recorded(request_id="r1", decision="approved", approver="bob")

    def test_emit_decision_recorded_denied(self):
        obs = ApprovalObservability()
        obs.emit_decision_recorded(request_id="r1", decision="denied", approver="bob")

    def test_log_decision_no_audit_trail(self):
        obs = ApprovalObservability(audit_trail=None)
        obs.log_decision(request_id="r1", decision="approved", reason="looks good", approver="bob")

    def test_log_decision_with_audit_trail(self):
        audit = MockAuditTrail()
        obs = ApprovalObservability(audit_trail=audit)
        obs.log_decision(request_id="r1", decision="approved", reason="all good", approver="alice")
        assert len(audit.operations) == 1
        op = audit.operations[0]
        assert op["operation_type"] == "decision.approved"
        assert op["actor"] == "alice"
        assert op["target"] == "r1"

    def test_log_decision_with_audit_trail_rejected(self):
        audit = MockAuditTrail()
        obs = ApprovalObservability(audit_trail=audit)
        obs.log_decision(request_id="r2", decision="rejected", reason="not ready", approver="charlie")
        assert len(audit.operations) == 1
        op = audit.operations[0]
        assert op["operation_type"] == "decision.rejected"
        assert op["changes"]["decision"] == "rejected"
        assert op["changes"]["reason"] == "not ready"

    def test_log_decision_audit_trail_error_does_not_raise(self):
        class BrokenAudit:
            def log_operation(self, **kwargs):
                raise RuntimeError("audit down")

        obs = ApprovalObservability(audit_trail=BrokenAudit())
        obs.log_decision(request_id="r1", decision="approved", reason="ok", approver="alice")
