"""Kairon ontology module.

Provides SHACL validation for governance architecture assets.
"""

from kairon.ontology.shacl_validator import (
    SHACLValidator,
    ValidationResult,
    ValidationSeverity,
)

__all__ = ["SHACLValidator", "ValidationResult", "ValidationSeverity"]
