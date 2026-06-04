from __future__ import annotations

"""
Quality package — quality gates and validation rules for extracted knowledge.
"""

from .gate import QualityGate, ValidationResult

__all__ = [
    "QualityGate",
    "ValidationResult",
]
