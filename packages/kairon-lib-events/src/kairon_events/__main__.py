"""P52-W0: kairon 包 __main__.py v5 — 真 method dispatch (替代 v4 info-only).

P51-W1 v4: 真 import 验证 + 返 package info (POC 可达性).
P52-W0 v5: 加 method dispatch — 尝试 getattr(module, f"do_{action}")(args).
        调成功 → status=ok + 真结果. 调失败 fall back 到 v4 info + echo.

POC: 各包按需加 do_<action> function. 默认无 method, v4 info + echo fallback.

用法:
  python -m <package> serve
"""
from __future__ import annotations

import importlib
from typing import Any


def _package_info() -> dict[str, Any]:
    """P51-W1: 真 import 验证 + 元数据."""
    pkg_name = __name__.split(".")[0]
    try:
        mod = importlib.import_module(__name__)
    except Exception as exc:
        return {"package": pkg_name, "_import_error": f"{type(exc).__name__}: {exc}"}
    return {
        "package": pkg_name,
        "module": mod.__name__,
        "attrs_count": len([a for a in dir(mod) if not a.startswith("_")]),
        "classes": [a for a in dir(mod) if not a.startswith("_") and isinstance(getattr(mod, a), type)],
    }


def _try_method_dispatch(action: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """P52-W0: 尝试调包内 do_<action> function. 返 None 表示未找到."""
    try:
        mod = importlib.import_module(__name__)
    except Exception:
        return None
    fn = getattr(mod, f"do_{action}", None)
    if fn is None or not callable(fn):
        return None
    try:
        result = fn(args) if args else fn()
        return {"method_dispatch": "ok", "result": result}
    except Exception as exc:
        return {"method_dispatch": "error", "error": f"{type(exc).__name__}: {exc}"}


def _call_action(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """P52-W0: 真 method dispatch (do_<action>), 失败 fall back v4 info."""
    dispatch = _try_method_dispatch(action, args)
    if dispatch is not None:
        info = _package_info()
        return {
            "package": info.get("package", "?"),
            "action_dispatched": action,
            "args_echo": args,
            "version": info.get("version", "unknown"),
            **dispatch,
        }
    # Fall back v4 info + echo
    info = _package_info()
    return {
        "package": info.get("package", "?"),
        "version": info.get("version", "unknown"),
        "attrs_count": info.get("attrs_count", 0),
        "classes_count": len(info.get("classes", [])),
        "action_dispatched": action,
        "args_echo": args,
        "_reachability": "ok" if "_import_error" not in info else "fail",
        "method_dispatch": "fallback",
    }


def serve() -> int:
    """P52-W0: serve 入口 (复用 kairon_utils.stdio_rpc)."""
    from kairon_utils.stdio_rpc import run_stdio_dispatch  # type: ignore[import-not-found]

    return run_stdio_dispatch(_call_action)


__all__ = ["serve", "_call_action", "_package_info", "_try_method_dispatch"]
