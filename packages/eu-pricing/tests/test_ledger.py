from __future__ import annotations

from eu_pricing.ledger import EUBalance, EULedger


def test_consume_uses_operation_cost_when_balance_is_sufficient(monkeypatch) -> None:
    ledger = EULedger()
    captured: dict[str, object] = {}

    monkeypatch.setattr(ledger, "check_balance", lambda caller: EUBalance(caller=caller, balance=20))

    def fake_push(caller: str, cost: int, operation: str) -> dict[str, object]:
        captured.update(caller=caller, cost=cost, operation=operation)
        return {"ok": True}

    monkeypatch.setattr(ledger, "_push_consumption", fake_push)

    tx = ledger.consume("demo", "minerva_research")

    assert tx.success is True
    assert tx.cost == 10
    assert tx.balance_after == 10
    assert captured == {"caller": "demo", "cost": 10, "operation": "minerva_research"}


def test_consume_rejects_blocked_or_insufficient_balance_without_pushing(monkeypatch) -> None:
    ledger = EULedger()
    push_called = False

    monkeypatch.setattr(
        ledger,
        "check_balance",
        lambda caller: EUBalance(caller=caller, balance=1, blocked=True),
    )

    def fake_push(caller: str, cost: int, operation: str) -> dict[str, object]:
        nonlocal push_called
        push_called = True
        return {"ok": True}

    monkeypatch.setattr(ledger, "_push_consumption", fake_push)

    tx = ledger.consume("demo", "minerva_research")

    assert tx.success is False
    assert tx.balance_after == 1
    assert "Insufficient EU" in (tx.error or "")
    assert push_called is False


def test_consume_defaults_unknown_operation_cost_to_one(monkeypatch) -> None:
    ledger = EULedger()

    monkeypatch.setattr(ledger, "check_balance", lambda caller: EUBalance(caller=caller, balance=5))
    monkeypatch.setattr(ledger, "_push_consumption", lambda caller, cost, operation: {"ok": True})

    tx = ledger.consume("demo", "custom_operation")

    assert tx.success is True
    assert tx.cost == 1
    assert tx.balance_after == 4
