"""Kairon CLI — Knowledge & Research Operating Stack command-line interface.

Subcommands:
    hybrid-query    — Run hybrid retrieval against KEMS-v2 knowledge graph
    bootstrap       — Load seed policy/regulation/ADR/approval corpus
    stats           — Show graph statistics
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kairon.graph.kems_v2 import (
    Entity,
    EntityType,
    Edge,
    KnowledgeGraph,
    RelationType,
)


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
    """Load seed corpus: 政策/规程/ADR/批复 4 类, 共 ≥5000 entities.

    Uses deterministic seed (per category) so multiple runs produce stable
    BM25 scores for evaluation.
    """
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kairon", description="Kairon CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_query = sub.add_parser("hybrid-query", help="Run hybrid retrieval")
    p_query.add_argument("--q", required=True, help="query text")
    p_query.add_argument("--top-k", type=int, default=10)
    p_query.add_argument("--graph", help="path to graph JSONL")
    p_query.set_defaults(func=cmd_hybrid_query)

    p_boot = sub.add_parser("bootstrap", help="Load seed corpus into JSONL")
    p_boot.add_argument("--output", required=True, help="output JSONL path")
    p_boot.set_defaults(func=cmd_bootstrap)

    p_stats = sub.add_parser("stats", help="Graph statistics")
    p_stats.add_argument("--graph", help="path to graph JSONL")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
