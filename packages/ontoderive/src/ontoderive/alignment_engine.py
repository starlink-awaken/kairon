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
# Alignment Engine ≡ Engine
# 内涵 ≝ {Alignment, Engine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, AlignmentEngine)}
# 功能 ⊢ {Alignment_Engine, Init_Alignment, Validate_Engine}
# =============================================================================

# ---
# domain: D-Logos
# layer: organ
# status: active
# version: 10.5.0
# owner: '@Architect'
# authority: organs/D-Logos/AGENTS.md
# ---
"""Compatibility facade for the AlignmentEngine public interface.

Re-exports the public API from the extracted alignment engine modules.
AlignmentEngine core class is not yet extracted (future wave).
"""

from ontoderive.alignment_governance import DocFreshnessScanner, IndexAuditor
from ontoderive.alignment_models import (
    AlignmentCategory,
    AlignmentIssue,
    AlignmentSeverity,
    EnhancedDiffReport,
    ScanResult,
)

__all__ = [
    "AlignmentCategory",
    "AlignmentIssue",
    "AlignmentSeverity",
    "EnhancedDiffReport",
    "ScanResult",
    "IndexAuditor",
    "DocFreshnessScanner",
]
