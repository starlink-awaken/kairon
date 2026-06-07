"""P54-W0: 4 关键 kairon 包 do_<action> 真业务 (eidos/kos/forge/iris).

v5 method dispatch 调 do_<action>(args), 加各包真业务 function.
POC 业务范围: import 成功 + 真类实例化 + 类方法调 (e.g. KOS().search(query)).

Strategy: 用 try/except, 调成功 → status=ok + 真结果, 调失败 → status=error.
"""
from __future__ import annotations

import importlib
import inspect
from typing import Any


def _package_info() -> dict[str, Any]:
    pkg_name = __name__.split(".")[0]
    try:
        mod = importlib.import_module(__name__)
    except Exception as exc:
        return {"package": pkg_name, "_import_error": f"{type(exc).__name__}: {exc}"}
    return {
        "package": pkg_name,
        "module": mod.__name__,
        "attrs_count": len([a for a in dir(mod) if not a.startswith("_")]),
    }


def do_search(args: dict[str, Any]) -> dict[str, Any]:
    """kos/kronos/eidos 等真调 (本包需有 search 类方法)."""
    try:
        mod = importlib.import_module(__name__)
        # 找含 search 方法的类
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "search"):
                instance = obj() if not isinstance(obj, type) else obj
                result = instance.search(args.get("query", ""))
                return {"_method": "search", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "search", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "search", "_error": "no class with search method"}


def do_ingest(args: dict[str, Any]) -> dict[str, Any]:
    """kos/kronos/ontoderive 等真调 (本包需有 ingest 类方法)."""
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "ingest"):
                instance = obj() if not isinstance(obj, type) else obj
                result = instance.ingest(args.get("entity", args.get("data", {})))
                return {"_method": "ingest", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "ingest", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "ingest", "_error": "no class with ingest method"}


def do_validate(args: dict[str, Any]) -> dict[str, Any]:
    """eidos/core-models 等真调 (本包需有 validate 类方法)."""
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "validate"):
                instance = obj() if not isinstance(obj, type) else obj
                result = instance.validate(args.get("data", args.get("entity", {})))
                return {"_method": "validate", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "validate", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "validate", "_error": "no class with validate method"}


def do_register(args: dict[str, Any]) -> dict[str, Any]:
    """forge/sot-bridge 等真调 (本包需有 register 类方法)."""
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "register"):
                instance = obj() if not isinstance(obj, type) else obj
                result = instance.register(args.get("name", "default"), args.get("capabilities", []))
                return {"_method": "register", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "register", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "register", "_error": "no class with register method"}


def do_list(args: dict[str, Any]) -> dict[str, Any]:
    """forge/kairon-pipeline 等真调 (本包需有 list 类方法)."""
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "list"):
                instance = obj() if not isinstance(obj, type) else obj
                result = instance.list(args)
                return {"_method": "list", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "list", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "list", "_error": "no class with list method"}


def do_run(args: dict[str, Any]) -> dict[str, Any]:
    """agent-runtime/minerva/kronos 等真调 (本包需有 run 类方法)."""
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "run"):
                instance = obj() if not isinstance(obj, type) else obj
                result = instance.run(args.get("query", args.get("task", "")))
                return {"_method": "run", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "run", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "run", "_error": "no class with run method"}


def do_get(args: dict[str, Any]) -> dict[str, Any]:
    """health-profile/kos 等真调 (本包需有 get 类方法)."""
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "get"):
                instance = obj() if not isinstance(obj, type) else obj
                result = instance.get(args.get("id", args.get("key", "")))
                return {"_method": "get", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "get", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "get", "_error": "no class with get method"}


def do_sync(args: dict[str, Any]) -> dict[str, Any]:
    """omo/sot-bridge 等真调 (本包需有 sync 类方法)."""
    try:
        mod = importlib.import_module(__name__)
        for name in dir(mod):
            obj = getattr(mod, name)
            if inspect.isclass(obj) and hasattr(obj, "sync"):
                instance = obj() if not isinstance(obj, type) else obj
                result = instance.sync(args)
                return {"_method": "sync", "_class": name, "result": str(result)[:500]}
    except Exception as exc:
        return {"_method": "sync", "_error": f"{type(exc).__name__}: {exc}"}
    return {"_method": "sync", "_error": "no class with sync method"}


# ── 路由表: action 名 → do_<action> function ─────────────
_DISPATCH = {
    "search": do_search,
    "ingest": do_ingest,
    "validate": do_validate,
    "register": do_register,
    "list": do_list,
    "run": do_run,
    "get": do_get,
    "sync": do_sync,
    # 通用: action 名作为 do_<action> fallback
}


def _call_action(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """P54-W0: 真业务 dispatch 路由."""
    fn = _DISPATCH.get(action)
    if fn is not None:
        result = fn(args)
        info = _package_info()
        return {
            "package": info.get("package", "?"),
            "action_dispatched": action,
            "args_echo": args,
            "_reachability": "ok" if "_import_error" not in info else "fail",
            **result,
        }
    # Fallback: 调 do_<action> 通用 (跨包 method 名 dispatch)
    fallback_name = f"do_{action.replace('-', '_')}"
    fallback_fn = globals().get(fallback_name)
    if fallback_fn is not None and callable(fallback_fn):
        try:
            result = fallback_fn(args)
            return {"package": __name__.split(".")[0], "action_dispatched": action, "args_echo": args, **result}
        except Exception as exc:
            return {"package": __name__.split(".")[0], "action_dispatched": action, "_error": f"{type(exc).__name__}: {exc}"}
    # 都没: echo
    info = _package_info()
    return {
        "package": info.get("package", "?"),
        "action_dispatched": action,
        "args_echo": args,
        "_reachability": "ok" if "_import_error" not in info else "fail",
        "_method_dispatch": "echo_fallback",
    }


def serve() -> int:
    """P52-W0 serve 入口 (复用 kairon_utils.stdio_rpc)."""
    from kairon_utils.stdio_rpc import run_stdio_dispatch  # type: ignore[import-not-found]

    return run_stdio_dispatch(_call_action)


__all__ = ["serve", "_call_action", "_package_info", "_DISPATCH"]

def main() -> int:
    """CLI + stdio serve 统一入口."""
    import sys
    from pathlib import Path

    # 非 serve 命令（如 toolforge / derive / check 等）委托给完整 CLI
    if len(sys.argv) > 1 and sys.argv[1] != "serve":
        # 确保 engine 包在 path 中 (__main__.py 在 src/ontoderive/, engine 在项目根)
        _pkg_root = Path(__file__).resolve().parent.parent.parent
        if str(_pkg_root) not in sys.path:
            sys.path.insert(0, str(_pkg_root))
        from engine.cli import main as _cli_main  # type: ignore[import-not-found]

        _cli_main()
        return 0
    from kairon_utils.stdio_rpc import run_stdio_main

    return run_stdio_main(serve)


if __name__ == "__main__":
    import sys

    sys.exit(main())
