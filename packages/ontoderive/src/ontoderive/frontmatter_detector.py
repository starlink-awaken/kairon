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
# Frontmatter Detector ≡ Module
# 内涵 ≝ {Frontmatter, Detector}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, FrontmatterDetector)}
# 功能 ⊢ {Frontmatter_Detector, Init_Frontmatter, Validate_Detector}
# =============================================================================

# ---
# Type: Module
# Status: ACTIVE
# Layer: L3
# ---
"""
Frontmatter Detector - 增强版 frontmatter 检测

功能:
- 检测单个 frontmatter
- 检测多个 frontmatter 块
- 识别无效 frontmatter
- 提供修复建议

Usage:
    python3 organs/D_Logos/organs/frontmatter_detector.py --check docs/README.md
    python3 organs/D_Logos/organs/frontmatter_detector.py --scan docs/20-architecture/
"""


import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_log = logging.getLogger(__name__)


@dataclass
class FrontmatterBlock:
    """Frontmatter 块"""

    start_line: int
    end_line: int
    start_char: int
    end_char: int
    content: str
    is_valid: bool
    parsed_data: dict[str, Any] | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "content_preview": self.content[:100] if len(self.content) > 100 else self.content,
            "is_valid": self.is_valid,
            "fields": list(self.parsed_data.keys()) if isinstance(self.parsed_data, dict) else [],
            "error_message": self.error_message,
        }


@dataclass
class DetectionResult:
    """检测结果"""

    file_path: Path
    blocks: list[FrontmatterBlock]
    recommendation: str
    scan_duration_ms: float

    @property
    def status(self) -> str:
        if len(self.blocks) == 0:
            return "MISSING"
        elif len(self.blocks) == 1 and self.blocks[0].is_valid:
            return "OK"
        elif len(self.blocks) == 1 and not self.blocks[0].is_valid:
            return "INVALID"
        elif len(self.blocks) > 1:
            return "MULTIPLE"
        else:
            return "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "status": self.status,
            "total_blocks": len(self.blocks),
            "valid_blocks": sum(1 for b in self.blocks if b.is_valid),
            "blocks": [b.to_dict() for b in self.blocks],
            "recommendation": self.recommendation,
            "scan_duration_ms": self.scan_duration_ms,
        }


class FrontmatterDetector:
    """Frontmatter 检测器"""

    def __init__(self) -> None:
        # 更宽松的正则，匹配各种变体
        # 允许 frontmatter 前后有空白行
        self.pattern = re.compile(r"(?:^|\n)---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL | re.MULTILINE)

    def detect(self, content: str) -> list[FrontmatterBlock]:
        """检测所有 frontmatter 块"""
        blocks = []

        for match in self.pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()

            # 计算行号
            start_line = content[:start_pos].count("\n") + 1
            end_line = content[:end_pos].count("\n") + 1

            fm_content = match.group(1)

            # 尝试解析 YAML
            parsed_data = None
            error_msg = None
            is_valid = True

            if yaml:
                try:
                    parsed_data = yaml.safe_load(fm_content)
                    if not isinstance(parsed_data, dict):
                        is_valid = False
                        error_msg = f"Not a dict, got {type(parsed_data).__name__}"
                except yaml.YAMLError as e:
                    is_valid = False
                    error_msg = str(e)[:150]
            else:
                is_valid = False
                error_msg = "PyYAML not available"

            blocks.append(
                FrontmatterBlock(
                    start_line=start_line,
                    end_line=end_line,
                    start_char=start_pos,
                    end_char=end_pos,
                    content=fm_content,
                    is_valid=is_valid,
                    parsed_data=parsed_data,
                    error_message=error_msg,
                )
            )

        return blocks

    def analyze(self, path: Path) -> DetectionResult:
        """分析文档的 frontmatter 情况"""
        start_time = time.time()

        content = path.read_text(encoding="utf-8")
        blocks = self.detect(content)

        # 生成修复建议
        recommendation = self._generate_recommendation(blocks)

        duration_ms = (time.time() - start_time) * 1000

        return DetectionResult(
            file_path=path,
            blocks=blocks,
            recommendation=recommendation,
            scan_duration_ms=duration_ms,
        )

    def _generate_recommendation(self, blocks: list[FrontmatterBlock]) -> str:
        """生成修复建议"""
        if len(blocks) == 0:
            return "ADD_FRONTMATTER"
        elif len(blocks) == 1 and blocks[0].is_valid:
            return "OK"
        elif len(blocks) == 1 and not blocks[0].is_valid:
            return f"FIX_YAML: {blocks[0].error_message}"
        elif len(blocks) > 1:
            valid_count = sum(1 for b in blocks if b.is_valid)
            return f"MERGE_BLOCKS: Found {len(blocks)} blocks ({valid_count} valid)"
        else:
            return "UNKNOWN"

    def scan_directory(self, dir_path: Path, pattern: str = "**/*.md") -> list[DetectionResult]:
        """扫描目录"""
        results = []

        all_files = list(dir_path.glob(pattern))
        _log.info(f"Found {len(all_files)} markdown files")

        for i, file_path in enumerate(all_files, 1):
            if i % 50 == 0:
                _log.info(f"Scanning {i}/{len(all_files)}: {file_path}")

            result = self.analyze(file_path)
            results.append(result)

        return results


def main() -> None:
    """CLI 入口"""
    parser = argparse.ArgumentParser(description="Frontmatter Detector - Enhanced Detection")
    parser.add_argument("path", type=str, help="File or directory to scan")
    parser.add_argument("--output", type=str, help="Output JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--pattern", type=str, default="**/*.md", help="File pattern (for directory scan)")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    detector = FrontmatterDetector()
    path = Path(args.path)

    if not path.exists():
        _log.error(f"Path not found: {path}")
        sys.exit(1)

    if path.is_file():
        result = detector.analyze(path)
        results = [result]

        print(f"\n{'=' * 60}")
        print(f"FRONTMATTER ANALYSIS: {path}")
        print(f"{'=' * 60}")
        print(f"Status: {result.status}")
        print(f"Total Blocks: {len(result.blocks)}")

        if result.blocks:
            for i, block in enumerate(result.blocks, 1):
                print(f"\nBlock {i}:")
                print(f"  Lines: {block.start_line}-{block.end_line}")
                print(f"  Valid: {block.is_valid}")
                if block.parsed_data:
                    print(f"  Fields: {', '.join(block.parsed_data.keys())}")
                if block.error_message:
                    print(f"  Error: {block.error_message}")

        print(f"\nRecommendation: {result.recommendation}")
        print(f"{'=' * 60}\n")

    elif path.is_dir():
        results = detector.scan_directory(path, pattern=args.pattern)

        # 统计
        total = len(results)
        ok = sum(1 for r in results if r.status == "OK")
        missing = sum(1 for r in results if r.status == "MISSING")
        invalid = sum(1 for r in results if r.status == "INVALID")
        multiple = sum(1 for r in results if r.status == "MULTIPLE")

        print(f"\n{'=' * 60}")
        print("DIRECTORY SCAN COMPLETE")
        print(f"{'=' * 60}")
        print(f"Total Files: {total}")
        print(f"OK: {ok} ({ok / total * 100:.1f}%)")
        print(f"Missing: {missing} ({missing / total * 100:.1f}%)")
        print(f"Invalid: {invalid} ({invalid / total * 100:.1f}%)")
        print(f"Multiple: {multiple} ({multiple / total * 100:.1f}%)")
        print(f"{'=' * 60}\n")

    if args.output:
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "scan_path": str(path),
            "results": [r.to_dict() for r in results],
        }

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        _log.info(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
