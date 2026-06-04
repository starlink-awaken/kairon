"""CLI entry point for EU (Energy Unit) accounting.

Merged from eu-pricing package into kaironcloud-billing pricing subpackage.
"""

from __future__ import annotations

import argparse
import json
import sys

from kaironcloud_billing.pricing.eu_ledger import DEFAULT_PRICING, EULedger


def cmd_balance(args: argparse.Namespace) -> int:
    """Query EU balance for a caller."""
    ledger = EULedger(agora_endpoint=args.endpoint)
    balance = ledger.check_balance(args.caller)

    if args.json:
        print(json.dumps({
            "caller": balance.caller,
            "balance": balance.balance,
            "limit": balance.limit,
            "blocked": balance.blocked,
        }, indent=2, ensure_ascii=False))
    else:
        status = "blocked" if balance.blocked else "ok"
        print(f"Caller:    {balance.caller}")
        print(f"Balance:   {balance.balance} EU")
        print(f"Limit:     {balance.limit} EU")
        print(f"Status:    {status}")

    return 0


def cmd_consume(args: argparse.Namespace) -> int:
    """Consume EU for a pipeline operation."""
    ledger = EULedger(agora_endpoint=args.endpoint)
    tx = ledger.consume(args.caller, args.operation)

    if args.json:
        print(json.dumps({
            "caller": tx.caller,
            "operation": tx.operation,
            "cost": tx.cost,
            "balance_after": tx.balance_after,
            "success": tx.success,
            "error": tx.error,
        }, indent=2, ensure_ascii=False))
    else:
        icon = "+" if tx.success else "-"
        print(f"{icon} {tx.operation}")
        print(f"   Cost:          {tx.cost} EU")
        print(f"   Balance after:  {tx.balance_after} EU")
        if tx.error:
            print(f"   Error:         {tx.error}")

    return 0 if tx.success else 1


def cmd_pricing(args: argparse.Namespace) -> int:
    """Show current EU pricing table."""
    if args.json:
        print(json.dumps(DEFAULT_PRICING, indent=2, ensure_ascii=False))
    else:
        print("EU Pricing Table:")
        print(f"{'Operation':<30} {'Cost (EU)':>10}")
        print("-" * 42)
        for op, cost in sorted(DEFAULT_PRICING.items(), key=lambda x: -x[1]):
            print(f"{op:<30} {cost:>10}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kaironcloud-billing-pricing",
        description="EU (Energy Unit) virtual resource accounting — L2 capability layer",
    )
    parser.add_argument("--endpoint", "-e", default="http://localhost:7430", help="Agora endpoint")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    sub = parser.add_subparsers(dest="command")

    p_bal = sub.add_parser("balance", help="Query EU balance")
    p_bal.add_argument("caller", nargs="?", default="kairon", help="Caller identifier (default: kairon)")
    p_bal.set_defaults(func=cmd_balance)

    p_con = sub.add_parser("consume", help="Consume EU")
    p_con.add_argument("caller", nargs="?", default="kairon", help="Caller identifier (default: kairon)")
    p_con.add_argument("operation", default="kronos_ingest", nargs="?", help="Operation name")
    p_con.set_defaults(func=cmd_consume)

    p_pr = sub.add_parser("pricing", help="Show EU pricing table")
    p_pr.set_defaults(func=cmd_pricing)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        return args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
