from __future__ import annotations

"""Quality assurance — test evaluation and test dispatching.

Migrated from agentmesh/packages/toolkit/src/qa/.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class TestType(Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    PERFORMANCE = "performance"
    SECURITY = "security"


@dataclass
class TestResult:
    type: TestType
    passed: bool
    duration: float = 0.0
    coverage: float | None = None
    defects: int = 0
    passed_count: int = 1
    total_count: int = 1


@dataclass
class QualityInput:
    test_results: list[TestResult] = field(default_factory=list)
    regression_passed: int = 0
    regression_total: int = 0


@dataclass
class QualityBreakdown:
    coverage: float = 0.0
    defects: float = 0.0
    pass_rate: float = 0.0
    regression: float = 0.0


class Decision(Enum):
    PASS = "pass"
    CONDITIONAL = "conditional"
    FIX = "fix"
    REJECT = "reject"


@dataclass
class QualityScore:
    total: float = 0.0
    breakdown: QualityBreakdown = field(default_factory=QualityBreakdown)
    decision: Decision = Decision.REJECT
    recommendations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WEIGHTS = {"coverage": 0.25, "defects": 0.30, "pass_rate": 0.30, "regression": 0.15}
THRESHOLDS = {"pass": 90, "conditional": 70, "fix": 50}

TEST_AGENTS: list[dict[str, Any]] = [
    {"id": "e2e-runner", "name": "E2E Runner", "type": "e2e", "languages": ["ts", "js", "python"]},
    {"id": "tdd-guide", "name": "TDD Guide", "type": "unit", "languages": ["ts", "python", "java", "go"]},
    {"id": "python-testing", "name": "Python Testing", "type": "unit", "languages": ["python"]},
    {"id": "qa-tester", "name": "QA Tester", "type": "e2e", "languages": ["ts", "js", "python", "java", "go"]},
]


# ---------------------------------------------------------------------------
# QualityEvaluator
# ---------------------------------------------------------------------------

class QualityEvaluator:
    """Multi-dimensional quality scoring (coverage / defects / pass-rate / regression)."""

    def evaluate(self, input_: QualityInput) -> QualityScore:
        bd = self._calculate_breakdown(input_)

        total = (
            bd.coverage * WEIGHTS["coverage"]
            + bd.defects * WEIGHTS["defects"]
            + bd.pass_rate * WEIGHTS["pass_rate"]
            + bd.regression * WEIGHTS["regression"]
        )
        total = round(total)

        decision = self._get_decision(total)
        recs = self._get_recommendations(bd, decision)

        return QualityScore(total=total, breakdown=bd, decision=decision, recommendations=recs)

    def _calculate_breakdown(self, input_: QualityInput) -> QualityBreakdown:
        # Coverage
        with_cov = [r for r in input_.test_results if r.coverage is not None]
        cov = sum(r.coverage or 0 for r in with_cov) / max(len(with_cov), 1)
        if not with_cov:
            cov = 50.0

        # Defects
        total_defects = sum(r.defects for r in input_.test_results)
        total_tests = sum(r.total_count for r in input_.test_results)
        def_score = max(0.0, 100.0 - (total_defects / max(total_tests, 1)) * 1000) if total_tests > 0 else 50.0

        # Pass rate
        passed = sum((r.passed_count if r.passed else 0) for r in input_.test_results)
        total_p = sum(r.total_count for r in input_.test_results)
        pr = (passed / max(total_p, 1)) * 100

        # Regression
        reg = (input_.regression_passed / max(input_.regression_total, 1)) * 100 if input_.regression_total > 0 else 75.0

        return QualityBreakdown(coverage=cov, defects=def_score, pass_rate=pr, regression=reg)

    @staticmethod
    def _get_decision(total: float) -> Decision:
        if total >= THRESHOLDS["pass"]:
            return Decision.PASS
        if total >= THRESHOLDS["conditional"]:
            return Decision.CONDITIONAL
        if total >= THRESHOLDS["fix"]:
            return Decision.FIX
        return Decision.REJECT

    @staticmethod
    def _get_recommendations(bd: QualityBreakdown, decision: Decision) -> list[str]:
        recs: list[str] = []
        if bd.coverage < 80:
            recs.append("建议增加测试覆盖率至80%以上")
        if bd.defects < 70:
            recs.append("存在较多缺陷，建议优先修复高优先级问题")
        if bd.pass_rate < 90:
            recs.append("测试通过率偏低，建议修复失败的测试用例")
        if bd.regression < 80 and bd.regression > 0:
            recs.append("回归测试通过率偏低，注意防止引入新问题")
        recs.append(
            {
                Decision.PASS: "代码质量良好，可以合并",
                Decision.CONDITIONAL: "代码基本可用，但需关注建议项",
                Decision.FIX: "建议修复关键问题后再合并",
                Decision.REJECT: "代码质量不达标，建议重新设计",
            }[decision]
        )
        return recs


# ---------------------------------------------------------------------------
# TestDispatcher
# ---------------------------------------------------------------------------

ESTIMATES: dict[TestType, str] = {
    TestType.UNIT: "1-5分钟",
    TestType.INTEGRATION: "5-15分钟",
    TestType.E2E: "10-30分钟",
    TestType.PERFORMANCE: "15-60分钟",
    TestType.SECURITY: "30-120分钟",
}


class TestDispatcher:
    """Dispatch testing tasks to appropriate agents."""

    def dispatch(self, test_type: TestType, language: str | None = None) -> list[dict[str, Any]]:
        candidates = [a for a in TEST_AGENTS if a["type"] == test_type.value]
        if language:
            candidates = [a for a in candidates if language in a["languages"]]
        return [
            {
                "agent": a,
                "test_type": test_type.value,
                "language": language,
                "estimated_time": ESTIMATES.get(test_type, "5-15分钟"),
            }
            for a in candidates
        ]


def create_quality_evaluator() -> QualityEvaluator:
    return QualityEvaluator()


def create_test_dispatcher() -> TestDispatcher:
    return TestDispatcher()
