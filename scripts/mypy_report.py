#!/usr/bin/env python3
"""Per-package mypy error report (提炼自 _count_errors.py, 去硬编码绝对路径).

服务 DEBT-CI-MYPY-STRICT: kairon 16/16 本地 strict, CI 未启用.
此工具给 per-package mypy 错误数报表, 辅助 mypy strict 推进诊断.

Usage:
    python scripts/mypy_report.py            # 全包报表, top 10
    python scripts/mypy_report.py --top 5    # top 5
    python scripts/mypy_report.py --json     # JSON 输出 (供 CI/dashboard)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 锚定 kairon 根 (scripts/ 的父目录), 不硬编码绝对路径 — CI 可移植
KAIRON_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = KAIRON_ROOT / "packages"


def count_mypy_errors(pkg_dir: Path) -> int:
    """跑 mypy 数某包错误 (namespace-packages + explicit-package-bases)."""
    try:
        result = subprocess.run(
            [
                "mypy",
                "--namespace-packages",
                "--explicit-package-bases",
                "--exclude", "/tests/",
                "--exclude", "/build/",
                str(pkg_dir),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        print(f"⚠️  mypy 未安装 (跳过 {pkg_dir.name})", file=sys.stderr)
        return 0
    m = re.search(r"Found (\d+) errors?", result.stdout)
    return int(m.group(1)) if m else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-package mypy error report")
    parser.add_argument("--top", type=int, default=10, help="显示 top N 包 (默认 10)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if not PACKAGES_DIR.exists():
        print(f"❌ packages/ 目录不存在: {PACKAGES_DIR}", file=sys.stderr)
        return 1

    packages = sorted(p for p in PACKAGES_DIR.iterdir() if p.is_dir())
    # (package_name, error_count) — 用 tuple 让 sum/sorted 类型推断精确 (mypy strict 友好)
    results: list[tuple[str, int]] = []
    for pkg in packages:
        count = count_mypy_errors(pkg)
        results.append((pkg.name, count))
        if not args.json:
            print(f"  {pkg.name}: {count} errors")

    total = sum(c for _, c in results)
    if args.json:
        payload = {"total": total, "packages": [{"package": n, "errors": c} for n, c in results]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"\nTotal: {total} errors across {len(results)} packages")
    print(f"\nTop {args.top} packages by error count:")
    for name, count in sorted(results, key=lambda x: x[1], reverse=True)[: args.top]:
        print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
