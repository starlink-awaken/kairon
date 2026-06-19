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
# Models ≡ Module
# 内涵 ≝ {Models}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Models)}
# 功能 ⊢ {Init_Models, Execute_Models, Validate_Models}
# =============================================================================

# ---
# domain: D-Logos
# layer: organ
# status: active
# version: 10.5.0
# owner: '@Architect'
# authority: organs/D-Logos/AGENTS.md
# ---
"""AlignmentEngine enums and dataclasses."""


from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class AlignmentSeverity(Enum):
    """对齐问题严重程度"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlignmentCategory(Enum):
    """对齐问题分类"""

    API_MISMATCH = "api_mismatch"
    PARAM_MISMATCH = "param_mismatch"
    RETURN_TYPE_MISMATCH = "return_type_mismatch"
    DOC_OUTDATED = "doc_outdated"
    IMPLEMENTATION_MISSING = "implementation_missing"
    DOC_ERROR = "doc_error"
    EXTRA_IMPLEMENTATION = "extra_implementation"
    INDEX_ORPHAN = "index_orphan"
    INDEX_GHOST = "index_ghost"
    DOC_STALE = "doc_stale"


@dataclass
class AlignmentIssue:
    """对齐问题"""

    id: str
    category: AlignmentCategory
    severity: AlignmentSeverity
    doc_source: Path | None = None
    doc_line: int | None = None
    code_source: Path | None = None
    code_line: int | None = None
    declaration_name: str = ""
    description: str = ""
    suggestion: str = ""
    param_diffs: list[dict] = field(default_factory=list)
    return_diff: str | None = None


@dataclass
class ScanResult:
    """扫描结果"""

    doc_ast_path: Path
    impl_manifest_path: Path
    doc_count: int
    code_entity_count: int
    scan_time: float


@dataclass
class EnhancedDiffReport:
    """增强的差异报告"""

    total_declarations: int
    total_entities: int
    matched_count: int
    unmatched_doc_count: int
    alignment_rate: float
    diff_type_a: int
    diff_type_b: int
    diff_type_c: int
    diff_type_d: int
    issues: list[AlignmentIssue]
    by_severity: dict[str, int]
    by_category: dict[str, int]
    recommendations: list[dict]


__all__ = [
    "AlignmentCategory",
    "AlignmentIssue",
    "AlignmentSeverity",
    "EnhancedDiffReport",
    "ScanResult",
]
