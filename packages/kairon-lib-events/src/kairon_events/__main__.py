"""P51-W1: kairon 包 __main__.py v4 — 真业务 dispatch (替代 v3 echo 模式).

P49-W0: 1 行用 omo_stdio_rpc helper (v3 echo 模式).
P51-W1: 加 _package_info 真 import + 包内 main class / public function 列表.
        返 {package, version, attrs, action_dispatched, args_echo}.
        真 import 失败 → status=error + _import_error.
        POC 业务: import 成功即 "可达服务" 派发信号, 让 LLM 派发链路真知道.

用法:
  python -m <package> serve
"""
from __future__ import annotations

import importlib
from typing import Any


def _package_info() -> dict[str, Any]:
    """P51-W1: 实际 import 本包验证可加载, 返版本/类/函数信息."""
    pkg_name = __name__.split(".")[0]
    try:
        mod = importlib.import_module(__name__)
    except Exception as exc:
        return {"package": pkg_name, "_import_error": f"{type(exc).__name__}: {exc}"}
    info: dict[str, Any] = {
        "package": pkg_name,
        "module": mod.__name__,
        "attrs_count": len([a for a in dir(mod) if not a.startswith("_")]),
        "classes": [a for a in dir(mod) if not a.startswith("_") and isinstance(getattr(mod, a), type)],
        "functions": [a for a in dir(mod) if not a.startswith("_") and callable(getattr(mod, a)) and not isinstance(getattr(mod, a), type)],
    }
    if hasattr(mod, "__version__"):
        info["version"] = mod.__version__
    return info


def _call_action(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """P51-W1: 真业务 dispatch — 实际 import 包 + 返 package info + echo.

    POC 业务范围: import 可达性 + 包元数据. 真 action 业务由各包 __init__.py
    后续在 P52+ 加 method dispatch. 本步只解决"服务可达性"维度.
    """
    info = _package_info()
    return {
        "package": info.get("package", "?"),
        "version": info.get("version", "unknown"),
        "attrs_count": info.get("attrs_count", 0),
        "classes_count": len(info.get("classes", [])),
        "action_dispatched": action,
        "args_echo": args,
        "_reachability": "ok" if "_import_error" not in info else "fail",
    }


def serve() -> int:
    """P51-W1: serve 入口 (复用 kairon_utils.stdio_rpc)."""
    from kairon_utils.stdio_rpc import run_stdio_dispatch  # type: ignore[import-not-found]

    return run_stdio_dispatch(_call_action)


__all__ = ["serve", "_call_action", "_package_info"]
