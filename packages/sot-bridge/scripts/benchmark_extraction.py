#!/usr/bin/env python3
"""提取器召回率基准测试

度量模板提取器和 LLM 提取器在不同文本上的召回率和准确率。

用法:
    python3 scripts/benchmark_extraction.py                           # 运行内置基准
    python3 scripts/benchmark_extraction.py --verbose                 # 详细输出
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保可以导入 ssot_kernel
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_SRC_DIR))

from ssot_kernel.extractor.base import TextSource
from ssot_kernel.extractor.template import TemplateExtractor

# ── 黄金标准定义 ──────────────────────────────────────
# 每条: (text, source_type, expected_ids, category)

BENCHMARKS: list[tuple[str, str, list[str], str]] = [
    # 政策编号模式
    (
        "P-F15 北京市科技成果转化条例\n来源: 市政府\n日期: 2026-01-15",
        "document",
        ["POL-P-F15"],
        "fact",
    ),
    (
        "P-F16 高校赋权改革方案（征求意见稿）\n来源: 教育部\n日期: 2026-03-01",
        "document",
        ["POL-P-F16"],
        "fact",
    ),
    # 数据事实模式
    (
        "优质成果数: 470 项\n来源: 中心介绍PDF\n日期: 2026-03",
        "structured",
        [],
        "fact",
    ),
    # 实体模式：h2 标题
    (
        "## ORG-国转中心\n\n全国高校绿色能源区域技术成果转移转化中心。\n\n"
        "## ORG-产投集团\n\n北京房山产业发展投资集团。",
        "document",
        ["ORG-国转中心", "ORG-产投集团"],
        "entity",
    ),
    (
        "## ROL-技术经理人\n\n中心的技术经理人团队。\n\n## ROL-企业用户\n\n企业用户角色。",
        "document",
        ["ROL-技术经理人", "ROL-企业用户"],
        "entity",
    ),
    # 表格模式
    (
        "| 指标 | 数值 | 单位 | 来源 |\n"
        "|------|------|------|------|\n"
        "| 优质成果数 | 470 | 项 | 中心PDF |\n"
        "| 技术需求数 | 228 | 项 | 中心PDF |\n"
        "| 落地转化数 | 15 | 项 | 中心PDF |",
        "file",
        [],
        "fact",
    ),
    # 混合文档
    (
        "## 政策文件\n\nP-F10 概念验证平台建设指引\n来源: 北京市科委\n\n## 组织实体\n\nORG-国转中心 是国家级平台。",
        "document",
        ["POL-P-F10", "ORG-国转中心"],
        "any",
    ),
    # 人物模式
    (
        "## person-张三\n\n角色: 技术经理人\n专长: 储能材料\n\n## person-李四\n\n角色: 评审专家\n专长: 氢能",
        "document",
        ["person-张三", "person-李四"],
        "entity",
    ),
    # 项目模式
    (
        "## project-数字化平台\n\nowner: 产投集团\n投资: 待定\n\n## project-概念验证\n\n投资: 1.5亿",
        "document",
        ["project-数字化平台", "project-概念验证"],
        "entity",
    ),
]


def run_template_benchmark(benchmarks: list[tuple] | None = None, verbose: bool = False) -> dict:
    """运行模板提取器基准测试"""
    if benchmarks is None:
        benchmarks = BENCHMARKS

    extractor = TemplateExtractor()
    total = len(benchmarks)
    total_expected = 0
    total_found = 0
    total_correct = 0

    results = []

    for text, source_type, expected_ids, category in benchmarks:
        source = TextSource(raw_text=text, source_type=source_type, source_name="benchmark")
        result = extractor.extract(source)

        found_ids = [c.id for c in result.candidates if c.id]
        correct = [e for e in expected_ids if e in found_ids]
        missed = [e for e in expected_ids if e not in found_ids]
        extra = [f for f in found_ids if f not in expected_ids]

        total_expected += len(expected_ids)
        total_found += len(found_ids)
        total_correct += len(correct)

        if verbose or correct != expected_ids:
            status = "✅" if correct == expected_ids else "⚠️"
            print(f"  {status} {source_type}: expected={expected_ids} found={found_ids}")

        results.append(
            {
                "expected": expected_ids,
                "found": found_ids,
                "correct": correct,
                "missed": missed,
                "extra": extra,
            }
        )

    # 计算指标
    precision = total_correct / total_found if total_found > 0 else 0
    recall = total_correct / total_expected if total_expected > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "total_benchmarks": total,
        "total_expected": total_expected,
        "total_found": total_found,
        "total_correct": total_correct,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "results": results,
    }


def print_report(stats: dict):
    """打印格式化的基准报告"""
    print()
    print("=" * 50)
    print("  模板提取器召回率基准报告")
    print("=" * 50)
    print(f"  基准用例:      {stats['total_benchmarks']}")
    print(f"  期望提取数:    {stats['total_expected']}")
    print(f"  实际提取数:    {stats['total_found']}")
    print(f"  正确提取数:    {stats['total_correct']}")
    print("  ─────────────────────────────")
    print(f"  精确率 (Precision):  {stats['precision']:.1%}")
    print(f"  召回率 (Recall):     {stats['recall']:.1%}")
    print(f"  F1 分数:            {stats['f1']:.1%}")
    print("=" * 50)

    if stats["recall"] < 0.5:
        print("  ⚠️  召回率偏低 — 可能需要:")
        print("    • 增加模板模式匹配规则")
        print("    • 检查 source_type 是否匹配")
        print("    • 使用 --verbose 查看具体缺失")


def run_llm_benchmark(verbose: bool = False) -> dict | None:
    """运行 LLM 提取器基准测试（可选，需要 Ollama 或云端 API）"""
    from ssot_kernel.extractor.llm import LLMExtractor

    extractor = LLMExtractor(auto_detect=True)
    if not extractor.available:
        print("  ⏭️  LLM 不可用，跳过 LLM 基准测试")
        return None

    if verbose:
        print(f"  🔌 LLM 后端: {[b.name for b in extractor.backends]}")

    # 选几个能展示 LLM vs 模板差异的用例
    llm_benchmarks = [
        ("P-F15 北京市科技成果转化条例", "document", ["POL-P-F15"], "fact"),
        ("## ORG-国转中心\n国家级平台。", "document", ["ORG-国转中心"], "entity"),
        ("优质成果数 470 项，落地转化 15 项", "free_text", [], "fact"),
    ]

    total_expected = 0
    total_found = 0
    total_correct = 0

    for text, source_type, expected_ids, category in llm_benchmarks:
        source = TextSource(raw_text=text, source_type=source_type, source_name="benchmark-llm")
        result = extractor.extract(source)
        found_ids = [c.id for c in result.candidates if c.id]
        correct = [e for e in expected_ids if e in found_ids]

        total_expected += len(expected_ids)
        total_found += len(found_ids)
        total_correct += len(correct)

        if verbose:
            print(f"  {'✅' if correct == expected_ids else '⚠️'} LLM: expected={expected_ids} found={found_ids}")

    precision = total_correct / total_found if total_found > 0 else 0
    recall = total_correct / total_expected if total_expected > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "total_expected": total_expected,
        "total_found": total_found,
        "total_correct": total_correct,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    use_llm = "--llm" in sys.argv

    print("🔍 运行模板提取器基准测试...")
    template_stats = run_template_benchmark(verbose=verbose)
    print_report(template_stats)

    if use_llm:
        print("\n🔍 运行 LLM 提取器基准测试（对比）...")
        llm_stats = run_llm_benchmark(verbose=verbose)
        if llm_stats:
            print()
            print("=" * 50)
            print("  LLM 提取器基准报告（对比）")
            print("=" * 50)
            print(f"  期望提取数:    {llm_stats['total_expected']}")
            print(f"  实际提取数:    {llm_stats['total_found']}")
            print(f"  正确提取数:    {llm_stats['total_correct']}")
            print(f"  精确率:        {llm_stats['precision']:.1%}")
            print(f"  召回率:        {llm_stats['recall']:.1%}")
            print(f"  F1:            {llm_stats['f1']:.1%}")
            print("=" * 50)

    overall_recall = template_stats["recall"]
    return 0 if overall_recall >= 0.05 else 1


if __name__ == "__main__":
    sys.exit(main())
