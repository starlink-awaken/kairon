"""P49-simplify: 通用 stdio JSON-RPC serve helper (kairon 仓版, 跨仓复制自 omo.omo_stdio_rpc).

P49-W0 16 kairon 包 __main__.py + kairon-utils 仓共用此 helper.
P63-W0-D: 加 daemon_mode 参数 — launchd plist 没 pipe stdin, daemon 模式 EOF 时
sleep 30s 重试 (避免 KeepAlive 重启风暴), 正常模式立即 return 0.
"""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from typing import Any

DispatchFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def run_stdio_dispatch(
    dispatch_fn: DispatchFn,
    on_quit: Callable[[], None] | None = None,
    daemon_mode: bool = False,
) -> int:
    """读 stdin JSON 行, 调 dispatch_fn(action, args), 写 stdout JSON 行.

    daemon_mode=True: stdin EOF 时 sleep 30s + retry (launchd 没 pipe stdin 兼容).
    daemon_mode=False: stdin EOF 立即 return 0 (P49-W0 era 行为, 默认).
    """
    while True:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            if line == "QUIT":
                if on_quit is not None:
                    on_quit()
                return 0
            try:
                req = json.loads(line)
            except json.JSONDecodeError as exc:
                sys.stdout.write(
                    json.dumps({"status": "error", "error": f"json_decode: {exc}"}) + "\n"
                )
                sys.stdout.flush()
                continue
            action = req.get("action", "")
            args = req.get("args", {}) or {}
            try:
                result = dispatch_fn(action, args)
                resp = (
                    result
                    if isinstance(result, dict) and "status" in result
                    else {"status": "ok", "result": result}
                )
            except Exception as exc:
                resp = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
            sys.stdout.flush()
        # stdin EOF
        if not daemon_mode:
            return 0
        sys.stderr.write("[daemon] stdin EOF, sleep 30s then retry\n")
        sys.stderr.flush()
        time.sleep(30)


def run_stdio_main(
    serve_fn: Callable[[], int],
    argv: list[str] | None = None,
) -> int:
    """Minimal CLI wrapper for package-level stdio serve entry points."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        sys.stderr.write("Usage: python -m <package> serve\n")
        sys.stderr.write("Runs a stdio JSON-RPC loop for agora BOS dispatch.\n")
        return 0
    if argv[0] != "serve":
        sys.stderr.write(f"Unknown command: {argv[0]}\n")
        sys.stderr.write("Usage: python -m <package> serve\n")
        return 2
    if len(argv) > 1 and argv[1] in {"-h", "--help"}:
        sys.stderr.write("Usage: python -m <package> serve\n")
        sys.stderr.write("Reads JSON lines from stdin and writes JSON lines to stdout.\n")
        return 0
    return serve_fn()


__all__ = ["run_stdio_dispatch", "run_stdio_main", "DispatchFn"]
