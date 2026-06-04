"""Tests for energy_model — extracted from SharedBrain D_Economy."""

from eu_pricing.energy_model import DEFAULT_PRICING, EnergyBudget, EnergyEntry, ResourceType


def test_budget_initial_balance():
    budget = EnergyBudget(caller_id="test-caller", limit=1000.0)
    assert budget.balance == 1000.0
    assert budget.consumed == 0.0


def test_budget_can_afford():
    budget = EnergyBudget(caller_id="test", limit=100.0)
    assert budget.can_afford(50.0)
    assert not budget.can_afford(200.0)


def test_budget_consume_success():
    budget = EnergyBudget(caller_id="test", limit=100.0)
    entry = budget.consume("test_op", 30.0, idempotency_key="ik-001")
    assert entry is not None
    assert entry.cost == 30.0
    assert budget.balance == 70.0


def test_budget_consume_insufficient():
    budget = EnergyBudget(caller_id="test", limit=50.0)
    entry = budget.consume("test_op", 100.0)
    assert entry is None
    assert budget.balance == 50.0


def test_energy_entry_to_dict():
    entry = EnergyEntry(
        caller_id="test",
        operation="minerva_research",
        cost=10.0,
        balance_before=100.0,
        balance_after=90.0,
    )
    d = entry.to_dict()
    assert d["caller_id"] == "test"
    assert d["cost"] == 10.0


def test_resource_type_enum():
    assert ResourceType.EU.value == "eu"
    assert ResourceType.NECTAR.value == "nectar"
    assert ResourceType.QUOTA.value == "quota"


def test_default_pricing_has_expected_entries():
    assert DEFAULT_PRICING["minerva_research"] == 10.0
    assert DEFAULT_PRICING["kronos_ingest"] == 1.0
    assert DEFAULT_PRICING["agora_route"] == 0.5
