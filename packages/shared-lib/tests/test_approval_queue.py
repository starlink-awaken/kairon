"""Tests for kairon_lib.approval_queue — ApprovalQueue, ApprovalItem, ApprovalResult, RiskLevel."""

import pytest
from kairon_lib.approval_queue import (
    ApprovalItem,
    ApprovalQueue,
    RiskLevel,
)


class TestRiskLevel:
    def test_from_value_valid(self):
        assert RiskLevel.from_value("high") == RiskLevel.HIGH
        assert RiskLevel.from_value("  LOW  ") == RiskLevel.LOW
        assert RiskLevel.from_value("CRITICAL") == RiskLevel.CRITICAL

    def test_from_value_none_defaults_to_medium(self):
        assert RiskLevel.from_value(None) == RiskLevel.MEDIUM

    def test_from_value_invalid_defaults_to_medium(self):
        assert RiskLevel.from_value("unknown") == RiskLevel.MEDIUM

class TestApprovalItem:
    def test_is_terminal(self):
        item = ApprovalItem(id="1", action={"type": "test"}, context={}, risk_level=RiskLevel.LOW)
        assert item.is_terminal() is False

    def test_to_dict(self):
        item = ApprovalItem(id="1", action={"type": "test"}, context={}, risk_level=RiskLevel.HIGH)
        d = item.to_dict()
        assert d["id"] == "1"
        assert d["risk_level"] == "high"
        assert d["status"] == "pending"

class TestApprovalQueue:
    def setup_method(self):
        ApprovalQueue.reset_instance()

    def test_request_approval_creates_item(self):
        q = ApprovalQueue()
        item = q.request_approval(action={"type": "deploy"}, requester="alice")
        assert item.requester == "alice"
        assert item.status == "pending"
        assert item.risk_level == RiskLevel.MEDIUM

    def test_request_approval_with_context(self):
        q = ApprovalQueue()
        item = q.request_approval(
            action={"type": "delete_data"},
            context={"risk_level": "high"},
            requester="bob",
        )
        assert item.risk_level == RiskLevel.HIGH
        assert item.context.get("risk_level") == "high"

    def test_request_approval_auto_approves_low_risk(self):
        q = ApprovalQueue()
        item = q.request_approval(
            action={"type": "read_logs"},
            context={"risk_level": "low"},
        )
        assert item.status == "approved"
        assert item.approver == "system"

    def test_request_approval_raises_on_empty_action(self):
        q = ApprovalQueue()
        with pytest.raises(ValueError, match="non-empty dict"):
            q.request_approval(action={})

    def test_request_approval_raises_on_none_action(self):
        q = ApprovalQueue()
        with pytest.raises(ValueError, match="non-empty dict"):
            q.request_approval(action=None)

    def test_approve_success(self):
        q = ApprovalQueue()
        item = q.request_approval(action={"type": "test"})
        result = q.approve(item.id, approver="@Prime", reason="Looks good")
        assert result.success is True
        assert result.action == "approved"

    def test_approve_unknown_id(self):
        q = ApprovalQueue()
        result = q.approve("nonexistent", approver="@Prime")
        assert result.success is False

    def test_approve_already_terminal(self):
        q = ApprovalQueue()
        item = q.request_approval(action={"type": "test"}, context={"risk_level": "low"})
        result = q.approve(item.id, approver="@Prime")
        assert result.success is False  # already auto-approved

    def test_approve_raises_on_empty_id(self):
        q = ApprovalQueue()
        with pytest.raises(ValueError, match="non-empty string"):
            q.approve("", approver="@Prime")

    def test_approve_raises_on_empty_approver(self):
        q = ApprovalQueue()
        with pytest.raises(ValueError, match="non-empty string"):
            q.approve("some-id", approver="")

    def test_reject_success(self):
        q = ApprovalQueue()
        item = q.request_approval(action={"type": "test"}, requester="bob")
        result = q.reject(item.id, reason="Not ready", approver="@Prime")
        assert result.success is True
        assert result.action == "rejected"

    def test_reject_unknown_id(self):
        q = ApprovalQueue()
        result = q.reject("nonexistent", reason="nope", approver="@Prime")
        assert result.success is False

    def test_reject_raises_on_empty_reason(self):
        q = ApprovalQueue()
        with pytest.raises(ValueError, match="non-empty string"):
            q.reject("some-id", reason="", approver="@Prime")

    def test_get_pending(self):
        q = ApprovalQueue()
        q.request_approval(action={"type": "a"}, requester="alice")
        q.request_approval(action={"type": "b"}, requester="bob")
        pending = q.get_pending()
        assert len(pending) == 2

    def test_get_pending_filters_by_risk(self):
        q = ApprovalQueue()
        q.request_approval(action={"type": "a"}, context={"risk_level": "medium"})
        q.request_approval(action={"type": "b"}, context={"risk_level": "high"})
        high_pending = q.get_pending(risk_level=RiskLevel.HIGH)
        assert len(high_pending) == 1

    def test_get_pending_filters_by_requester(self):
        q = ApprovalQueue()
        q.request_approval(action={"type": "a"}, requester="alice")
        q.request_approval(action={"type": "b"}, requester="bob")
        alice_items = q.get_pending(requester="alice")
        assert len(alice_items) == 1

    def test_get_history(self):
        q = ApprovalQueue()
        item = q.request_approval(action={"type": "a"}, requester="alice")
        q.reject(item.id, reason="no", approver="@Prime")
        history = q.get_history()
        assert len(history) == 1

    def test_get_item_pending(self):
        q = ApprovalQueue()
        item = q.request_approval(action={"type": "test"})
        found = q.get_item(item.id)
        assert found is not None
        assert found.id == item.id

    def test_get_item_history(self):
        q = ApprovalQueue()
        item = q.request_approval(action={"type": "test"}, requester="alice")
        q.reject(item.id, reason="no", approver="@Prime")
        found = q.get_item(item.id)
        assert found is not None

    def test_get_item_nonexistent(self):
        q = ApprovalQueue()
        assert q.get_item("ghost") is None

    def test_restore_pending(self):
        q = ApprovalQueue()
        item = q.request_approval(action={"type": "test"}, requester="alice")
        q.reject(item.id, reason="no", approver="@Prime")
        restored = q.restore_pending(item.id)
        assert restored is True
        pending_item = q.get_item(item.id)
        assert pending_item.status == "pending"

    def test_restore_pending_nonexistent(self):
        q = ApprovalQueue()
        assert q.restore_pending("ghost") is False

    def test_get_queue_stats(self):
        q = ApprovalQueue()
        q.request_approval(action={"type": "a"}, requester="alice")
        stats = q.get_queue_stats()
        assert stats["pending_count"] >= 1
        assert "pending_by_risk" in stats

    def test_mark_vetoed(self):
        q = ApprovalQueue()
        item = q.request_approval(action={"type": "test"}, requester="alice")
        result = q.mark_vetoed(item.id, vetoer="@Prime", reason="Override")
        assert result.success is True
        assert result.action == "vetoed"

    def test_mark_vetoed_nonexistent(self):
        q = ApprovalQueue()
        result = q.mark_vetoed("ghost", vetoer="@Prime", reason="nope")
        assert result.success is False

    def test_cancel_all_pending(self):
        q = ApprovalQueue()
        q.request_approval(action={"type": "a"}, requester="alice")
        q.request_approval(action={"type": "b"}, requester="bob")
        count = q.cancel_all_pending(reason="Emergency", actor="system")
        assert count == 2
        assert len(q.get_pending()) == 0

    def test_effective_risk_level_escalates_high_blast(self):
        action = {"type": "test", "blast_radius": "global"}
        context = {"risk_level": "low"}
        level = ApprovalQueue._effective_risk_level(action, context)
        assert level == RiskLevel.HIGH

    def test_get_instance_singleton(self):
        ApprovalQueue.reset_instance()
        q1 = ApprovalQueue.get_instance()
        q2 = ApprovalQueue.get_instance()
        assert q1 is q2
