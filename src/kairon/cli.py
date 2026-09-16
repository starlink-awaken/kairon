"""cli.py — Kairon 统一 CLI 入口。

提供子命令：
- org-graph: 组织人脉图谱查询

Usage:
    python -m kairon.cli org-graph --query <关键词> [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_org_graph(args: argparse.Namespace) -> int:
    """Handle org-graph subcommand."""
    from kairon.graph.org_graph import OrgGraph

    query: str = args.query
    output_json: bool = getattr(args, "json", False)

    # Load or create demo graph
    data_path = Path(__file__).parent / "_data" / "org_graph.jsonl"
    if data_path.exists():
        graph = OrgGraph.load(data_path)
    else:
        graph = OrgGraph.demo()

    if output_json:
        result = graph.network_view(query)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        matches = graph.search(query, top_k=10)
        if not matches:
            print(f"未找到与 '{query}' 相关的组织或人物。")
            return 0

        print(f"查询: {query}")
        print(f"匹配: {len(matches)} 条\n")
        for node, score in matches:
            type_label = {
                "organization": "🏢 单位",
                "person": "👤 人物",
                "document": "📄 来件",
            }.get(node.node_type.value, node.node_type.value)
            print(f"  [{type_label}] {node.name} (score={score:.1f})")
            if node.title:
                print(f"    职位/文号: {node.title}")
            if node.summary:
                print(f"    摘要: {node.summary}")
            print()

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="kairon.cli",
        description="Kairon Knowledge & Research Operating Stack CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    # ── org-graph subcommand ──
    org_parser = subparsers.add_parser(
        "org-graph",
        help="组织人脉图谱查询",
        description="查询组织-人物-来件关系网络，返回匹配的节点与关系子图。",
    )
    org_parser.add_argument(
        "--query", "-q",
        required=True,
        help="查询关键词（单位名称、人名或来件主题）",
    )
    org_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="以 JSON 格式输出完整网络视图",
    )
    org_parser.set_defaults(func=_cmd_org_graph)

    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
