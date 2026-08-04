"""MOS CLI — human flags + Agora StdioAdapter stdin JSON ({args, kwargs})."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mos.persist import FileStore


def _read_stdio_request() -> dict[str, Any] | None:
    """If stdin is a pipe with JSON {args, kwargs}, return it; else None.

    Agora StdioAdapter does communicate(input=json). Flag-mode CLIs leave
    stdin empty / TTY. pytest capture raises OSError on read — ignore.
    """
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return None
    except Exception:  # noqa: BLE001
        return None
    # Prefer non-blocking detect so flag-mode does not consume pytest stdin
    try:
        import select

        ready, _, _ = select.select([sys.stdin], [], [], 0.0)
        if not ready:
            # Still allow env-forced stdio (tests / adapters that already filled buffer)
            if not __import__("os").environ.get("MOS_STDIO"):
                return None
    except Exception:  # noqa: BLE001 — select unavailable
        if not __import__("os").environ.get("MOS_STDIO"):
            # Fall through to attempt read only when MOS_STDIO set
            pass
    try:
        raw = sys.stdin.read()
    except OSError:
        return None
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw.strip().splitlines()[0])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    # Agora StdioAdapter shape
    if "args" in data or "kwargs" in data:
        return data
    # Also accept a bare envelope / query object as kwargs
    return {"args": [], "kwargs": data}


def _emit(obj: dict[str, Any], *, pretty: bool = False) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None))


def _run_write(mos: Any, store: FileStore, kwargs: dict[str, Any], *, pretty: bool = False) -> int:
    envelope: dict[str, Any] = {}
    if isinstance(kwargs.get("envelope"), dict):
        envelope = dict(kwargs["envelope"])
    else:
        envelope = {
            "type": kwargs.get("type") or kwargs.get("mem_type"),
            "content": kwargs.get("content"),
            "content_ref": kwargs.get("content_ref") or kwargs.get("contentRef"),
            "confidence": float(kwargs.get("confidence", 0.8)),
            "principal_id": kwargs.get("principal_id"),
            "agent_profile": kwargs.get("agent_profile"),
            "session_id": kwargs.get("session_id"),
            "run_id": kwargs.get("run_id"),
            "source": kwargs.get("source") or "bos-stdio",
            "metadata": kwargs.get("metadata") or {},
        }
    # drop Nones for cleaner validation messages
    envelope = {k: v for k, v in envelope.items() if v is not None}
    result = mos.write(envelope)
    store.flush_from(mos)
    _emit(result.to_dict(), pretty=pretty)
    return 0 if result.ok else 1


def _run_recall(mos: Any, kwargs: dict[str, Any], args_list: list[Any], *, pretty: bool = False) -> int:
    query = kwargs.get("query")
    if query is None and args_list:
        query = args_list[0]
    if not query:
        _emit({"ok": False, "error": "query required"})
        return 2
    intent = kwargs.get("intent")
    limit = int(kwargs.get("limit", 10))
    scope = kwargs.get("scope") if isinstance(kwargs.get("scope"), dict) else None
    result = mos.recall(str(query), intent=intent, limit=limit, scope=scope)
    _emit(result.to_dict(), pretty=pretty)
    return 0


def _run_status(mos: Any, store: FileStore, *, pretty: bool = False) -> int:
    st = mos.status()
    st["store_path"] = str(store.path)
    _emit(st, pretty=pretty)
    return 0


def dispatch(cmd: str, stdio: dict[str, Any] | None, argv_ns: argparse.Namespace | None = None) -> int:
    store = FileStore()
    mos = store.build_memory_os()
    pretty = bool(getattr(argv_ns, "json", False)) if argv_ns is not None else False

    if stdio is not None:
        args_list = list(stdio.get("args") or [])
        kwargs = dict(stdio.get("kwargs") or {})
        if cmd == "write":
            return _run_write(mos, store, kwargs, pretty=False)
        if cmd == "recall":
            return _run_recall(mos, kwargs, args_list, pretty=False)
        if cmd == "status":
            return _run_status(mos, store, pretty=False)
        _emit({"ok": False, "error": f"unknown cmd {cmd}"})
        return 2

    assert argv_ns is not None
    if cmd == "write":
        return _run_write(
            mos,
            store,
            {
                "type": argv_ns.mem_type,
                "content": argv_ns.content,
                "content_ref": argv_ns.content_ref,
                "confidence": argv_ns.confidence,
            },
            pretty=pretty,
        )
    if cmd == "recall":
        return _run_recall(
            mos,
            {"query": argv_ns.query, "intent": argv_ns.intent, "limit": argv_ns.limit},
            [],
            pretty=pretty,
        )
    if cmd == "status":
        return _run_status(mos, store, pretty=pretty)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mos", description="Memory OS control plane")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_write = sub.add_parser("write", help="Write a memory envelope")
    p_write.add_argument("--type", dest="mem_type", default=None, help="Required for flag mode")
    p_write.add_argument("--content", default=None)
    p_write.add_argument("--content-ref", default=None)
    p_write.add_argument("--confidence", type=float, default=0.8)
    p_write.add_argument("--json", action="store_true", help="Pretty JSON")

    p_recall = sub.add_parser("recall", help="Recall memories")
    p_recall.add_argument("query", nargs="?", default=None)
    p_recall.add_argument("--intent", default=None)
    p_recall.add_argument("--limit", type=int, default=10)
    p_recall.add_argument("--json", action="store_true")

    sub.add_parser("status", help="Control plane status")

    # When invoked via Agora stdio, argv is like ["write"] and payload is on stdin.
    # Parse known args first so --help still works; stdio path does not require flags.
    args = parser.parse_args(argv)
    stdio = _read_stdio_request()

    if args.cmd == "write" and stdio is None and not args.mem_type:
        parser.error("write requires --type (or Agora stdin JSON with kwargs.type)")
    if args.cmd == "recall" and stdio is None and not args.query:
        parser.error("recall requires query (or Agora stdin JSON with kwargs.query)")

    return dispatch(args.cmd, stdio, args)


if __name__ == "__main__":
    sys.exit(main())
