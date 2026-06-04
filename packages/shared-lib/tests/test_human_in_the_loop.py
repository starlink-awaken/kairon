"""Tests for kairon_lib.human_in_the_loop — HITL confirmation workflow."""

import time

import pytest
from kairon_lib.human_in_the_loop import ConfirmationRequest, HITLStatus, HumanInTheLoop


class TestHITLStatus:
    def test_values(self):
        assert HITLStatus.PENDING == "pending"
        assert HITLStatus.CONFIRMED == "confirmed"
        assert HITLStatus.REJECTED == "rejected"
        assert HITLStatus.TIMEOUT == "timeout"

class TestConfirmationRequest:
    def test_is_terminal_pending(self):
        req = ConfirmationRequest(request_id="r1", action={}, context={})
        assert req.is_terminal() is False

    def test_is_terminal_confirmed(self):
        req = ConfirmationRequest(request_id="r1", action={}, context={}, status=HITLStatus.CONFIRMED)
        assert req.is_terminal() is True

    def test_to_dict(self):
        req = ConfirmationRequest(request_id="r1", action={"type": "delete"}, context={"risk": "high"})
        d = req.to_dict()
        assert d["request_id"] == "r1"
        assert d["status"] == "pending"

class TestHumanInTheLoop:
    def setup_method(self):
        self.hitl = HumanInTheLoop()

    def test_request_confirmation_creates_pending(self):
        req = self.hitl.request_confirmation(
            action={"type": "delete_data", "target": "old"},
            context={"risk_level": "medium"},
            requester="alice",
        )
        assert req.status == HITLStatus.PENDING
        assert req.action["type"] == "delete_data"

    def test_request_confirmation_raises_on_empty_action(self):
        with pytest.raises(ValueError, match="non-empty dict"):
            self.hitl.request_confirmation(action={})

    def test_confirm_request_success(self):
        req = self.hitl.request_confirmation(action={"type": "test"})
        result = self.hitl.confirm_request(req.request_id, confirmer="@Prime")
        assert result is True
        confirmed = self.hitl.get_request(req.request_id)
        assert confirmed.status == HITLStatus.CONFIRMED
        assert confirmed.confirmed_by == "@Prime"

    def test_confirm_request_unknown_id(self):
        result = self.hitl.confirm_request("nonexistent")
        assert result is False

    def test_confirm_request_already_terminal(self):
        req = self.hitl.request_confirmation(action={"type": "test"})
        self.hitl.confirm_request(req.request_id)
        result = self.hitl.confirm_request(req.request_id)
        assert result is False

    def test_reject_request_success(self):
        req = self.hitl.request_confirmation(action={"type": "test"})
        result = self.hitl.reject_request(req.request_id, reason="Not safe", rejector="@Prime")
        assert result is True
        rejected = self.hitl.get_request(req.request_id)
        assert rejected.status == HITLStatus.REJECTED
        assert rejected.rejection_reason == "Not safe"

    def test_reject_request_unknown_id(self):
        result = self.hitl.reject_request("nonexistent", reason="nope")
        assert result is False

    def test_reject_request_raises_on_empty_reason(self):
        req = self.hitl.request_confirmation(action={"type": "test"})
        with pytest.raises(ValueError, match="non-empty string"):
            self.hitl.reject_request(req.request_id, reason="")

    def test_get_pending_requests(self):
        self.hitl.request_confirmation(action={"type": "a"}, context={"risk_level": "low"})
        self.hitl.request_confirmation(action={"type": "b"}, context={"risk_level": "low"})
        pending = self.hitl.get_pending_requests()
        assert len(pending) == 2

    def test_get_pending_requests_excludes_expired(self):
        self.hitl.request_confirmation(action={"type": "a"}, timeout_seconds=0)
        time.sleep(0.01)
        pending = self.hitl.get_pending_requests()
        assert len(pending) == 0

    def test_get_pending_requests_includes_expired_when_requested(self):
        self.hitl.request_confirmation(action={"type": "a"}, timeout_seconds=0)
        time.sleep(0.01)
        pending = self.hitl.get_pending_requests(include_expired=True)
        assert len(pending) >= 1

    def test_get_request_from_history(self):
        req = self.hitl.request_confirmation(action={"type": "test"})
        self.hitl.confirm_request(req.request_id)
        found = self.hitl.get_request(req.request_id)
        assert found is not None
        assert found.status == HITLStatus.CONFIRMED

    def test_get_request_nonexistent(self):
        assert self.hitl.get_request("ghost") is None

    def test_get_stats(self):
        self.hitl.request_confirmation(action={"type": "a"})
        self.hitl.request_confirmation(action={"type": "b"})
        stats = self.hitl.get_stats()
        assert stats["pending_count"] == 2
        assert stats["history_count"] == 0

    def test_get_stats_after_confirm(self):
        req = self.hitl.request_confirmation(action={"type": "test"})
        self.hitl.confirm_request(req.request_id)
        stats = self.hitl.get_stats()
        assert stats["pending_count"] == 0
        assert stats["history_count"] == 1

    def test_wait_for_confirmation_unknown_id(self):
        result = self.hitl.wait_for_confirmation("nonexistent", timeout_seconds=0)
        assert result is False

    def test_wait_for_confirmation_already_confirmed(self):
        """wait_for_confirmation only works on pending requests; use get_request for resolved ones."""
        req = self.hitl.request_confirmation(action={"type": "test"})
        self.hitl.confirm_request(req.request_id)
        # After confirm, request moves to history — wait can't find it
        result = self.hitl.wait_for_confirmation(req.request_id, timeout_seconds=0)
        assert result is False
        # But get_request can retrieve it
        resolved = self.hitl.get_request(req.request_id)
        assert resolved is not None
        assert resolved.status == HITLStatus.CONFIRMED

    def test_validate_access_always_true(self):
        assert self.hitl.validate_access("any", {}) is True

    def test_get_metadata(self):
        meta = self.hitl.get_metadata()
        assert meta["name"] == "HumanInTheLoop"
        assert meta["domain"] == "D-Governance"

    def test_get_registry_info(self):
        info = self.hitl.get_registry_info()
        assert info["bos_uri"] == "bos://governance/hitl"
        assert len(info["endpoints"]) == 4

    def test_request_confirmation_with_high_risk_approval_queue(self):
        # High risk should not raise even though ApprovalQueue is unavailable
        req = self.hitl.request_confirmation(
            action={"type": "delete"},
            context={"risk_level": "high"},
        )
        assert req.status == HITLStatus.PENDING
