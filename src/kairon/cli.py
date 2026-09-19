"""cli.py — Kairon 统一 CLI 入口。

提供子命令：
- org-graph: 组织人脉图谱查询
- hybrid-query: KEMS-v2 混合检索
- bootstrap: 种子语料加载
- stats: 图谱统计

Usage:
    python -m kairon.cli org-graph --query <关键词> [--json]
    python -m kairon.cli hybrid-query --q <文本> [--top-k N] [--graph PATH]
    python -m kairon.cli bootstrap --output <PATH>
    python -m kairon.cli stats [--graph PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kairon.graph.kems_v2 import KnowledgeGraph


def _load_graph(path: Path | None) -> KnowledgeGraph:
    g = KnowledgeGraph()
    if path and path.exists():
        g = KnowledgeGraph.load(path)
    return g


def cmd_hybrid_query(args: argparse.Namespace) -> int:
    g = _load_graph(Path(args.graph) if args.graph else None)
    results = g.search(args.q, top_k=args.top_k)
    if not results:
        print(f"未命中: query={args.q!r}")
        return 0
    for entity, score in results:
        print(f"[{score:.3f}] {entity.id} ({entity.entity_type.value}): {entity.title}")
        if entity.source:
            print(f"  source: {entity.source}")
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Load seed corpus: 政策/规程/ADR/批复 4 类, 共 ≥5000 entities."""
    from kairon.graph.bootstrap import seed_default_corpus
    g = KnowledgeGraph()
    counts = seed_default_corpus(g)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g.save(out_path)
    print(f"已 bootstrap {sum(counts.values())} entities → {out_path}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    g = _load_graph(Path(args.graph) if args.graph else None)
    entities = g.list_entities()
    by_type: dict[str, int] = {}
    for e in entities:
        t = e.entity_type.value
        by_type[t] = by_type.get(t, 0) + 1
    print(f"entities: {len(entities)}  ({', '.join(f'{k}={v}' for k, v in sorted(by_type.items()))})")
    print(f"edges:    {len(g._edges)}")
    return 0


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

    # ── hybrid-query subcommand (KEMS-v2) ──
    hq_parser = subparsers.add_parser(
        "hybrid-query",
        help="KEMS-v2 混合检索",
        description="对 KEMS-v2 知识图谱执行混合检索（BM25 + 向量）。",
    )
    hq_parser.add_argument("--q", required=True, help="query text")
    hq_parser.add_argument("--top-k", type=int, default=10)
    hq_parser.add_argument("--graph", help="path to graph JSONL")
    hq_parser.set_defaults(func=cmd_hybrid_query)

    # ── bootstrap subcommand ──
    boot_parser = subparsers.add_parser(
        "bootstrap",
        help="种子语料加载",
        description="加载种子政策/规程/ADR/批复语料到 JSONL 图谱。",
    )
    boot_parser.add_argument("--output", required=True, help="output JSONL path")
    boot_parser.set_defaults(func=cmd_bootstrap)

    # ── stats subcommand ──
    stats_parser = subparsers.add_parser(
        "stats",
        help="图谱统计",
        description="显示 KEMS-v2 图谱实体与边统计。",
    )
    stats_parser.add_argument("--graph", help="path to graph JSONL")
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
