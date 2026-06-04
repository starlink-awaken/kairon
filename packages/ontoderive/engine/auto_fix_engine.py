from __future__ import annotations

#!/usr/bin/env python3
"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# ---
# Type: Module
# Status: ACTIVE
# Layer: L3
# ---
"""
Auto-Fix Engine - 文档问题自动修复引擎

功能:
- Frontmatter 自动补充
- 命名违规自动重命名
- 形式化摘要模板插入
- AI Context 模板插入
- 批量修复处理

Usage:
    python3 -m organs.D_Logos.organs.auto_fix_engine --fix docs/README.md
    python3 -m organs.D_Logos.organs.auto_fix_engine --batch docs/ --dry-run
"""

import argparse
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

# Import QualityIssue from quality_probe
from .quality_probe import QualityIssue

_log = logging.getLogger(__name__)


class FixType(Enum):
    """修复类型"""

    NAMING = "naming"
    FRONTMATTER = "frontmatter"
    FORMAL_SUMMARY = "formal_summary"
    AI_CONTEXT = "ai_context"
    AUTHORITY = "authority"


@dataclass
class AutoFixResult:
    """自动修复结果"""

    file_path: Path
    fix_type: FixType
    success: bool
    before: str
    after: str
    confidence: float
    requires_review: bool
    duration_ms: float = 0.0
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "file_path": str(self.file_path),
            "fix_type": self.fix_type.value,
            "success": self.success,
            "confidence": self.confidence,
            "requires_review": self.requires_review,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
        }


class AutoFixEngine:
    """自动修复引擎"""

    def __init__(self, config_path: str | None = None) -> None:
        self.config = self._load_config(config_path)

        # 注册修复策略
        self.fix_strategies: dict[FixType, Callable[[Path, QualityIssue, str], str]] = {
            FixType.NAMING: self._fix_naming,
            FixType.FRONTMATTER: self._fix_frontmatter,
            FixType.FORMAL_SUMMARY: self._add_formal_summary_stub,
            FixType.AI_CONTEXT: self._add_ai_context_stub,
            FixType.AUTHORITY: self._fix_authority,
        }

        _log.info("Auto-Fix Engine initialized")

    def fix_metadata(self, path: Path, suggested_metadata: dict[str, Any], dry_run: bool = True) -> AutoFixResult:
        """[PB-5] 专项修复元数据逻辑"""
        start_time = time.time()
        content = path.read_text(encoding="utf-8")
        before_content = content

        # 增强型 frontmatter 修复：直接合并建议的元数据
        if yaml is None:
            raise ImportError("PyYAML required for metadata fix")

        match = re.search(r"^---\s*\n(.*?)\n---\s*$", content, re.DOTALL)
        fm = yaml.safe_load(match.group(1)) if match else {}
        fm.update(suggested_metadata)
        fm["Updated"] = datetime.now().strftime("%Y-%m-%d")

        fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
        if match:
            after_content = content.replace(match.group(0), f"---\n{fm_yaml}---")
        else:
            after_content = f"---\n{fm_yaml}---\n\n{content}"

        if not dry_run and after_content != before_content:
            path.write_text(after_content, encoding="utf-8")

        return AutoFixResult(
            file_path=path,
            fix_type=FixType.FRONTMATTER,
            success=after_content != before_content,
            before=before_content,
            after=after_content,
            confidence=1.0,
            requires_review=False,
            duration_ms=(time.time() - start_time) * 1000,
        )

    def _fix_authority(self, path: Path, issue: QualityIssue, content: str) -> str:
        """修复 Authority 字段错误"""
        suggested_auth = issue.context.get("suggested_authority", "docs/AGENTS.md")
        return self._update_frontmatter_field(content, "Authority", suggested_auth)

    def _update_frontmatter_field(self, content: str, field: str, value: object) -> str:
        """更新 frontmatter 中的单个字段"""
        if yaml is None:
            return content
        match = re.search(r"^---\s*\n(.*?)\n---\s*$", content, re.DOTALL)
        if not match:
            return content

        fm = yaml.safe_load(match.group(1))
        fm[field] = value
        fm["Updated"] = datetime.now().strftime("%Y-%m-%d")

        fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return content.replace(match.group(0), f"---\n{fm_yaml}---")

    def auto_fix(self, issue: QualityIssue, content: str | None = None) -> AutoFixResult:
        """自动修复单个问题"""
        start_time = time.time()

        if not issue.auto_fixable:
            return AutoFixResult(
                file_path=issue.file_path,
                fix_type=FixType(issue.check_type),
                success=False,
                before="",
                after="",
                confidence=0.0,
                requires_review=True,
                duration_ms=0,
                error_message="Issue is not auto-fixable",
            )

        # 读取内容
        if content is None:
            content = issue.file_path.read_text(encoding="utf-8")

        before_content = content

        try:
            # 获取修复策略
            strategy = self.fix_strategies.get(FixType(issue.check_type))

            if not strategy:
                return AutoFixResult(
                    file_path=issue.file_path,
                    fix_type=FixType(issue.check_type),
                    success=False,
                    before=before_content,
                    after=content,
                    confidence=0.0,
                    requires_review=True,
                    duration_ms=(time.time() - start_time) * 1000,
                    error_message=f"No strategy for {issue.check_type}",
                )

            # 执行修复
            content = strategy(issue.file_path, issue, content)

            # 计算置信度
            confidence = self._calculate_confidence(issue, before_content, content)

            # 判断是否需要人工审查
            requires_review = self._requires_human_review(issue, before_content, content)

            success = before_content != content

            result = AutoFixResult(
                file_path=issue.file_path,
                fix_type=FixType(issue.check_type),
                success=success,
                before=before_content,
                after=content,
                confidence=confidence,
                requires_review=requires_review,
                duration_ms=(time.time() - start_time) * 1000,
            )

            _log.info(f"Fixed {issue.check_type} in {issue.file_path}: {success}")
            return result

        except (ImportError, OSError, RuntimeError, TypeError, ValueError, KeyError) as e:
            _log.error(f"Auto-fix failed for {issue.file_path}: {e}")
            return AutoFixResult(
                file_path=issue.file_path,
                fix_type=FixType(issue.check_type),
                success=False,
                before=before_content,
                after=content,
                confidence=0.0,
                requires_review=True,
                duration_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
            )

    def fix_all(self, issues: list[QualityIssue], dry_run: bool = True) -> list[AutoFixResult]:
        """批量自动修复"""
        results = []

        # 按文件分组问题
        issues_by_file: dict[Path, list[QualityIssue]] = {}
        for issue in issues:
            if issue.auto_fixable:
                if issue.file_path not in issues_by_file:
                    issues_by_file[issue.file_path] = []
                issues_by_file[issue.file_path].append(issue)

        _log.info(f"Processing {len(issues_by_file)} files with auto-fixable issues")

        # 逐个文件修复
        for file_path, file_issues in issues_by_file.items():
            try:
                original_content = file_path.read_text(encoding="utf-8")
                new_content = original_content

                file_results = []
                for issue in file_issues:
                    result = self.auto_fix(issue, new_content)
                    if result.success:
                        new_content = result.after
                    file_results.append(result)

                # 如果内容有变化且不是 dry-run，写入文件
                if new_content != original_content and not dry_run:
                    file_path.write_text(new_content, encoding="utf-8")
                    _log.info(f"Updated {file_path}")

                results.extend(file_results)

            except (OSError, RuntimeError, TypeError, ValueError, KeyError) as e:
                _log.error(f"Failed to process {file_path}: {e}")

        return results

    # ========== 修复策略实现 ==========

    def _fix_naming(self, path: Path, issue: QualityIssue, content: str) -> str:
        """修复命名违规"""
        filename = path.name

        # 策略 1: 全大写转小写
        if filename.isupper():
            new_filename = filename.lower().replace("_", "-")
            issue.context["suggested_name"] = new_filename
            _log.warning(f"Suggest rename: {filename} → {new_filename}")
            # 注意：实际重命名需要文件系统操作，这里只返回建议
            return content

        # 策略 2: 下划线转连字符
        if "_" in filename and not filename.startswith("__"):
            new_filename = filename.replace("_", "-").lower()
            issue.context["suggested_name"] = new_filename
            _log.warning(f"Suggest rename: {filename} → {new_filename}")
            return content

        # 策略 3: 添加日期前缀（针对 Process 文档）
        if issue.context.get("needs_date_prefix"):
            today = datetime.now().strftime("%Y%m%d")
            new_filename = f"{today}-{filename.lower()}"
            issue.context["suggested_name"] = new_filename
            _log.warning(f"Suggest rename: {filename} → {new_filename}")
            return content

        return content

    def _fix_frontmatter(self, path: Path, issue: QualityIssue, content: str) -> str:
        """修复 Frontmatter 缺失"""
        if yaml is None:
            _log.error("PyYAML not available, skipping frontmatter fix")
            return content

        # 解析现有 frontmatter
        match = re.search(r"^---\s*\n(.*?)\n---\s*$", content, re.DOTALL)

        if match:
            fm = yaml.safe_load(match.group(1))
        else:
            fm = {}

        # 补充缺失字段
        required_fields = {
            "Type": issue.context.get("suggested_type", "Unknown"),
            "Status": "ACTIVE",
            "Version": "1.0.0",
            "Owner": "@Unassigned",  # 需要人工确认
            "Authority": "docs/AGENTS.md",
            "Updated": datetime.now().strftime("%Y-%m-%d"),
        }

        missing_field = issue.context.get("missing_field")
        if missing_field and missing_field not in fm:
            fm[missing_field] = required_fields[missing_field]

        # 如果是整个 frontmatter 缺失
        if issue.context.get("missing") == "entire_frontmatter":
            for key, value in required_fields.items():
                if key not in fm:
                    fm[key] = value

        # 重建 frontmatter
        fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)

        if match:
            content = content.replace(match.group(0), f"---\n{fm_yaml}---")
        else:
            content = f"---\n{fm_yaml}---\n\n{content}"

        return content

    def _add_formal_summary_stub(self, path: Path, issue: QualityIssue, content: str) -> str:
        """添加形式化摘要模板"""
        stub = """
## 0. 形式化摘要 ≝

```logic
Document(Name) :
    Define(Goal)    : [待补充 - 一句话描述文档目标]
    Define(Scope)   : [待补充 - 适用范围]
□ (Success_Criteria)
Constraint: "[!!]" (关键约束)
```

"""
        # 插入到第一个一级标题之前
        match = re.search(r"\n# ", content)
        if match:
            content = content[: match.start()] + stub + content[match.start() :]
        else:
            # 如果没有一级标题，添加到开头
            content = stub + content

        return content

    def _add_ai_context_stub(self, path: Path, issue: QualityIssue, content: str) -> str:
        """添加 AI Semantic Context 模板"""
        stub = """
## 🤖 AI Semantic Context

> **AI 指引**: [待补充 - AI 应如何理解和使用此文档]
>
> **使用时机**:
> 1. [场景 1 - 待补充]
> 2. [场景 2 - 待补充]
>
> **禁止行为**:
> - [禁止事项 1 - 待补充]

"""
        # 插入到形式化摘要之后
        match = re.search(r"## 0\. 形式化摘要.*?\n```", content, re.DOTALL)
        if match:
            end_pos = match.end()
            # 找到代码块结束位置
            code_block_end = content.find("```\n", end_pos) + 4
            if code_block_end > 3:
                content = content[:code_block_end] + stub + content[code_block_end:]
            else:
                content = content + stub
        else:
            # 如果没有形式化摘要，添加到开头
            content = stub + content

        return content

    # ========== 辅助方法 ==========

    def _calculate_confidence(self, issue: QualityIssue, before: str, after: str) -> float:
        """计算修复置信度"""
        base_confidence = 0.85

        # 根据修复类型调整
        if issue.check_type == "naming":
            return 0.95  # 命名修复很可靠
        elif issue.check_type == "frontmatter":
            return 0.80  # frontmatter 修复需要人工确认 Owner
        elif issue.check_type in ["formal_summary", "ai_context"]:
            return 0.75  # 模板插入较可靠，但内容需要填充

        return base_confidence

    def _requires_human_review(self, issue: QualityIssue, before: str, after: str) -> bool:
        """判断是否需要人工审查"""
        # Owner 修改、Authority 修改等需要人工确认
        if issue.check_type == "frontmatter":
            return True

        # 低置信度修复需要审查
        confidence = self._calculate_confidence(issue, before, after)
        if confidence < 0.7:
            return True

        return False

    def _load_config(self, config_path: str | None) -> dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "auto_fix_enabled": True,
            "require_review_for": ["authority_change", "owner_change"],
            "min_confidence": 0.7,
        }

        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                default_config.update(json.load(f))

        return default_config


def main() -> None:
    """CLI 入口"""
    parser = argparse.ArgumentParser(description="Auto-Fix Engine - Document Issue Fixer")
    parser.add_argument("path", type=str, help="File or directory to fix")
    parser.add_argument(
        "--fix-type",
        choices=["naming", "frontmatter", "formal_summary", "ai_context"],
        nargs="+",
        help="Types of fixes to apply",
    )
    parser.add_argument("--batch", action="store_true", help="Batch mode for directories")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed without making changes")
    parser.add_argument("--output", type=str, help="Output JSON report file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    path = Path(args.path)

    print(f"\n{'=' * 60}")
    print("AUTO-FIX ENGINE")
    print(f"{'=' * 60}")
    print(f"Target: {path}")
    print(f"Dry run: {args.dry_run}")

    from .quality_probe import QualityProbe

    probe = QualityProbe()
    engine = AutoFixEngine()

    if path.is_file():
        scan_result = probe.scan(path)
        issues = scan_result.issues
        print(f"\nScanned 1 file — found {len(issues)} issue(s) (score: {scan_result.score:.1f})")
    elif path.is_dir():
        scan_results = probe.scan_directory(path)
        issues = [issue for result in scan_results for issue in result.issues]
        avg_score = sum(r.score for r in scan_results) / len(scan_results) if scan_results else 0.0
        print(f"\nScanned {len(scan_results)} file(s) — found {len(issues)} issue(s) (avg score: {avg_score:.1f})")
    else:
        print(f"\nError: {path} is not a valid file or directory")
        return

    if not issues:
        print("\n✅ No issues found — nothing to fix.")
        return

    # Filter by requested fix types if specified
    if args.fix_type:
        issues = [i for i in issues if i.check_type in args.fix_type]
        print(f"Filtered to {len(issues)} issue(s) matching types: {args.fix_type}")

    results = engine.fix_all(issues, dry_run=args.dry_run)

    # Print results summary
    applied = [r for r in results if r.applied]
    skipped = [r for r in results if not r.applied]
    print(f"\n{'=' * 60}")
    print(f"Results: {len(applied)} applied, {len(skipped)} skipped")
    for r in applied:
        print(f"  ✅ {r.fix_type.value}: {r.file_path}")
    for r in skipped:
        print(f"  ⏭️  {r.fix_type.value}: {r.file_path} — {r.error or 'skipped'}")

    # Export report if requested
    if args.output:
        report = {
            "timestamp": datetime.now().isoformat(),
            "target": str(path),
            "dry_run": args.dry_run,
            "total_issues": len(issues),
            "applied": len(applied),
            "skipped": len(skipped),
            "results": [
                {
                    "file": str(r.file_path),
                    "fix_type": r.fix_type.value,
                    "applied": r.applied,
                    "error": r.error,
                }
                for r in results
            ],
        }
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
