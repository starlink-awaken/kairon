"""kairon/minerva stdio MCP server (POC).

读取 stdin 的 JSON 请求, 写入 stdout 的 JSON 响应.
战役 1 阶段: 进程可 spawn + alive 即可; 完整 MCP 协议 W4.5+.

调用: python -m minerva serve --action <action>
"""
from __future__ import annotations

import argparse
import json
import sys


def _serve(action: str) -> int:
    """POC stdio 协议: stdin JSON 行 → stdout JSON 行."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            err = {
                "status": "error",
                "service": "kairon-minerva",
                "action": action,
                "error": f"invalid_json: {exc}",
            }
            sys.stdout.write(json.dumps(err, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue
        resp = {
            "status": "ok",
            "service": "kairon-minerva",
            "action": action,
            "request_id": req.get("request_id", ""),
            "result": {
                "message": f"minerva {action} invoked",
                "echo_args": req.get("args", []),
            },
        }
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kairon-minerva")
    parser.add_argument("command", choices=["serve"], help="POC: only 'serve'")
    parser.add_argument("--action", required=True, help="research/...")
    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(args.action)
    return 1


if __name__ == "__main__":
    sys.exit(main())
