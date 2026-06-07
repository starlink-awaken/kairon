"""Kairon package __main__.py — stdio JSON-RPC serve mode (P48-W3 / P33-W4).

Usage:
  python -m <package>            # 包默认入口 (P33 时代 CLI)
  python -m <package> serve      # stdio JSON-RPC serve 模式 (供 agora daemon 派发)

协议 (P33-W4 stdio JSON-RPC 简化):
  - 客户端写: {"action": "X", "args": {...}}\\n
  - 服务端响应: {"status": "ok", "result": ...}\\n 或 {"status": "error", "error": "..."}\\n
  - 客户端关闭: {"action": "QUIT"}\\n
"""
from __future__ import annotations

import json
import sys


def serve() -> int:
    """P48-W3 stdio JSON-RPC serve 入口.

    POC: action 名 + args 直接 echo, 让 agora daemon 派发能正常返.
    实际各 action 业务逻辑可后续按需在此 dispatch.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "QUIT":
            break
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
        # POC 行为: echo 返 ok, 不做具体业务
        # (P33-W4 时代各包 serve --action 实际是各包特定实现,
        #  P48-W3 简化为统一 echo 模式, 让 agora 派发链路通)
        resp = {
            "status": "ok",
            "result": {
                "package": __name__.split(".")[0],
                "action": action,
                "args_echo": args,
            },
        }
        sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()
    return 0


__all__ = ["serve"]
