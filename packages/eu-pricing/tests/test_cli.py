"""Tests for CLI — argparse parsing and main entry point."""

from unittest.mock import patch

import pytest
from eu_pricing.cli import main
from eu_pricing.ledger import EUTransaction


def test_main_no_args_shows_help():
    """Running main() without arguments should print help and return 0."""
    rc = main([])
    assert rc == 0


def test_pricing_command():
    """The 'pricing' subcommand should work independently of ledger."""
    rc = main(["pricing"])
    assert rc == 0


def test_pricing_json():
    """The 'pricing --json' subcommand should output JSON.

    Note: --json must come before the subcommand due to argparse behavior.
    """
    rc = main(["--json", "pricing"])
    assert rc == 0


def test_help_flag():
    """The --help flag should print help text."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_balance_command():
    """The 'balance' subcommand should work with EnergyLedger."""
    rc = main(["balance"])
    assert rc == 0


def test_consume_command():
    """The 'consume' subcommand should work with EnergyLedger."""
    with patch("eu_pricing.cli.EULedger.consume", return_value=EUTransaction(
        caller="kairon", operation="kronos_ingest", cost=1, balance_after=99, success=True,
    )):
        rc = main(["consume"])
    assert rc == 0


def test_balance_help():
    """The 'balance --help' should print help text."""
    with pytest.raises(SystemExit) as exc_info:
        main(["balance", "--help"])
    assert exc_info.value.code == 0


def test_consume_help():
    """The 'consume --help' should print help text."""
    with pytest.raises(SystemExit) as exc_info:
        main(["consume", "--help"])
    assert exc_info.value.code == 0


def test_pricing_help():
    """The 'pricing --help' should print help text."""
    with pytest.raises(SystemExit) as exc_info:
        main(["pricing", "--help"])
    assert exc_info.value.code == 0


def test_json_global_flag():
    """The --json global flag should be accepted before the subcommand."""
    rc = main(["--json", "pricing"])
    assert rc == 0


def test_endpoint_flag_before_subcommand():
    """The --endpoint global flag should be accepted before a subcommand."""
    rc = main(["--endpoint", "http://localhost:9999", "balance"])
    assert rc == 0


def test_endpoint_flag_json_balance():
    """Balance with --endpoint and --json should work."""
    rc = main(["--endpoint", "http://localhost:9999", "--json", "balance", "test-caller"])
    assert rc == 0


def test_consume_with_json():
    """Consume with --json flag should work."""
    with patch("eu_pricing.cli.EULedger.consume", return_value=EUTransaction(
        caller="kairon", operation="test_op", cost=1, balance_after=99, success=True,
    )):
        rc = main(["--json", "consume", "kairon", "test_op"])
    assert rc == 0


def test_main_handles_bad_subcommand():
    """main() with an invalid subcommand should be handled gracefully."""
    with pytest.raises(SystemExit) as exc_info:
        main(["nonexistent_command"])
    assert exc_info.value.code == 2


def test_main_balance_normal():
    """main() balance subcommand should return 0 on success."""
    rc = main(["balance"])
    assert rc == 0
