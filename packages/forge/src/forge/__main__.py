"""kairon/forge stdio MCP server (POC).

P33-W5 战役 3: 集市 stdio 入口.
POC 协议: stdin JSON 行 → stdout JSON 行.

支持 action:
  - list         : 列出注册表工具
  - install      : 安装本地工具 (args: name, source_path, bos_uri, description)
  - remove       : 卸载工具 (args: name)
  - list-tools   : 列出工具名 (P36-W1 补, 跨域 POC 简化版)
  - exec-tool    : 执行工具 (P36-W1 补, 跨域 POC 简化版 — 返回元数据)
"""
from __future__ import annotations

import argparse
import json
import sys

from forge.market import (
    install_local_tool,
    list_tools,
    remove_tool,
)


def _handle_request(req: dict, action: str) -> dict:
    """处理单条 JSON 请求."""
    rid = req.get("request_id", "")
    # P36-W1 修: 同时支持 args (dict) 和 kwargs (resolver 协议)
    raw_args = req.get("args", {}) or {}
    raw_kwargs = req.get("kwargs", {}) or {}
    if isinstance(raw_args, dict):
        args = {**raw_args, **raw_kwargs}
    else:
        args = raw_kwargs if raw_kwargs else {x: x for x in raw_args}

    if action == "list":
        tools = list_tools()
        return {
            "status": "ok",
            "service": "kairon-forge",
            "action": action,
            "request_id": rid,
            "result": {"count": len(tools), "tools": tools},
        }

    if action == "install":
        name = args.get("name", "")
        source_path = args.get("source_path", "")
        bos_uri = args.get("bos_uri", "")
        description = args.get("description", "")
        if not name or not source_path:
            return {
                "status": "error",
                "service": "kairon-forge",
                "action": action,
                "request_id": rid,
                "error": "missing_args: require name, source_path",
            }
        result = install_local_tool(name, source_path, bos_uri, description)
        if "error" in result:
            return {
                "status": "error",
                "service": "kairon-forge",
                "action": action,
                "request_id": rid,
                "error": result["error"],
            }
        return {
            "status": "ok",
            "service": "kairon-forge",
            "action": action,
            "request_id": rid,
            "result": result,
        }

    if action == "remove":
        name = args.get("name", "")
        if not name:
            return {
                "status": "error",
                "service": "kairon-forge",
                "action": action,
                "request_id": rid,
                "error": "missing_args: require name",
            }
        ok = remove_tool(name)
        return {
            "status": "ok" if ok else "error",
            "service": "kairon-forge",
            "action": action,
            "request_id": rid,
            "result": {"removed": name} if ok else {},
            "error": "" if ok else f"not_found: {name}",
        }

    if action == "list-tools":
        # P36-W1 补: 简化版 — 只返回工具名列表
        tools = list_tools()
        return {
            "status": "ok",
            "service": "kairon-forge",
            "action": action,
            "request_id": rid,
            "result": {
                "count": len(tools),
                "names": [t.get("name", "") for t in tools],
            },
        }

    if action == "exec-tool":
        # P36-W1 补: POC 简化版 — 模拟执行, 任意 name 返回 ok
        name = args.get("name", "")
        if not name:
            return {
                "status": "error",
                "service": "kairon-forge",
                "action": action,
                "request_id": rid,
                "error": "missing_args: require name",
            }
        return {
            "status": "ok",
            "service": "kairon-forge",
            "action": action,
            "request_id": rid,
            "result": {
                "name": name,
                "executed": True,
                "mode": "poc-simulated",
            },
        }

    return {
        "status": "error",
        "service": "kairon-forge",
        "action": action,
        "request_id": rid,
        "error": f"unknown_action: {action} (supported: list, install, remove, list-tools, exec-tool)",
    }


def main() -> None:
    """stdio 主循环."""
    parser = argparse.ArgumentParser(prog="forge", description="Forge stdio MCP server (POC)")
    parser.add_argument(
        "--action",
        default="serve",
        help="action: serve (stdio 循环) / list / install / remove (单次 CLI 模式)",
    )
    args = parser.parse_args()

    # 单次 CLI 模式: 从 stdin 读 1 行
    if args.action in ("list", "install", "remove", "list-tools", "exec-tool"):
        line = sys.stdin.readline()
        if not line.strip():
            req: dict = {"request_id": "cli", "args": {}}
        else:
            req = json.loads(line)
        resp = _handle_request(req, args.action)
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return

    # serve 模式: 持续 stdio 循环
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            err = {
                "status": "error",
                "service": "kairon-forge",
                "error": f"json_decode: {exc}",
            }
            sys.stdout.write(json.dumps(err, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue

        action = req.get("action", args.action)
        resp = _handle_request(req, action)
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
