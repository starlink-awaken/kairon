"""P49-W0: kairon 包 __main__.py v3 — 1 行复用 omo_stdio_rpc.

P48-W3: POC echo 模式 (-30 行).
P49-simplify pass 1: 加 _package_info + 真 import (-80 行).
P49-W0: 1 行用 omo_stdio_rpc 共用 helper (跨仓复制 omo.omo_stdio_rpc 模板).

用法:
  python -m <package> serve      # stdin JSON-RPC serve 模式 (供 agora daemon 派发)

协议 (P33-W4):
  stdin:  {"action": "X", "args": {...}}\\n
  stdout: {"status": "ok", "result": ...}\\n
  close:  {"action": "QUIT"}\\n
"""
from __future__ import annotations

from typing import Any


def _call_action(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """P49-W0: kairon 包通用 dispatch. 返 package info + echo."""
    return {
        "package": __name__.split(".")[0],
        "action_dispatched": action,
        "args_echo": args,
    }


def serve() -> int:
    """P49-W0: serve 入口 (跨仓用 omo_stdio_rpc 模板)."""
    # 跨仓复用: 此处不直接 import omo, 因 kairon 仓是独立 venv
    # omo_stdio_rpc 模板已 cp 到 kairon-utils/src/kairon_utils/stdio_rpc.py
    from kairon_utils.stdio_rpc import run_stdio_dispatch  # type: ignore[import-not-found]

    return run_stdio_dispatch(_call_action)


__all__ = ["serve", "_call_action"]
