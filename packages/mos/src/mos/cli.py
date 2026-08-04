"""MOS CLI — write / recall / status."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mos.service import MemoryOS, default_memory_os_with_fixtures

# Process-local singleton for CLI dual-track continuity in one process
_OS: MemoryOS | None = None


def get_os() -> MemoryOS:
    global _OS
    if _OS is None:
        _OS = default_memory_os_with_fixtures()
    return _OS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mos", description="Memory OS control plane")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_write = sub.add_parser("write", help="Write a memory envelope")
    p_write.add_argument("--type", required=True, dest="mem_type")
    p_write.add_argument("--content", default=None)
    p_write.add_argument("--content-ref", default=None)
    p_write.add_argument("--confidence", type=float, default=0.8)
    p_write.add_argument("--json", action="store_true", help="Print JSON")

    p_recall = sub.add_parser("recall", help="Recall memories")
    p_recall.add_argument("query")
    p_recall.add_argument("--intent", default=None)
    p_recall.add_argument("--limit", type=int, default=10)
    p_recall.add_argument("--json", action="store_true")

    sub.add_parser("status", help="Control plane status")

    args = parser.parse_args(argv)
    mos = get_os()

    if args.cmd == "write":
        result = mos.write(
            {
                "type": args.mem_type,
                "content": args.content,
                "content_ref": args.content_ref,
                "confidence": args.confidence,
            }
        )
        out: dict[str, Any] = result.to_dict()
        print(json.dumps(out, ensure_ascii=False, indent=2 if args.json else None))
        return 0 if result.ok else 1

    if args.cmd == "recall":
        result = mos.recall(args.query, intent=args.intent, limit=args.limit)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2 if args.json else None))
        return 0

    if args.cmd == "status":
        print(json.dumps(mos.status(), ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
