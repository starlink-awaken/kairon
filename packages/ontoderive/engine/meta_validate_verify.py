from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Meta Validate Verify ≡ Module
# 内涵 ≝ {Meta, Validate, Verify}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, MetaValidateVerify)}
# 功能 ⊢ {Meta_Validate, Validate_Verify, Verify_Init}
# =============================================================================


import logging

_log = logging.getLogger(__name__)

from engine.meta_validate_types import (
    ConfidenceScore,
    FalseNegative,
    FalseNegativeType,
    FalsePositive,
    FalsePositiveType,
    GroundTruth,
)


class _MetaVerifyMixin:
    """Verification and confidence-scoring helpers extracted from MetaValidateEngine.

    Provides _verify_syntax, _verify_logic, _verify_semantic,
    _calculate_confidence, calculate_confidence, _is_likely_false_positive,
    and _is_likely_false_negative.
    Mixed into MetaValidateEngine in meta_validate.py.
    """

    def _verify_syntax(self, report: object) -> tuple[bool, list[str]]:
        """语法验证"""
        errors = []

        # 检查必填字段
        required_fields = ["total_declarations", "total_entities", "matched_count"]
        for req_field in required_fields:
            if not hasattr(report, req_field):
                errors.append(f"缺少必填字段: {req_field}")

        return len(errors) == 0, errors

    def _verify_logic(self, report: object) -> tuple[bool, list[str]]:
        """逻辑验证"""
        errors = []

        total = getattr(report, "total_declarations", 0)
        matched = getattr(report, "matched_count", 0)
        unmatched = getattr(report, "unmatched_doc_count", 0)

        if matched + unmatched > total:
            errors.append("逻辑错误: matched + unmatched > total")

        return len(errors) == 0, errors

    def _verify_semantic(
        self,
        report: object,
        ground_truth: GroundTruth,
    ) -> tuple[bool, list[FalsePositive], list[FalseNegative]]:
        """语义验证"""
        _log.info("  执行语义验证...")
        false_positives = []
        false_negatives = []

        # 获取报告中的问题
        report_issues = getattr(report, "issues", [])
        report_issue_ids = {getattr(issue, "declaration_name", f"unknown-{i}") for i, issue in enumerate(report_issues)}

        # 获取基准真值中的期望问题
        expected_issues = ground_truth.expected_alignment.get("issues", [])
        expected_issue_ids = {issue.get("declaration_name", f"expected-{i}") for i, issue in enumerate(expected_issues)}

        # 检测误报：报告中有但基准真值中没有
        fp_count = 0
        for i, issue in enumerate(report_issues):
            issue_name = getattr(issue, "declaration_name", f"unknown-{i}")
            if issue_name not in expected_issue_ids:
                fp = FalsePositive(
                    id=f"FP-{fp_count:04d}",
                    declaration_name=issue_name,
                    issue_type=FalsePositiveType.PATTERN_MISMATCH,
                    description=f"报告标记问题但基准真值未标记: {issue_name}",
                    original_alignment_issue_id=getattr(issue, "id", f"issue-{i}"),
                    root_cause="模式匹配差异或上下文缺失",
                    suggestion="人工审核确认是否为误报",
                )
                false_positives.append(fp)
                fp_count += 1

        # 检测漏报：基准真值中有但报告中没有
        fn_count = 0
        for i, expected in enumerate(expected_issues):
            expected_name = expected.get("declaration_name", f"expected-{i}")
            if expected_name not in report_issue_ids:
                fn = FalseNegative(
                    id=f"FN-{fn_count:04d}",
                    declaration_name=expected_name,
                    issue_type=FalseNegativeType.PATTERN_MISSING,
                    description=f"基准真值标记问题但报告未标记: {expected_name}",
                    expected_issue=expected.get("description", ""),
                    root_cause="可能缺少匹配模式",
                    suggestion="添加匹配规则或更新模式",
                )
                false_negatives.append(fn)
                fn_count += 1

        # 检查整体匹配率
        total_issues = max(len(report_issues), len(expected_issues))

        # If there are no issues in either the report or ground-truth the
        # validation is trivially correct — nothing to flag, nothing missing.
        if total_issues == 0:
            _log.info("  语义验证: 无问题 → 通过 (trivially valid)")
            return True, [], []

        match_count = len(report_issue_ids & expected_issue_ids)
        match_rate = match_count / total_issues

        valid = match_rate >= 0.7
        _log.info("  语义匹配率: {match_rate:.1%} ({match_count}/{total_issues})")
        _log.info("  误报: {len(false_positives)}")
        _log.info("  漏报: {len(false_negatives)}")

        return valid, false_positives, false_negatives

    def _calculate_confidence(
        self,
        syntax_valid: bool,
        logic_valid: bool,
        semantic_valid: bool,
        fp_count: int,
        fn_count: int,
    ) -> ConfidenceScore:
        """计算置信度"""
        # 基础分数
        base_score = 0.0
        if syntax_valid:
            base_score += 0.3
        if logic_valid:
            base_score += 0.3
        if semantic_valid:
            base_score += 0.2

        # 误报/漏报惩罚
        penalty = min(0.3, (fp_count + fn_count) * 0.05)
        score = max(0.0, base_score - penalty)

        # 简化的 precision/recall
        precision = max(0.5, 1.0 - fp_count * 0.05)
        recall = max(0.5, 1.0 - fn_count * 0.05)
        f1 = 2 * precision * recall / max(0.001, precision + recall)

        return ConfidenceScore(
            score=score,
            precision=precision,
            recall=recall,
            f1_score=f1,
            benchmark_pass_rate=0.9,  # 假设基准测试通过率
            factors={
                "syntax": 0.3 if syntax_valid else 0.0,
                "logic": 0.3 if logic_valid else 0.0,
                "semantic": 0.2 if semantic_valid else 0.0,
                "penalty": -penalty,
            },
        )

    def _is_likely_false_positive(self, issue: object) -> bool:
        """判断是否可能是误报"""
        # 简单启发式规则
        desc = getattr(issue, "description", "").lower()
        if "deprecated" in desc or "optional" in desc:
            return True
        return False

    def _is_likely_false_negative(self, entity: dict) -> bool:
        """判断是否可能是漏报"""
        # 简单启发式规则
        name = entity.get("name", "").lower()
        if "public" in name or "api" in name:
            return True
        return False

    def calculate_confidence(
        self,
        alignment_report: object,
    ) -> ConfidenceScore:
        """计算验证结果的置信度"""
        # 基于报告质量计算置信度
        issues = getattr(alignment_report, "issues", [])
        total_declarations = getattr(alignment_report, "total_declarations", 100)
        matched_count = getattr(alignment_report, "matched_count", 90)

        precision = matched_count / max(1, matched_count + len(issues))
        recall = matched_count / max(1, total_declarations)
        f1 = 2 * precision * recall / max(0.001, precision + recall)

        # 简单基准测试通过率
        benchmark_pass_rate = 0.9

        # 综合评分
        score = 0.4 * precision + 0.4 * recall + 0.2 * benchmark_pass_rate

        return ConfidenceScore(
            score=score,
            precision=precision,
            recall=recall,
            f1_score=f1,
            benchmark_pass_rate=benchmark_pass_rate,
            factors={
                "precision": precision,
                "recall": recall,
                "benchmark": benchmark_pass_rate,
            },
        )
