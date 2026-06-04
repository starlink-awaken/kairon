"""Tests for reputation — ReputationLedger with in-memory SQLite."""

import time

from eu_pricing.reputation import (
    CIRCUIT_BREAK_DURATION,
    ReputationLedger,
)


class TestReputationLedger:
    """Tests for ReputationLedger using in-memory SQLite."""

    def setup_method(self):
        self.ledger = ReputationLedger(db_path=":memory:")

    def test_default_reputation_for_unknown_node(self):
        """get_reputation for an unknown node should return 0.5."""
        rep = self.ledger.get_reputation("node-unknown")
        assert rep == 0.5

    def test_report_success_increases_reputation(self):
        """Reporting a successful outcome should increase reputation above 0.5."""
        rep = self.ledger.report_outcome("node-1", success=True, quality=0.8)
        # success_rate = 1/1 = 1.0, avg_quality = 0.8
        # rep = (1.0 * 0.7) + (0.8 * 0.3) = 0.7 + 0.24 = 0.94
        assert rep == 0.94

    def test_report_failure_decreases_reputation(self):
        """Reporting a failed outcome should decrease reputation below 0.5."""
        rep = self.ledger.report_outcome("node-2", success=False, quality=0.0)
        # success_rate = 0/1 = 0.0, avg_quality = 0.0 (completed=0)
        # avg_quality = 0.5 (fallback when completed == 0)
        # rep = (0.0 * 0.7) + (0.5 * 0.3) = 0.15
        assert rep == 0.15

    def test_report_multiple_outcomes(self):
        """Multiple reports should compute SMA-based reputation correctly."""
        self.ledger.report_outcome("node-3", success=True, quality=0.9)
        rep = self.ledger.report_outcome("node-3", success=True, quality=0.7)
        # After 2 successes: success_rate = 2/2 = 1.0, avg_quality = (0.9+0.7)/2 = 0.8
        # rep = (1.0 * 0.7) + (0.8 * 0.3) = 0.7 + 0.24 = 0.94
        assert rep == 0.94

    def test_report_mixed_outcomes(self):
        """Mixed success/failure should produce intermediate reputation."""
        self.ledger.report_outcome("node-4", success=True, quality=0.8)
        rep = self.ledger.report_outcome("node-4", success=False, quality=0.0)
        # After 2: attempted=2, completed=1, quality_sum=0.8
        # success_rate = 1/2 = 0.5, avg_quality = 0.8/1 = 0.8
        # rep = (0.5 * 0.7) + (0.8 * 0.3) = 0.35 + 0.24 = 0.59
        assert rep == 0.59

    def test_reputation_clamped(self):
        """Reputation should be clamped to [0.0, 1.0]."""
        rep = self.ledger.report_outcome("node-5", success=False, quality=0.0)
        assert rep >= 0.0
        # Verify max clamping by reporting many successful outcomes
        for _ in range(50):
            self.ledger.report_outcome("node-5", success=True, quality=1.0)
        rep = self.ledger.get_reputation("node-5")
        assert rep <= 1.0

    def test_automatic_circuit_breaker_on_low_reputation(self):
        """When reputation drops below threshold, circuit should trip automatically."""
        self.ledger.report_outcome("node-6", success=False, quality=0.0)
        # After 1 failure: rep should be 0.15 < 0.3 → circuit tripped
        assert self.ledger.is_node_circuit_open("node-6") is True

    def test_circuit_not_tripped_for_acceptable_reputation(self):
        """A node with good reputation should not have its circuit tripped."""
        self.ledger.report_outcome("node-7", success=True, quality=0.9)
        assert self.ledger.is_node_circuit_open("node-7") is False

    def test_reset_circuit_manually(self):
        """Manually resetting a circuit should close it."""
        self.ledger.report_outcome("node-8", success=False, quality=0.0)
        assert self.ledger.is_node_circuit_open("node-8") is True
        self.ledger.reset_circuit("node-8")
        assert self.ledger.is_node_circuit_open("node-8") is False

    def test_trip_circuit_directly(self):
        """trip_circuit should mark the node as circuit-open."""
        self.ledger.report_outcome("node-9", success=True, quality=0.8)
        assert self.ledger.is_node_circuit_open("node-9") is False
        self.ledger.trip_circuit("node-9", reason="manual test")
        assert self.ledger.is_node_circuit_open("node-9") is True

    def test_auto_reset_after_break_duration(self, monkeypatch):
        """After CIRCUIT_BREAK_DURATION passes, circuit should auto-reset."""
        self.ledger.report_outcome("node-10", success=False, quality=0.0)
        assert self.ledger.is_node_circuit_open("node-10") is True

        # Simulate time passing beyond break duration
        future = time.time() + CIRCUIT_BREAK_DURATION + 60
        monkeypatch.setattr(time, "time", lambda: future)

        assert self.ledger.is_node_circuit_open("node-10") is False

    def test_apply_positive_feedback(self):
        """Positive feedback should increase reputation."""
        self.ledger.report_outcome("node-11", success=True, quality=0.5)
        rep_before = self.ledger.get_reputation("node-11")
        new_rep = self.ledger.apply_feedback("node-11", is_positive=True)
        assert new_rep > rep_before

    def test_apply_negative_feedback(self):
        """Negative feedback should decrease reputation."""
        self.ledger.report_outcome("node-12", success=True, quality=0.8)
        rep_before = self.ledger.get_reputation("node-12")
        new_rep = self.ledger.apply_feedback("node-12", is_positive=False)
        assert new_rep < rep_before

    def test_apply_feedback_on_new_node(self):
        """Feedback on an unknown node should initialize a default reputation."""
        rep = self.ledger.apply_feedback("node-new-positive", is_positive=True)
        # current_rep = 0.55, delta = 0.15 * 0.55 * (1-0.55) = 0.037125
        # new = 0.55 + 0.037125 = 0.587125
        assert rep == 0.587125

        rep = self.ledger.apply_feedback("node-new-negative", is_positive=False)
        # current_rep = 0.45, delta = 0.15 * 0.45 * (1-0.45) = 0.037125
        # new = 0.45 - 0.037125 = 0.412875
        assert rep == 0.412875

    def test_detect_anomalies_insufficient_data(self):
        """detect_anomalies should return empty list with < 4 nodes."""
        self.ledger.report_outcome("node-a", success=True, quality=0.5)
        self.ledger.report_outcome("node-b", success=True, quality=0.5)
        self.ledger.report_outcome("node-c", success=True, quality=0.5)
        assert self.ledger.detect_anomalies() == []

    def test_detect_anomalies_with_enough_data(self):
        """detect_anomalies should identify outlier nodes with IQR."""
        for i in range(8):
            self.ledger.report_outcome(f"normal-{i}", success=True, quality=0.5 + i * 0.05)
        self.ledger.report_outcome("outlier-low", success=False, quality=0.0)
        anomalies = self.ledger.detect_anomalies()
        assert "outlier-low" in anomalies

    def test_list_top_nodes_ordering(self):
        """list_top_nodes should return nodes ordered by reputation descending."""
        self.ledger.report_outcome("high", success=True, quality=1.0)
        self.ledger.report_outcome("low", success=False, quality=0.0)
        self.ledger.report_outcome("medium", success=True, quality=0.5)
        top = self.ledger.list_top_nodes(limit=3)
        assert top[0]["node_id"] == "high"
        assert top[-1]["node_id"] == "low"

    def test_new_node_not_circuit_open(self):
        """An unknown node should have its circuit closed by default."""
        assert self.ledger.is_node_circuit_open("never-seen") is False


class TestReputationDecay:
    """Tests for ReputationLedger time decay in get_reputation."""

    def setup_method(self):
        self.ledger = ReputationLedger(db_path=":memory:")

    def test_get_reputation_applies_time_decay(self, monkeypatch):
        """get_reputation should apply exponential decay based on elapsed time."""
        import math

        from eu_pricing.reputation import TIME_DECAY_LAMBDA

        self.ledger.report_outcome("node-decay", success=True, quality=1.0)
        # After report, reputation = (1.0 * 0.7) + (1.0 * 0.3) = 1.0
        rep_fresh = self.ledger.get_reputation("node-decay")
        assert rep_fresh == 1.0

        # Simulate 30 days passing
        future = time.time() + 86400 * 30  # 30 days in seconds
        monkeypatch.setattr(time, "time", lambda: future)

        rep_decayed = self.ledger.get_reputation("node-decay")
        # decayed = 1.0 * exp(-1e-6 * 86400*30) = exp(-2.592) ≈ 0.0749
        expected_decay = math.exp(-TIME_DECAY_LAMBDA * 86400 * 30)
        assert rep_decayed < 1.0
        assert abs(rep_decayed - expected_decay) < 1e-6

    def test_get_reputation_long_inactivity(self, monkeypatch):
        """After very long inactivity, reputation should approach zero."""
        self.ledger.report_outcome("node-old", success=True, quality=1.0)

        # Simulate 10 years passing
        future = time.time() + 86400 * 365 * 10
        monkeypatch.setattr(time, "time", lambda: future)

        rep = self.ledger.get_reputation("node-old")
        assert rep < 0.01  # Nearly decayed to zero

    def test_get_reputation_immediate_no_decay(self):
        """get_reputation should not decay within seconds of update."""
        self.ledger.report_outcome("node-now", success=True, quality=1.0)
        rep = self.ledger.get_reputation("node-now")
        assert rep == 1.0

    def test_get_reputation_clamped_above_zero(self, monkeypatch):
        """Decayed reputation should not go below 0.0."""
        self.ledger.report_outcome("node-clamp", success=True, quality=0.1)

        # Simulate extreme time
        future = time.time() + 86400 * 365 * 100  # 100 years
        monkeypatch.setattr(time, "time", lambda: future)

        rep = self.ledger.get_reputation("node-clamp")
        assert 0.0 <= rep <= 1.0
