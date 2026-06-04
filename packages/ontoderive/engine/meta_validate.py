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
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Meta Validate ≡ Module
# 内涵 ≝ {Meta, Validate}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, MetaValidate)}
# 功能 ⊢ {Meta_Validate, Init_Meta, Validate_Validate}
# =============================================================================

# ---
# Type: Module
# Status: ACTIVE
# Layer: L3
# ---
"""
Meta-Validate Engine - 元验证引擎

功能:
- 验证 Quality Probe 的检测结果正确性
- 检测误报率 (False Positive Rate)
- 检测漏报率 (False Negative Rate)
- 自动校准评分算法
- 生成验证报告

Usage:
    python3 -m engine.meta_validate --scan docs/ --sample-size 50
    python3 -m engine.meta_validate --validate-report report.json
    python3 -m engine.meta_validate --calibrate
"""

import argparse
import json
import logging
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from engine.organs.doc_type_validator import DocTypeValidator
from engine.organs.meta_validate_benchmark import _MetaBenchmarkMixin
from engine.organs.meta_validate_persist import _MetaPersistenceMixin
from engine.organs.meta_validate_types import (
    BenchmarkResult,
    ConfidenceScore,
    GroundTruth,
    ValidationIssueSeverity,
    ValidationStatus,
    ValidationVerification,
)
from engine.organs.meta_validate_verify import _MetaVerifyMixin
from engine.organs.quality_probe import QualityProbe, ScanResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_log = logging.getLogger(__name__)

__all__ = [
    "BenchmarkResult",
    "ConfidenceScore",
    "DocTypeValidator",
    "GroundTruth",
    "MetaValidateEngine",
    "MetaValidationReport",
    "ValidationIssueSeverity",
    "ValidationResult",
    "ValidationStatus",
    "ValidationVerification",
]


@dataclass
class ValidationResult:
    """验证结果"""

    file_path: Path
    probe_issues: int
    manual_issues: int
    false_positives: int  # 误报：工具报告但实际没问题
    false_negatives: int  # 漏报：实际有问题但工具没报告
    accuracy: float  # 准确率
    precision: float  # 精确率
    recall: float  # 召回率

    def to_dict(self) -> dict:
        return {
            "file_path": str(self.file_path),
            "probe_issues": self.probe_issues,
            "manual_issues": self.manual_issues,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "accuracy": round(self.accuracy, 2),
            "precision": round(self.precision, 2),
            "recall": round(self.recall, 2),
        }


@dataclass
class MetaValidationReport:
    """元验证报告"""

    timestamp: str
    sample_size: int
    total_results: int
    overall_accuracy: float
    overall_precision: float
    overall_recall: float
    false_positive_rate: float
    false_negative_rate: float
    calibration_suggestions: list[str]
    results: list[ValidationResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "sample_size": self.sample_size,
            "total_results": self.total_results,
            "overall_metrics": {
                "accuracy": round(self.overall_accuracy, 2),
                "precision": round(self.overall_precision, 2),
                "recall": round(self.overall_recall, 2),
                "false_positive_rate": round(self.false_positive_rate, 2),
                "false_negative_rate": round(self.false_negative_rate, 2),
            },
            "calibration_suggestions": self.calibration_suggestions,
            "results": [r.to_dict() for r in self.results],
        }


class MetaValidateEngine(_MetaVerifyMixin, _MetaBenchmarkMixin, _MetaPersistenceMixin):
    """元验证引擎"""

    if TYPE_CHECKING:

        def _load_ground_truths(self) -> None: ...
        def _save_validation_history(self) -> None: ...
        def _verify_syntax(self, report: object) -> tuple[bool, list[str]]: ...
        def _verify_logic(self, report: object) -> tuple[bool, list[str]]: ...
        def _verify_semantic(
            self,
            report: object,
            ground_truth: GroundTruth,
        ) -> tuple[bool, list[object], list[object]]: ...
        def _calculate_confidence(
            self,
            syntax_valid: bool,
            logic_valid: bool,
            semantic_valid: bool,
            fp_count: int,
            fn_count: int,
        ) -> ConfidenceScore: ...
        def _test_syntax_required_fields(self) -> bool: ...
        def _test_syntax_optional_fields(self) -> bool: ...
        def _test_logic_matched_unmatched(self) -> bool: ...
        def _test_logic_alignment_rate(self) -> bool: ...
        def _test_fp_deprecated(self) -> bool: ...
        def _test_fp_optional(self) -> bool: ...
        def _test_fn_public(self) -> bool: ...
        def _test_fn_api(self) -> bool: ...
        def _test_confidence_calc(self) -> bool: ...
        def _test_gt_save_load(self) -> bool: ...
        def _test_semantic_exact(self) -> bool: ...
        def _test_semantic_partial(self) -> bool: ...
        def _test_semantic_missing(self) -> bool: ...
        def _test_semantic_extra(self) -> bool: ...
        def _test_vv_creation(self) -> bool: ...
        def _test_vv_status_valid(self) -> bool: ...
        def _test_vv_status_invalid(self) -> bool: ...
        def _test_history_save(self) -> bool: ...
        def _test_confidence_factors(self) -> bool: ...
        def _test_f1_score(self) -> bool: ...

    def __init__(self, root: Path | str | None = None, config_path: str | None = None) -> None:
        from nucleus.Z_Microkernel.facades import get_path_resolver

        self.status = "active"
        self.root = Path(root) if root is not None else Path("organs/D-Logos")

        # Use canonical data directory via PathResolverFacade
        resolver = get_path_resolver()
        self.data_dir = resolver.resolve("data/organs/memory/logos")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = self._load_config(config_path)
        self.probe = QualityProbe()
        self.doc_type_validator = DocTypeValidator()
        self.ground_truths: dict[str, GroundTruth] = {}
        self.validation_history: list[ValidationVerification] = []
        self._metrics: dict[str, int] = {
            "verifications_run": 0,
            "benchmarks_run": 0,
            "errors": 0,
        }

        # 手动验证规则（简化版，用于对比）
        self.manual_checks = {
            "frontmatter": self._manual_check_frontmatter,
            "formal_summary": self._manual_check_formal_summary,
            "ai_context": self._manual_check_ai_context,
        }
        self._load_ground_truths()

    def health_check(self) -> dict[str, Any]:
        """Return operational health metrics for MetaValidateEngine."""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "organ": "MetaValidateEngine",
            "ground_truth_count": len(self.ground_truths),
            "validation_history_count": len(self.validation_history),
            "metrics": self._metrics,
        }

    def describe(self) -> dict[str, Any]:
        """Return a capability descriptor for MetaValidateEngine."""
        return {
            "name": "MetaValidateEngine",
            "version": "1.0.0",
            "capabilities": [
                "logos.validate.sample",
                "logos.validate.verify",
                "logos.validate.benchmark",
                "logos.validate.ground_truth",
            ],
            "bos_uri": "bos://d-logos/meta-validate",
        }

    def heartbeat(self) -> dict[str, Any]:
        """Return a liveness heartbeat for MetaValidateEngine."""
        return {
            "status": "alive",
            "ts": time.time(),
            "metrics": self._metrics,
        }

    def call(self, *args: object, **kwargs: object) -> dict[str, Any]:
        """Minimal membrane-compatible dispatch entrypoint."""
        action = str(args[0]) if args else str(kwargs.get("action", ""))
        if action == "health":
            return self.health_check()
        if action == "describe":
            return self.describe()
        if action == "heartbeat":
            return self.heartbeat()
        if action == "validate":
            return {"status": "ok", "engine": "MetaValidateEngine", "metrics": self._metrics}
        return {"status": "unknown_action", "action": action}

    def _manual_check_frontmatter(self, content: str) -> bool:
        """手动检查 frontmatter"""
        return content.strip().startswith("---")

    def _manual_check_formal_summary(self, content: str) -> bool:
        """手动检查形式化摘要"""
        return "## 0. 形式化摘要" in content or "## 0." in content

    def _manual_check_ai_context(self, content: str) -> bool:
        """手动检查 AI Context"""
        return "🤖 AI" in content or "AI Semantic Context" in content

    def _load_config(self, config_path: str | None) -> dict[str, float]:
        """加载配置"""
        default_config: dict[str, float] = {
            "accuracy_threshold": 0.85,
            "precision_threshold": 0.80,
            "recall_threshold": 0.80,
            "max_false_positive_rate": 0.10,
            "max_false_negative_rate": 0.15,
        }

        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                loaded = json.load(f)
                default_config.update(loaded)

        return default_config

    def validate_sample(self, scan_dir: Path, sample_size: int = 30, pattern: str = "**/*.md") -> MetaValidationReport:
        """验证随机样本"""

        start_time = time.time()
        _log.info(f"Starting meta-validation with sample size {sample_size}")

        # 获取所有文件
        all_files = list(scan_dir.glob(pattern))
        _log.info(f"Found {len(all_files)} files")

        # 随机抽样
        if len(all_files) > sample_size:
            sampled_files = random.sample(all_files, sample_size)
        else:
            sampled_files = all_files

        _log.info(f"Sampled {len(sampled_files)} files for validation")

        results = []
        total_tp = 0  # True Positives
        total_fp = 0  # False Positives
        total_fn = 0  # False Negatives

        for i, file_path in enumerate(sampled_files, 1):
            if i % 10 == 0:
                _log.info(f"Validating {i}/{len(sampled_files)}: {file_path}")

            result = self._validate_single_file(file_path)
            results.append(result)

            # 累积统计
            true_positives = result.probe_issues - result.false_positives
            total_tp += true_positives
            total_fp += result.false_positives
            total_fn += result.false_negatives

        # 计算整体指标
        total_detected = total_tp + total_fp  # 工具检测到的总数
        total_actual = total_tp + total_fn  # 实际存在的总数

        overall_accuracy = total_tp / (total_tp + total_fp + total_fn) if (total_tp + total_fp + total_fn) > 0 else 0
        overall_precision = total_tp / total_detected if total_detected > 0 else 0
        overall_recall = total_tp / total_actual if total_actual > 0 else 0
        false_positive_rate = total_fp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        false_negative_rate = total_fn / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0

        # 生成校准建议
        calibration_suggestions = self._generate_calibration_suggestions(
            overall_accuracy,
            overall_precision,
            overall_recall,
            false_positive_rate,
            false_negative_rate,
        )

        duration = time.time() - start_time

        report = MetaValidationReport(
            timestamp=datetime.now().isoformat(),
            sample_size=sample_size,
            total_results=len(results),
            overall_accuracy=overall_accuracy,
            overall_precision=overall_precision,
            overall_recall=overall_recall,
            false_positive_rate=false_positive_rate,
            false_negative_rate=false_negative_rate,
            calibration_suggestions=calibration_suggestions,
            results=results,
        )

        _log.info(f"Meta-validation complete in {duration:.2f}s")
        _log.info(f"Accuracy: {overall_accuracy:.2%}, Precision: {overall_precision:.2%}, Recall: {overall_recall:.2%}")

        return report

    def _validate_single_file(self, file_path: Path) -> ValidationResult:
        """验证单个文件"""

        # 1. 运行 Quality Probe
        probe_result = self.probe.scan(file_path)
        probe_issues = len(probe_result.issues)

        # 2. 手动验证（简化规则）
        manual_issues = self._manual_validation(file_path)

        # 3. 对比结果
        false_positives = 0
        false_negatives = 0

        # 简化的对比逻辑
        if probe_issues > manual_issues:
            false_positives = probe_issues - manual_issues
        elif manual_issues > probe_issues:
            false_negatives = manual_issues - probe_issues

        # 4. 计算指标
        true_positives = min(probe_issues, manual_issues)

        accuracy = true_positives / max(probe_issues, manual_issues) if max(probe_issues, manual_issues) > 0 else 1.0
        precision = true_positives / probe_issues if probe_issues > 0 else 1.0
        recall = true_positives / manual_issues if manual_issues > 0 else 1.0

        return ValidationResult(
            file_path=file_path,
            probe_issues=probe_issues,
            manual_issues=manual_issues,
            false_positives=false_positives,
            false_negatives=false_negatives,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
        )

    def _manual_validation(self, file_path: Path) -> int:
        """手动验证（简化规则集）"""
        issues = 0
        content = file_path.read_text(encoding="utf-8")

        # Frontmatter 检查
        if not content.strip().startswith("---"):
            issues += 1

        # 形式化摘要检查
        if "## 0. 形式化摘要" not in content and "## 0." not in content:
            issues += 1

        # AI Context 检查
        if "🤖 AI" not in content and "AI Semantic Context" not in content:
            issues += 1

        return issues

    def _generate_calibration_suggestions(
        self, accuracy: float, precision: float, recall: float, fp_rate: float, fn_rate: float
    ) -> list[str]:
        """生成校准建议"""
        suggestions = []

        if accuracy < self.config["accuracy_threshold"]:
            suggestions.append(
                f"⚠️ Overall accuracy ({accuracy:.2%}) below threshold "
                f"({self.config['accuracy_threshold']:.2%}). "
                "Consider reviewing detection algorithms."
            )

        if precision < self.config["precision_threshold"]:
            suggestions.append(
                f"⚠️ Precision ({precision:.2%}) below threshold "
                f"({self.config['precision_threshold']:.2%}). "
                "Too many false positives - consider tightening detection rules."
            )

        if recall < self.config["recall_threshold"]:
            suggestions.append(
                f"⚠️ Recall ({recall:.2%}) below threshold "
                f"({self.config['recall_threshold']:.2%}). "
                "Too many false negatives - consider adding more detection rules."
            )

        if fp_rate > self.config["max_false_positive_rate"]:
            suggestions.append(
                f"🔴 False positive rate ({fp_rate:.2%}) exceeds maximum "
                f"({self.config['max_false_positive_rate']:.2%}). "
                "Review regex patterns and validation logic."
            )

        if fn_rate > self.config["max_false_negative_rate"]:
            suggestions.append(
                f"🔴 False negative rate ({fn_rate:.2%}) exceeds maximum "
                f"({self.config['max_false_negative_rate']:.2%}). "
                "Add additional checks for missed issue types."
            )

        if not suggestions:
            suggestions.append("✅ All metrics within acceptable thresholds. No calibration needed.")

        return suggestions

    def calibrate_scoring(self, historical_data: list[ScanResult]) -> dict[str, Any]:
        """校准评分算法"""
        _log.info("Calibrating scoring algorithm based on historical data")

        # 分析历史数据分布
        scores = [r.score for r in historical_data]
        if not scores:
            return {"recommendation": "Insufficient data for calibration"}

        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        # 计算分数分布
        high_quality = sum(1 for s in scores if s >= 85) / len(scores)
        medium_quality = sum(1 for s in scores if 70 <= s < 85) / len(scores)
        low_quality = sum(1 for s in scores if s < 70) / len(scores)

        calibration: dict[str, Any] = {
            "current_average": round(avg_score, 2),
            "score_range": f"{min_score} - {max_score}",
            "distribution": {
                "high_quality_85_plus": round(high_quality, 2),
                "medium_quality_70_84": round(medium_quality, 2),
                "low_quality_below_70": round(low_quality, 2),
            },
            "recommendations": [],
        }

        # 生成校准建议
        if avg_score < 70:
            calibration["recommendations"].append(
                "Average score is low. Consider if scoring is too strict or documentation quality needs improvement."
            )

        if high_quality < 0.3:
            calibration["recommendations"].append(
                "Less than 30% of documents are high quality. Consider batch auto-fix campaign."
            )

        if low_quality > 0.3:
            calibration["recommendations"].append(
                "More than 30% of documents are low quality. Prioritize fixing critical issues."
            )

        return calibration

    def run_benchmark(self, suite_name: str) -> BenchmarkResult:
        """Run a lightweight self-benchmark suite for validation helpers."""
        suite_sizes = {
            "tiny": 10,
            "small": 20,
        }
        total_tests = suite_sizes.get(suite_name, 5)
        benchmark_checks = [
            ("syntax_required_fields", self._test_syntax_required_fields),
            ("syntax_optional_fields", self._test_syntax_optional_fields),
            ("logic_matched_unmatched", self._test_logic_matched_unmatched),
            ("logic_alignment_rate", self._test_logic_alignment_rate),
            ("fp_deprecated", self._test_fp_deprecated),
            ("fp_optional", self._test_fp_optional),
            ("fn_public", self._test_fn_public),
            ("fn_api", self._test_fn_api),
            ("confidence_calc", self._test_confidence_calc),
            ("gt_save_load", self._test_gt_save_load),
            ("semantic_exact", self._test_semantic_exact),
            ("semantic_partial", self._test_semantic_partial),
            ("semantic_missing", self._test_semantic_missing),
            ("semantic_extra", self._test_semantic_extra),
            ("vv_creation", self._test_vv_creation),
            ("vv_status_valid", self._test_vv_status_valid),
            ("vv_status_invalid", self._test_vv_status_invalid),
            ("history_save", self._test_history_save),
            ("confidence_factors", self._test_confidence_factors),
            ("f1_score", self._test_f1_score),
        ][:total_tests]

        start = time.time()
        details: list[dict[str, Any]] = []
        passed_tests = 0
        for name, fn in benchmark_checks:
            passed = bool(fn())
            details.append({"name": name, "passed": passed})
            if passed:
                passed_tests += 1

        self._metrics["benchmarks_run"] += 1
        failed_tests = total_tests - passed_tests
        pass_rate = passed_tests / total_tests if total_tests else 0.0
        return BenchmarkResult(
            suite_name=suite_name,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            pass_rate=pass_rate,
            details=details,
            duration=time.time() - start,
        )

    def verify_alignment_result(
        self,
        alignment_report: object,
        ground_truth: GroundTruth | None = None,
    ) -> ValidationVerification:
        """Verify an alignment report against structural and semantic expectations."""
        syntax_valid, _ = self._verify_syntax(alignment_report)
        logic_valid, _ = self._verify_logic(alignment_report)

        if ground_truth is None:
            ground_truth = GroundTruth.create_from_audit(
                project="D-Logos",
                version="1.0.0",
                files={},
                expected_alignment={"issues": []},
            )

        semantic_valid, false_positives, false_negatives = self._verify_semantic(
            alignment_report,
            ground_truth,
        )
        confidence = self._calculate_confidence(
            syntax_valid=syntax_valid,
            logic_valid=logic_valid,
            semantic_valid=semantic_valid,
            fp_count=len(false_positives),
            fn_count=len(false_negatives),
        )

        if syntax_valid and logic_valid and semantic_valid:
            status = ValidationStatus.VALID
        elif syntax_valid or logic_valid or semantic_valid:
            status = ValidationStatus.PARTIAL
        else:
            status = ValidationStatus.INVALID

        verification = ValidationVerification(
            id=f"VV-{len(self.validation_history) + 1:04d}",
            alignment_report_id=str(getattr(alignment_report, "id", "unknown-report")),
            status=status,
            confidence=confidence,
            false_positives=false_positives,
            false_negatives=false_negatives,
        )
        self.validation_history.append(verification)
        self._metrics["verifications_run"] += 1
        self._save_validation_history()
        return verification


def main() -> None:
    """CLI 入口"""
    parser = argparse.ArgumentParser(description="Meta-Validate Engine - Verify Quality Probe Accuracy")
    parser.add_argument("--scan", type=str, help="Directory to scan for validation")
    parser.add_argument("--sample-size", type=int, default=30, help="Number of files to sample")
    parser.add_argument("--output", type=str, help="Output JSON report path")
    parser.add_argument("--calibrate", action="store_true", help="Run calibration on historical data")
    parser.add_argument("--config", type=str, help="Config file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    engine = MetaValidateEngine(config_path=args.config)

    if args.scan:
        scan_dir = Path(args.scan)
        if not scan_dir.exists():
            _log.error(f"Directory not found: {scan_dir}")
            sys.exit(1)

        report = engine.validate_sample(scan_dir, sample_size=args.sample_size)

        # 打印报告摘要
        print("\n" + "=" * 80)
        print("META-VALIDATION REPORT")
        print("=" * 80)
        print(f"Timestamp: {report.timestamp}")
        print(f"Sample Size: {report.sample_size} files")
        print(f"Total Validated: {report.total_results} files")
        print()
        print("Overall Metrics:")
        print(f"  Accuracy:  {report.overall_accuracy:.2%}")
        print(f"  Precision: {report.overall_precision:.2%}")
        print(f"  Recall:    {report.overall_recall:.2%}")
        print(f"  FP Rate:   {report.false_positive_rate:.2%}")
        print(f"  FN Rate:   {report.false_negative_rate:.2%}")
        print()
        print("Calibration Suggestions:")
        for suggestion in report.calibration_suggestions:
            print(f"  {suggestion}")
        print("=" * 80)

        # 保存详细报告
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            _log.info(f"Detailed report saved to: {output_path}")

    elif args.calibrate:
        # Load historical scan data for calibration
        history_file = engine.data_dir / "validation_history.json"
        gt_file = engine.data_dir / "ground_truths.json"

        history_data: list[dict] = []
        if history_file.exists():
            try:
                with open(history_file, encoding="utf-8") as f:
                    raw = json.load(f)
                    history_data = raw.get("validations", [])
                _log.info(f"Loaded {len(history_data)} historical validation records")
            except (json.JSONDecodeError, OSError) as e:
                _log.warning(f"Failed to load validation history: {e}")

        gt_data: list[dict] = []
        if gt_file.exists():
            try:
                with open(gt_file, encoding="utf-8") as f:
                    raw = json.load(f)
                    gt_data = raw.get("ground_truths", [])
                _log.info(f"Loaded {len(gt_data)} ground truth records")
            except (json.JSONDecodeError, OSError) as e:
                _log.warning(f"Failed to load ground truths: {e}")

        if not history_data and not gt_data:
            print("No historical scan data found for calibration.")
            print("Expected files at:")
            print(f"  {history_file}")
            print(f"  {gt_file}")
            print("Use --scan to generate new validation data first.")
        else:
            # Compute calibration metrics from history
            print("\n" + "=" * 80)
            print("CALIBRATION REPORT")
            print("=" * 80)
            print(f"Validation records:  {len(history_data)}")
            print(f"Ground truths:       {len(gt_data)}")

            avg_confidence = 0.0
            if history_data:
                confidences = [v.get("confidence", 0.0) for v in history_data]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                status_counts: dict[str, int] = {}
                for v in history_data:
                    s = v.get("status", "unknown")
                    status_counts[s] = status_counts.get(s, 0) + 1

                print(f"\nAvg confidence:      {avg_confidence:.2%}")
                print("Status distribution:")
                for status, count in sorted(status_counts.items()):
                    print(f"  {status}: {count}")

            suggestions = (
                engine._generate_calibration_suggestions(
                    avg_confidence,
                    avg_confidence,
                    avg_confidence,
                    0.0,
                    0.0,
                )
                if history_data
                else []
            )
            if suggestions:
                print("\nCalibration suggestions:")
                for s in suggestions:
                    print(f"  • {s}")
            print("=" * 80)


if __name__ == "__main__":
    main()
