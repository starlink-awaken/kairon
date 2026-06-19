from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Frontmatter Merger ≡ Module
# 内涵 ≝ {Frontmatter, Merger}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, FrontmatterMerger)}
# 功能 ⊢ {Frontmatter_Merger, Init_Frontmatter, Validate_Merger}
# =============================================================================

# ---
# Type: Module
# Status: ACTIVE
# Layer: L3
# ---
"""
Frontmatter Merger - 合并多个 frontmatter 块

策略:
1. 收集所有有效字段
2. 优先级：第一个块 > 后续块
3. 清理重复和冲突
4. 生成单一标准 frontmatter

Usage:
    python3 organs/D_Logos/organs/frontmatter_merger.py --fix docs/README.md
    python3 organs/D_Logos/organs/frontmatter_merger.py --batch docs/20-architecture/ --dry-run
"""


import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from ontoderive.frontmatter_detector import FrontmatterDetector  # type: ignore[import-not-found]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_log = logging.getLogger(__name__)


class FrontmatterMerger:
    """Frontmatter 合并器"""

    def __init__(self) -> None:
        self.priority_fields = ["Type", "Status", "Version", "Owner", "Authority", "Layer"]
        self.standard_fields = [
            "Type",
            "Status",
            "Version",
            "Owner",
            "Authority",
            "Layer",
            "Updated",
            "Created",
            "Summary",
            "Tags",
        ]

    def merge(self, blocks: list[dict]) -> dict[str, Any]:
        """合并多个 frontmatter 块

        Args:
            blocks: 列表，每个元素是 {'is_valid': bool, 'parsed_data': dict}

        Returns:
            合并后的字典
        """
        merged = {}

        # 第一轮：收集所有有效字段（按优先级顺序）
        for block_data in blocks:
            if not block_data.get("is_valid"):
                continue

            parsed = block_data.get("parsed_data")
            if not isinstance(parsed, dict):
                continue

            # 优先保留高优先级字段
            for key, value in parsed.items():
                if key not in merged:
                    merged[key] = value
                elif key in self.priority_fields:
                    # 高优先级字段使用第一个值
                    pass
                else:
                    # 其他字段：如果当前为空则覆盖
                    if merged[key] is None or merged[key] == "":
                        merged[key] = value

        # 第二轮：标准化
        merged = self._normalize(merged)

        return merged

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        """标准化 frontmatter"""
        normalized = {}

        # 确保必需字段存在并设置默认值
        defaults = {
            "Type": "Unknown",
            "Status": "ACTIVE",
            "Version": "1.0.0",
            "Owner": "@Unassigned",
            "Updated": datetime.now().strftime("%Y-%m-%d"),
        }

        for key, default in defaults.items():
            value = data.get(key, default)

            # 特殊处理
            if key == "Status" and isinstance(value, str):
                value = value.upper()
            elif key == "Owner" and isinstance(value, str) and "@" in value:
                # 不要手动加引号 - yaml.dump() 会自动处理
                # 只需确保值是字符串
                value = str(value).strip()

            normalized[key] = value

        # 复制其他字段
        for key, value in data.items():
            if key not in normalized:
                normalized[key] = value

        # 确保 Tags 是列表
        if "Tags" in normalized and not isinstance(normalized["Tags"], list):
            if isinstance(normalized["Tags"], str):
                normalized["Tags"] = [normalized["Tags"]]
            else:
                del normalized["Tags"]

        return normalized

    def apply(self, path: Path, merged_fm: dict[str, Any]) -> str:
        """应用合并后的 frontmatter 到文件

        Args:
            path: 文件路径
            merged_fm: 合并后的 frontmatter 字典

        Returns:
            新内容
        """
        content = path.read_text(encoding="utf-8")

        # 移除所有现有 frontmatter - 使用 MULTILINE 确保匹配所有块
        content_no_fm = re.sub(r"(?:^|\n)---\s*\n.*?\n---\s*(?:\n|$)", "", content, flags=re.DOTALL | re.MULTILINE)

        # 去除开头的多余空行
        content_no_fm = content_no_fm.lstrip("\n")

        # 如果内容为空，添加标题占位
        if not content_no_fm.strip():
            content_no_fm = "# Document\n\nContent.\n"

        # 生成新 frontmatter
        fm_yaml = yaml.dump(merged_fm, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # 组合
        new_content = f"---\n{fm_yaml}---\n\n{content_no_fm}"

        return new_content

    def fix_file(self, path: Path, dry_run: bool = True) -> dict[str, Any]:
        """修复单个文件

        Args:
            path: 文件路径
            dry_run: 是否干跑

        Returns:
            修复结果
        """
        start_time = time.time()

        # 检测 frontmatter
        detector = FrontmatterDetector()
        detection = detector.analyze(path)

        result = {
            "file_path": str(path),
            "original_status": detection.status,
            "original_blocks": len(detection.blocks),
            "fixed": False,
            "new_content": None,
            "merged_frontmatter": None,
            "duration_ms": 0,
        }

        # 只有 multiple blocks 或 invalid 才需要修复
        if detection.status not in ["MULTIPLE", "INVALID"]:
            result["duration_ms"] = (time.time() - start_time) * 1000
            return result

        # 转换为字典格式
        block_dicts = [{"is_valid": b.is_valid, "parsed_data": b.parsed_data} for b in detection.blocks]

        # 合并
        merged = self.merge(block_dicts)
        result["merged_frontmatter"] = merged

        # 生成新内容
        new_content = self.apply(path, merged)
        result["new_content"] = new_content

        # 验证修复效果
        temp_path = Path("/tmp/test_fix.md")
        temp_path.write_text(new_content, encoding="utf-8")
        verification = detector.analyze(temp_path)
        temp_path.unlink()

        result["fixed"] = verification.status == "OK"
        result["verification_status"] = verification.status
        result["duration_ms"] = (time.time() - start_time) * 1000

        # 实际应用
        if not dry_run and result["fixed"]:
            path.write_text(new_content, encoding="utf-8")
            _log.info(f"Fixed: {path}")
        elif not dry_run and not result["fixed"]:
            # 即使验证失败也应用（用于测试）
            path.write_text(new_content, encoding="utf-8")
            _log.warning(f"Applied fix despite verification failure: {path}")

        return result

    def fix_batch(self, dir_path: Path, pattern: str = "**/*.md", dry_run: bool = True) -> list[dict[str, Any]]:
        """批量修复

        Args:
            dir_path: 目录
            pattern: 文件模式
            dry_run: 是否干跑

        Returns:
            修复结果列表
        """
        detector = FrontmatterDetector()
        detections = detector.scan_directory(dir_path, pattern=pattern)

        results = []

        for i, detection in enumerate(detections, 1):
            if detection.status in ["MULTIPLE", "INVALID"]:
                if i % 50 == 0:
                    _log.info(f"Fixing {i}/{len(detections)}: {detection.file_path}")

                result = self.fix_file(detection.file_path, dry_run=dry_run)
                results.append(result)

        return results


def main() -> None:
    """CLI 入口"""
    parser = argparse.ArgumentParser(description="Frontmatter Merger - Merge Multiple Blocks")
    parser.add_argument("path", type=str, help="File or directory to fix")
    parser.add_argument("--apply", action="store_true", help="Apply fixes (default: dry-run)")
    parser.add_argument("--pattern", type=str, default="**/*.md", help="File pattern (for directory)")
    parser.add_argument("--output", type=str, help="Output JSON report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    merger = FrontmatterMerger()
    path = Path(args.path)

    if not path.exists():
        _log.error(f"Path not found: {path}")
        sys.exit(1)

    dry_run = not args.apply

    print(f"\n{'=' * 60}")
    print("FRONTMATTER MERGER")
    print(f"{'=' * 60}")
    print(f"Mode: {'APPLY' if not dry_run else 'DRY-RUN'}")
    print(f"Path: {path}")
    print(f"{'=' * 60}\n")

    if path.is_file():
        result = merger.fix_file(path, dry_run=dry_run)

        print(f"File: {result['file_path']}")
        print(f"Original Status: {result['original_status']}")
        print(f"Fixed: {result['fixed']}")

        if result["merged_frontmatter"]:
            print("\nMerged Frontmatter:")
            for key, value in result["merged_frontmatter"].items():
                print(f"  {key}: {value}")

        print(f"\nDuration: {result['duration_ms']:.1f}ms")

        results = [result]

    elif path.is_dir():
        results = merger.fix_batch(path, pattern=args.pattern, dry_run=dry_run)

        total = len(results)
        fixed = sum(1 for r in results if r["fixed"])

        print(f"Total Processed: {total}")
        if total > 0:
            print(f"Successfully Fixed: {fixed} ({fixed / total * 100:.1f}%)")
            avg_duration = sum(r["duration_ms"] for r in results) / len(results)
            print(f"Avg Duration: {avg_duration:.1f}ms")
        else:
            print("No files needed fixing (all files already have valid single frontmatter)")

    if args.output:
        # Convert results to JSON-serializable format
        json_results = []
        for r in results:
            r_copy = r.copy()
            # Convert merged_frontmatter values to strings
            if r_copy.get("merged_frontmatter"):
                for k, v in r_copy["merged_frontmatter"].items():
                    if hasattr(v, "isoformat"):  # date/datetime object
                        r_copy["merged_frontmatter"][k] = v.isoformat()
            json_results.append(r_copy)

        output_data = {
            "timestamp": datetime.now().isoformat(),
            "mode": "apply" if not dry_run else "dry-run",
            "results": json_results,
        }

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        _log.info(f"Report saved to: {output_path}")

    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
