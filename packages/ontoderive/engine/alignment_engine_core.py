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
# Engine ≡ Engine
# 内涵 ≝ {Engine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Engine)}
# 功能 ⊢ {Init_Engine, Execute_Engine, Validate_Engine}
# =============================================================================

# ---
# domain: D-Logos
# layer: organ
# status: active
# version: 10.5.0
# owner: '@Architect'
# authority: organs/D-Logos/AGENTS.md
# ---
"""AlignmentEngine core implementation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .alignment_models import (
    AlignmentCategory,
    AlignmentIssue,
    AlignmentSeverity,
    EnhancedDiffReport,
    ScanResult,
)
from .alignment_renderers import generate_html_report, generate_json_report, generate_markdown_report

if TYPE_CHECKING:
    from .diff_analyzer import DiffAnalyzer, DiffReport, MatchResult
    from .doc_extractor import DocStatementExtractor
    from .impl_scanner import ImplementationScanner
_log = logging.getLogger(__name__)

class AlignmentEngine:
    """
    ---
    Type: Organ
    Status: Stable
    Layer: L3-Logos
    Summary: AlignmentEngine - unified interface for doc-code alignment verification
    ---
    """

    def __init__(self, root: Path = Path(".")) -> None:
        self.status = "active"
        self.root = root
        self.output_dir = root / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._doc_extractor = None
        self._impl_scanner = None
        self._diff_analyzer = None

    def health_check(self) -> dict:
        """Return operational health metrics."""
        return {
            "status": "healthy",
            "organ": "AlignmentEngine",
            "root": str(self.root),
            "doc_extractor_ready": self._doc_extractor is not None,
            "impl_scanner_ready": self._impl_scanner is not None,
        }

    def _check_doc_access(
        self,
        doc_path: str,
        requesting_agent: str | None = None,
    ) -> bool:
        """Basic access control for document reads."""
        _log.debug("Document access: agent=%r path=%r", requesting_agent, doc_path)
        try:
            mod = __import__(
                "organs.D_Immunity.organs.permission_guard",
                fromlist=["PermissionGuard", "PermissionContext"],
            )
            PermissionGuard = mod.PermissionGuard  # noqa: N806
            PermissionContext = mod.PermissionContext  # noqa: N806
            guard = PermissionGuard()
            ctx = PermissionContext(
                role_id=requesting_agent or "anonymous",
                worker_id=requesting_agent or "anonymous",
                operation="read",
                resource=doc_path,
            )
            guard.check_permission(ctx)
            return True
        except (ImportError, KeyError, AttributeError):
            try:
                from engine.organs.fault_tolerance_policy import (  # type: ignore[import-not-found]
                    FaultContext,
                    FaultTolerancePolicy,
                )

                policy = FaultTolerancePolicy()
                decision = policy.evaluate(
                    FaultContext(
                        operation="doc_access_check",
                        severity="low",
                        system_health=0.8,
                        retry_count=0,
                    )
                )
                _log.debug(
                    "FaultTolerancePolicy decision: allow=%s reason=%s",
                    decision.allow,
                    decision.reason,
                )
                return decision.allow
            except Exception:
                _log.warning(
                    "FaultTolerancePolicy unavailable during document access check; defaulting to deny",
                    exc_info=True,
                )
                return False

    def scan(
        self,
        docs_dir: Path | None = None,
        code_dir: Path | None = None,
        skip_docs: bool = False,
        skip_code: bool = False,
        requesting_agent: str | None = None,
    ) -> ScanResult:
        """扫描文档和代码"""
        import time

        start_time = time.time()
        docs_path = docs_dir or self.root / "docs"

        if not self._check_doc_access(str(docs_path), requesting_agent):
            raise PermissionError(f"Document access denied: {docs_path}")

        doc_ast_path = self.output_dir / "doc-ast.json"
        impl_manifest_path = self.output_dir / "impl-manifest.json"
        doc_count = 0
        code_entity_count = 0

        if not skip_docs:
            _log.info("📄 扫描文档目录: {docs_path}")
            extractor = self._get_doc_extractor()
            extractor.extract_from_directory(docs_path)
            extractor.export_ast(doc_ast_path)
            doc_count = len(extractor.documents)
            _log.info("  ✅ 文档扫描完成: {doc_count} 个文档")

        if not skip_code:
            _log.info("🔍 扫描代码目录: {code_path}")
            scanner = self._get_impl_scanner()
            manifest = scanner.scan()
            scanner.export_manifest(impl_manifest_path)
            code_entity_count = (
                len(manifest.modules) + len(manifest.classes) + len(manifest.functions) + len(manifest.methods)
            )
            _log.info("  ✅ 代码扫描完成: {code_entity_count} 个实体")

        scan_time = time.time() - start_time
        return ScanResult(
            doc_ast_path=doc_ast_path,
            impl_manifest_path=impl_manifest_path,
            doc_count=doc_count,
            code_entity_count=code_entity_count,
            scan_time=scan_time,
        )

    def analyze(
        self,
        doc_ast_path: Path | None = None,
        impl_manifest_path: Path | None = None,
    ) -> EnhancedDiffReport:
        """分析差异"""
        doc_path = doc_ast_path or self.output_dir / "doc-ast.json"
        impl_path = impl_manifest_path or self.output_dir / "impl-manifest.json"

        if not doc_path.exists():
            raise FileNotFoundError(f"文档 AST 不存在: {doc_path}")
        if not impl_path.exists():
            raise FileNotFoundError(f"实现清单不存在: {impl_path}")

        _log.info("🔍 分析文档-实现差异...")
        analyzer = self._get_diff_analyzer()
        report = analyzer.analyze(doc_path, impl_path)
        enhanced = self._enhance_report(report)

        _log.info("  ✅ 分析完成:")
        _log.info("     对齐率: {enhanced.alignment_rate:.1f}%")
        _log.info("     问题数: {len(enhanced.issues)}")
        _log.info("     严重: {enhanced.by_severity.get('critical', 0)}")
        _log.info("     高: {enhanced.by_severity.get('high', 0)}")
        return enhanced

    def generate_report(
        self,
        output_path: Path,
        format: str = "markdown",
        enhanced_report: EnhancedDiffReport | None = None,
    ) -> None:
        """生成报告"""
        report = enhanced_report or self.analyze()

        if format == "markdown":
            content = self._generate_markdown_report(report)
        elif format == "json":
            content = self._generate_json_report(report)
        elif format == "html":
            content = self._generate_html_report(report)
        else:
            raise ValueError(f"不支持的格式: {format}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        _log.info("✅ 报告已生成: {output_path}")

    def verify(
        self,
        threshold: float = 90.0,
        fail_on: str = "type_b",
    ) -> bool:
        """CI 验证模式"""
        report = self.analyze()

        if report.alignment_rate < threshold:
            _log.info("❌ 验证失败: 对齐率 {report.alignment_rate:.1f}% < 阈值 {threshold}%")
            return False

        if fail_on == "any" and report.diff_type_a + report.diff_type_b + report.diff_type_c + report.diff_type_d > 0:
            _log.info("❌ 验证失败: 发现差异")
            return False
        elif fail_on == "type_b" and report.diff_type_b > 0:
            _log.info("❌ 验证失败: 发现 {report.diff_type_b} 个 Type B 差异 (实现缺失)")
            return False
        elif fail_on == "critical" and report.by_severity.get("critical", 0) > 0:
            _log.info("❌ 验证失败: 发现严重问题")
            return False

        _log.info("✅ 验证通过: 对齐率 {report.alignment_rate:.1f}%")
        return True

    def _enhance_report(self, original_report: DiffReport) -> EnhancedDiffReport:
        """增强原始报告"""
        alignment_rate = original_report.matched_count / max(1, original_report.total_declarations) * 100
        issues = []
        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}

        for i, match in enumerate(original_report.matches):
            if match.diff_type:
                category, severity = self._classify_issue(match)
                issue = AlignmentIssue(
                    id=f"ALIGN-{i:04d}",
                    category=category,
                    severity=severity,
                    doc_source=Path(match.doc_source) if match.doc_source else None,
                    doc_line=match.doc_line,
                    code_source=Path(match.code_source) if match.code_source else None,
                    code_line=match.code_line,
                    declaration_name=match.doc_declaration_id,
                    description=match.diff_description,
                    suggestion=self._generate_suggestion(match),
                )
                issues.append(issue)
                sev_key = severity.value
                cat_key = category.value
                by_severity[sev_key] = by_severity.get(sev_key, 0) + 1
                by_category[cat_key] = by_category.get(cat_key, 0) + 1

        recommendations = self._generate_recommendations(issues, alignment_rate)
        return EnhancedDiffReport(
            total_declarations=original_report.total_declarations,
            total_entities=original_report.total_entities,
            matched_count=original_report.matched_count,
            unmatched_doc_count=original_report.unmatched_doc_count,
            alignment_rate=alignment_rate,
            diff_type_a=original_report.diff_type_a,
            diff_type_b=original_report.diff_type_b,
            diff_type_c=original_report.diff_type_c,
            diff_type_d=original_report.diff_type_d,
            issues=issues,
            by_severity=by_severity,
            by_category=by_category,
            recommendations=recommendations,
        )

    def _classify_issue(self, match: MatchResult) -> tuple[AlignmentCategory, AlignmentSeverity]:
        """分类问题"""
        diff_type = match.diff_type.value if match.diff_type else ""

        if diff_type == "type_a":
            return AlignmentCategory.DOC_OUTDATED, AlignmentSeverity.MEDIUM
        elif diff_type == "type_b":
            return AlignmentCategory.IMPLEMENTATION_MISSING, AlignmentSeverity.CRITICAL
        elif diff_type == "type_c":
            return AlignmentCategory.DOC_ERROR, AlignmentSeverity.HIGH
        elif diff_type == "type_d":
            if match.param_mismatch:
                return AlignmentCategory.PARAM_MISMATCH, AlignmentSeverity.HIGH
            elif match.return_type_mismatch:
                return AlignmentCategory.RETURN_TYPE_MISMATCH, AlignmentSeverity.HIGH
            else:
                return AlignmentCategory.API_MISMATCH, AlignmentSeverity.MEDIUM

        return AlignmentCategory.API_MISMATCH, AlignmentSeverity.LOW

    def _generate_suggestion(self, match: MatchResult) -> str:
        """生成修复建议"""
        diff_type = match.diff_type.value if match.diff_type else ""

        if diff_type == "type_a":
            return "更新文档以匹配当前实现"
        elif diff_type == "type_b":
            return "评估是否需要补充实现，或修正文档"
        elif diff_type == "type_c":
            return "重新描述或删除该文档声明"
        elif diff_type == "type_d":
            if match.param_mismatch:
                return "对齐参数列表或更新文档"
            elif match.return_type_mismatch:
                return "对齐返回值类型或更新文档"
            else:
                return "重构代码或更新文档"

        return "需要人工评估"

    def _generate_recommendations(self, issues: list[AlignmentIssue], alignment_rate: float) -> list[dict]:
        """生成修复建议（按优先级排序）"""
        recommendations = []
        sorted_issues = sorted(
            issues,
            key=lambda x: {
                "critical": 0,
                "high": 1,
                "medium": 2,
                "low": 3,
            }.get(x.severity.value, 99),
        )

        for issue in sorted_issues[:20]:
            recommendations.append(
                {
                    "issue_id": issue.id,
                    "declaration_name": issue.declaration_name,
                    "category": issue.category.value,
                    "severity": issue.severity.value,
                    "description": issue.description,
                    "suggestion": issue.suggestion,
                    "doc_source": str(issue.doc_source) if issue.doc_source else None,
                    "doc_line": issue.doc_line,
                    "code_source": str(issue.code_source) if issue.code_source else None,
                    "code_line": issue.code_line,
                }
            )

        if alignment_rate < 90:
            recommendations.insert(
                0,
                {
                    "issue_id": "OVERALL-001",
                    "declaration_name": "整体对齐率",
                    "category": "overall",
                    "severity": "high" if alignment_rate < 80 else "medium",
                    "description": f"对齐率 {alignment_rate:.1f}% 低于目标 90%",
                    "suggestion": "优先修复 Critical 和 High 级别的问题",
                },
            )

        return recommendations

    def _generate_markdown_report(self, report: EnhancedDiffReport) -> str:
        """生成 Markdown 报告"""
        return generate_markdown_report(report)

    def _generate_json_report(self, report: EnhancedDiffReport) -> str:
        """生成 JSON 报告"""
        return generate_json_report(report)

    def _generate_html_report(self, report: EnhancedDiffReport) -> str:
        """生成 HTML 报告（简化版）"""
        return generate_html_report(report)

    def _get_doc_extractor(self) -> DocStatementExtractor:
        """获取文档提取器（延迟加载）"""
        if self._doc_extractor is None:
            from ..doc_extractor import DocStatementExtractor  # type: ignore[import-not-found]

            self._doc_extractor = DocStatementExtractor()
        return self._doc_extractor

    def _get_impl_scanner(self) -> ImplementationScanner:
        """获取实现扫描器（延迟加载）"""
        if self._impl_scanner is None:
            from ..impl_scanner import ImplementationScanner  # type: ignore[import-not-found]

            self._impl_scanner = ImplementationScanner(self.root)
        return self._impl_scanner

    def _get_diff_analyzer(self) -> DiffAnalyzer:
        """获取差异分析器（延迟加载）"""
        if self._diff_analyzer is None:
            from ..diff_analyzer import DiffAnalyzer  # type: ignore[import-not-found]

            self._diff_analyzer = DiffAnalyzer()
        return self._diff_analyzer

__all__ = ["AlignmentEngine"]
