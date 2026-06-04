"""Tests for CLI — argparse parsing and main entry point."""

import sys

import pytest
from eu_pricing.cli import main


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
    rc = main(["--json", "consume", "kairon", "test_op"])
    assert rc == 0


def test_main_handles_bad_subcommand():
    """main() with an invalid subcommand should be handled gracefully."""
    from io import StringIO

    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        rc = main(["nonexistent_command"])
        assert rc != 0
    finally:
        sys.stderr = old_stderr


def test_main_balance_normal():
    """main() balance subcommand should return 0 on success."""
    rc = main(["balance"])
    assert rc == 0
