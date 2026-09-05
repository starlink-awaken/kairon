"""KEMS-v2 CLI + bootstrap test suite."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


KAIRON_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = KAIRON_ROOT / "pyproject.toml"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    # Use uv run to ensure kairon package is on PYTHONPATH (installed via pyproject.toml)
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", "-m", "kairon.cli", *args],
        cwd=KAIRON_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_cli_help_exits_zero() -> None:
    cp = _run_cli("--help")
    assert cp.returncode == 0
    assert "hybrid-query" in cp.stdout


def test_cli_stats_empty_graph() -> None:
    cp = _run_cli("stats")
    assert cp.returncode == 0
    assert "entities: 0" in cp.stdout


def test_bootstrap_5000_entities_20k_edges(tmp_path: Path) -> None:
    out = tmp_path / "kems.jsonl"
    cp = _run_cli("bootstrap", "--output", str(out))
    assert cp.returncode == 0, cp.stderr
    assert out.exists()
    assert "policy: 2000" in cp.stdout
    assert "regulation: 1500" in cp.stdout
    assert "adr: 1000" in cp.stdout
    assert "approval: 500" in cp.stdout
    assert "edges:" in cp.stdout

    # 解析输出取 edges 数值
    edges_line = [l for l in cp.stdout.splitlines() if l.strip().startswith("edges:")][0]
    n_edges = int(edges_line.split(":")[1].strip())
    assert n_edges >= 20000, f"edges={n_edges} < 20000"

    # 统计 JSONL 行数
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    n_entity = sum(1 for l in lines if '"entity_type"' in l)
    n_edge = sum(1 for l in lines if '"relation"' in l)
    assert n_entity == 5000, f"entities={n_entity}"
    assert n_edge >= 20000, f"edge rows={n_edge}"


def test_hybrid_query_returns_relevant_hits(tmp_path: Path) -> None:
    out = tmp_path / "kems.jsonl"
    cp = _run_cli("bootstrap", "--output", str(out))
    assert cp.returncode == 0

    cp = _run_cli("hybrid-query", "--q", "卫生健康数字化转型", "--graph", str(out), "--top-k", "5")
    assert cp.returncode == 0, cp.stderr
    # 至少 1 行命中
    hits = [l for l in cp.stdout.splitlines() if l.startswith("[")]
    assert len(hits) >= 1
    # 第一条命中应当是 policy 类型 (强相关)
    assert "(policy)" in hits[0]


def test_hybrid_query_no_match() -> None:
    cp = _run_cli("hybrid-query", "--q", "完全不存在的虚构主题 xyzqwerty")
    assert cp.returncode == 0
    # 无命中, 提示未命中
    assert "未命中" in cp.stdout or cp.stdout.strip() == ""


def test_stats_after_bootstrap(tmp_path: Path) -> None:
    out = tmp_path / "kems.jsonl"
    _run_cli("bootstrap", "--output", str(out))
    cp = _run_cli("stats", "--graph", str(out))
    assert cp.returncode == 0
    assert "entities: 5000" in cp.stdout
    assert "edges:" in cp.stdout
