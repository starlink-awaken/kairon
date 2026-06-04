"""Tests for optimizer — EnergyOptimizer and budget management."""

from eu_pricing.optimizer import Budget, CostEstimate, EnergyOptimizer, Strategy


class TestStrategy:
    """Tests for Strategy enum."""

    def test_values(self):
        assert Strategy.MINIMIZE_COST.value == "minimize_cost"
        assert Strategy.MAXIMIZE_SPEED.value == "maximize_speed"
        assert Strategy.BALANCED.value == "balanced"

    def test_is_string_enum(self):
        assert isinstance(Strategy.MINIMIZE_COST, str)


class TestCostEstimate:
    """Tests for CostEstimate dataclass."""

    def test_default_confidence(self):
        estimate = CostEstimate(operation="llm_query", estimated_eu=2.0)
        assert estimate.confidence == 0.8

    def test_default_factors(self):
        estimate = CostEstimate(operation="llm_query", estimated_eu=2.0)
        assert estimate.factors == {}


class TestBudget:
    """Tests for Budget dataclass."""

    def test_available_no_reservations(self):
        budget = Budget(agent_id="a1", limit=100.0)
        assert budget.available == 100.0

    def test_available_with_spent(self):
        budget = Budget(agent_id="a1", limit=100.0, spent=30.0)
        assert budget.available == 70.0

    def test_available_with_spent_and_reserved(self):
        budget = Budget(agent_id="a1", limit=100.0, spent=30.0, reserved=20.0)
        assert budget.available == 50.0

    def test_available_no_negative(self):
        budget = Budget(agent_id="a1", limit=10.0, spent=50.0)
        assert budget.available == 0.0

    def test_usage_pct(self):
        budget = Budget(agent_id="a1", limit=200.0, spent=50.0, reserved=30.0)
        assert round(budget.usage_pct, 1) == 40.0

    def test_usage_pct_zero_limit(self):
        """Should not divide by zero."""
        budget = Budget(agent_id="a1", limit=0.0)
        assert budget.usage_pct == 0.0


class TestEnergyOptimizer:
    """Tests for EnergyOptimizer budget management and cost estimation."""

    def setup_method(self):
        self.optimizer = EnergyOptimizer()

    def test_default_cost_model(self):
        """Default cost model should have expected entries."""
        assert self.optimizer._cost_model["kos_search"] == 3.0
        assert self.optimizer._cost_model["minerva_research"] == 10.0
        assert self.optimizer._cost_model["llm_query"] == 2.0

    def test_set_budget_new(self):
        """set_budget should create a new budget."""
        self.optimizer.set_budget("agent-1", limit=500.0)
        budget = self.optimizer.get_budget("agent-1")
        assert budget.limit == 500.0

    def test_set_budget_update(self):
        """set_budget should update an existing budget's limit."""
        self.optimizer.set_budget("agent-2", limit=100.0)
        self.optimizer.set_budget("agent-2", limit=200.0)
        budget = self.optimizer.get_budget("agent-2")
        assert budget.limit == 200.0

    def test_get_budget_creates_default(self):
        """get_budget for unknown agent should create a default budget."""
        budget = self.optimizer.get_budget("agent-new")
        assert budget.limit == 1000.0
        assert budget.spent == 0.0

    def test_estimate_cost_known_operation(self):
        """estimate_cost for a known operation should use its base cost."""
        estimate = self.optimizer.estimate_cost("llm_query")
        assert estimate.estimated_eu == 2.0
        assert estimate.operation == "llm_query"

    def test_estimate_cost_unknown_operation(self):
        """estimate_cost for an unknown operation should default to 5.0."""
        estimate = self.optimizer.estimate_cost("unknown_op")
        assert estimate.estimated_eu == 5.0

    def test_estimate_cost_with_complexity(self):
        """complexity should scale the estimate."""
        estimate = self.optimizer.estimate_cost("llm_query", complexity=2.0)
        # base=2.0, complexity=2.0, size=1, urgency=1.0
        # estimated = 2.0 * 2.0 * 1 * 1.0 = 4.0
        assert estimate.estimated_eu == 4.0

    def test_estimate_cost_with_size(self):
        """Size should multiply the estimate."""
        estimate = self.optimizer.estimate_cost("llm_query", complexity=1.0, size=3)
        # base=2.0, complexity=1.0, size=3, urgency=1.0
        # estimated = 2.0 * 1.0 * 3 * 1.0 = 6.0
        assert estimate.estimated_eu == 6.0

    def test_estimate_cost_with_urgency(self):
        """Urgency factor should increase the estimate."""
        estimate = self.optimizer.estimate_cost("llm_query", urgency=0.5)
        # base=2.0, urgency_factor = 1.0 + 0.5*0.5 = 1.25
        # estimated = 2.0 * 1.0 * 1 * 1.25 = 2.5
        assert estimate.estimated_eu == 2.5

    def test_estimate_cost_rounding(self):
        """Estimated cost should be rounded to 2 decimal places."""
        estimate = self.optimizer.estimate_cost("code_analysis", complexity=1.3, size=2)
        # base=5.0, complexity=1.3, size=2, urgency=1.0
        # estimated = 5.0 * 1.3 * 2 * 1.0 = 13.0
        assert estimate.estimated_eu == 13.0

    def test_estimate_cost_factors_included(self):
        """The factors used in estimation should be included in the result."""
        estimate = self.optimizer.estimate_cost("llm_query", complexity=2.0, size=3, urgency=0.5)
        assert estimate.factors["base"] == 2.0
        assert estimate.factors["complexity"] == 2.0
        assert estimate.factors["size"] == 3
        assert estimate.factors["urgency"] == 1.25

    def test_can_afford_sufficient(self):
        """can_afford should return True when budget is sufficient."""
        self.optimizer.set_budget("agent-13", limit=100.0)
        affordable, estimate = self.optimizer.can_afford("agent-13", "llm_query")
        # llm_query base = 2.0, budget available = 100.0
        assert affordable is True
        assert estimate.estimated_eu == 2.0

    def test_can_afford_insufficient(self):
        """can_afford should return False when budget is insufficient."""
        self.optimizer.set_budget("agent-14", limit=1.0)
        affordable, estimate = self.optimizer.can_afford("agent-14", "minerva_research")
        # minerva_research base = 10.0, budget available = 1.0
        assert affordable is False
        assert estimate.estimated_eu == 10.0

    def test_reserve_success(self):
        """reserve should deduct from available budget."""
        self.optimizer.set_budget("agent-15", limit=100.0)
        result = self.optimizer.reserve("agent-15", 30.0)
        assert result is True
        budget = self.optimizer.get_budget("agent-15")
        assert budget.reserved == 30.0
        assert budget.available == 70.0

    def test_reserve_failure(self):
        """reserve should fail when insufficient available budget."""
        self.optimizer.set_budget("agent-16", limit=10.0)
        result = self.optimizer.reserve("agent-16", 50.0)
        assert result is False

    def test_commit_spends_reserved(self):
        """commit should move reserved to spent."""
        self.optimizer.set_budget("agent-17", limit=100.0)
        self.optimizer.reserve("agent-17", 40.0)
        self.optimizer.commit("agent-17", 40.0)
        budget = self.optimizer.get_budget("agent-17")
        assert budget.spent == 40.0
        assert budget.reserved == 0.0

    def test_commit_handles_over_commitment(self):
        """commit should not allow negative reserved."""
        self.optimizer.set_budget("agent-18", limit=100.0)
        self.optimizer.reserve("agent-18", 30.0)
        self.optimizer.commit("agent-18", 50.0)  # commit more than reserved
        budget = self.optimizer.get_budget("agent-18")
        assert budget.reserved == 0.0  # max(0, 30-50) = 0
        assert budget.spent == 50.0

    def test_commit_triggers_alert_at_80_percent(self):
        """commit should add an alert when budget usage exceeds 80%."""
        self.optimizer.set_budget("agent-19", limit=100.0)
        self.optimizer.commit("agent-19", 85.0)
        budget = self.optimizer.get_budget("agent-19")
        assert len(budget.alerts) >= 1
        assert "Budget at 85%" in budget.alerts[0]

    def test_get_usage_trend_insufficient_data(self):
        """get_usage_trend should return 'insufficient_data' with < 5 entries."""
        for _ in range(4):
            self.optimizer.commit("agent-20", 10.0)
        assert self.optimizer.get_usage_trend("agent-20") == "insufficient_data"

    def test_get_usage_trend_stable(self):
        """Stable usage should be detected."""
        for _ in range(10):
            self.optimizer.commit("agent-21", 10.0)
        assert self.optimizer.get_usage_trend("agent-21") == "stable"

    def test_get_usage_trend_increasing(self):
        """Increasing usage trend should be detected."""
        for i in range(10):
            self.optimizer.commit("agent-22", 5.0 + i * 2.0)
        assert self.optimizer.get_usage_trend("agent-22") == "increasing"

    def test_get_usage_trend_decreasing(self):
        """Decreasing usage trend should be detected."""
        for i in range(10):
            self.optimizer.commit("agent-23", 20.0 - i * 2.0)
        assert self.optimizer.get_usage_trend("agent-23") == "decreasing"

    def test_reserve_commit_workflow(self):
        """Full reserve → commit workflow should track budget accurately."""
        self.optimizer.set_budget("agent-24", limit=200.0)
        assert self.optimizer.reserve("agent-24", 50.0) is True
        assert self.optimizer.reserve("agent-24", 30.0) is True
        budget = self.optimizer.get_budget("agent-24")
        assert budget.reserved == 80.0
        assert budget.available == 120.0

        self.optimizer.commit("agent-24", 50.0)
        budget = self.optimizer.get_budget("agent-24")
        assert budget.reserved == 30.0
        assert budget.spent == 50.0
        assert budget.available == 120.0
