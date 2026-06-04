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
# Doc Type Validator ≡ Validator
# 内涵 ≝ {Doc, Type, Validator}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, DocTypeValidator)}
# 功能 ⊢ {Doc_Type, Type_Validator, Validator_Init}
# =============================================================================


import re
from pathlib import Path

from engine.meta_validate_types import (  # type: ignore[import-not-found]
    DocType,
    ValidationIssue,
    ValidationIssueSeverity,
)


class DocTypeValidator:
    """Validates doc type / filename / frontmatter contracts from the 4-type taxonomy.

    Implements the governance rules from docs/50-reference/standards/01-naming-convention.md.
    """

    REQUIRED_FRONTMATTER: list[str] = ["Type", "Status", "Layer", "Summary", "Updated"]
    VALID_STATUSES: set[str] = {"ACTIVE", "DRAFT", "DEPRECATED", "ARCHIVED"}
    VALID_LAYERS: set[str] = {"L1", "L2", "L3", "L4", "L5"}

    # Pattern: ^\\d{2}-[a-z0-9-]+\\.md$ — State and Reference docs
    _PATTERN_NUMBERED = re.compile(r"^\d{2}-[a-z0-9-]+\.md$")
    # Pattern: ^\\d{8}-[a-z0-9-]+\\.md$ — Process (dated) docs
    _PATTERN_DATED = re.compile(r"^\d{8}-[a-z0-9-]+\.md$")
    # Pattern: RFC-NNN-Title — RFC docs
    _PATTERN_RFC = re.compile(r"^RFC-\d{3}-[A-Za-z0-9-]+\.md$")

    # Section directory → expected doc type
    SECTION_TYPE_MAP: dict[str, DocType] = {
        "10-strategy": DocType.STATE,
        "20-architecture": DocType.STATE,
        "60-api": DocType.STATE,
        "00-overview": DocType.REFERENCE,
        "30-user-guides": DocType.REFERENCE,
        "40-operations": DocType.REFERENCE,
        "50-reference": DocType.REFERENCE,
        "25-implementation": DocType.PROCESS,
        "90-internal": DocType.INTERNAL,
    }

    def validate_frontmatter(self, doc_path: Path, content: str) -> list[ValidationIssue]:
        """Check required frontmatter fields and valid values.

        A YAML frontmatter block delimited by ``---`` is expected.  Returns a
        list of :class:`ValidationIssue` — one per problem found.  Missing
        required fields are CRITICAL; invalid Status/Layer values are MEDIUM.
        """
        issues: list[ValidationIssue] = []
        frontmatter = self._extract_frontmatter(content)

        if frontmatter is None:
            for field_name in self.REQUIRED_FRONTMATTER:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.CRITICAL,
                        message=f"Missing required frontmatter field '{field_name}' (no frontmatter block found)",
                        doc_path=doc_path,
                        field_name=field_name,
                    )
                )
            return issues

        for field_name in self.REQUIRED_FRONTMATTER:
            if field_name not in frontmatter or not str(frontmatter[field_name]).strip():
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.CRITICAL,
                        message=f"Missing required frontmatter field '{field_name}'",
                        doc_path=doc_path,
                        field_name=field_name,
                    )
                )

        # Validate Status value (if present)
        status_val = frontmatter.get("Status", "")
        if status_val and str(status_val).upper() not in self.VALID_STATUSES:
            issues.append(
                ValidationIssue(
                    severity=ValidationIssueSeverity.MEDIUM,
                    message=(f"Invalid Status value '{status_val}'; expected one of {sorted(self.VALID_STATUSES)}"),
                    doc_path=doc_path,
                    field_name="Status",
                )
            )

        # Validate Layer value (if present)
        layer_val = frontmatter.get("Layer", "")
        if layer_val and str(layer_val) not in self.VALID_LAYERS:
            issues.append(
                ValidationIssue(
                    severity=ValidationIssueSeverity.MEDIUM,
                    message=(f"Invalid Layer value '{layer_val}'; expected one of {sorted(self.VALID_LAYERS)}"),
                    doc_path=doc_path,
                    field_name="Layer",
                )
            )

        return issues

    def validate_filename(self, doc_path: Path) -> list[ValidationIssue]:
        """Check filename follows the naming convention for its doc type.

        State/Reference: ``^\\d{2}-[a-z0-9-]+\\.md$``
        Process:         ``^\\d{8}-[a-z0-9-]+\\.md$``
        RFC:             ``^RFC-\\d{3}-[A-Za-z0-9-]+\\.md$``
        """
        issues: list[ValidationIssue] = []
        name = doc_path.name

        # Skip README.md — it is exempt from naming rules
        if name == "README.md":
            return issues

        matched = self._PATTERN_NUMBERED.match(name) or self._PATTERN_DATED.match(name) or self._PATTERN_RFC.match(name)
        if not matched:
            issues.append(
                ValidationIssue(
                    severity=ValidationIssueSeverity.MEDIUM,
                    message=(
                        f"Filename '{name}' does not match any valid pattern "
                        "(numbered: NN-kebab.md, dated: YYYYMMDD-kebab.md, or RFC-NNN-Title.md)"
                    ),
                    doc_path=doc_path,
                )
            )
        return issues

    def validate_placement(self, doc_path: Path, declared_type: str) -> list[ValidationIssue]:
        """Check doc type matches the expected type for its section directory."""
        issues: list[ValidationIssue] = []

        # Determine the top-level section from the path
        section = self._resolve_section(doc_path)
        if section is None:
            return issues  # Cannot determine section — skip

        expected_type = self.SECTION_TYPE_MAP.get(section)
        if expected_type is None:
            return issues  # Unknown section — skip

        try:
            actual_type = DocType(declared_type)
        except ValueError:
            issues.append(
                ValidationIssue(
                    severity=ValidationIssueSeverity.MEDIUM,
                    message=f"Unknown Type value '{declared_type}' in frontmatter",
                    doc_path=doc_path,
                    field_name="Type",
                )
            )
            return issues

        if actual_type != expected_type:
            issues.append(
                ValidationIssue(
                    severity=ValidationIssueSeverity.MEDIUM,
                    message=(
                        f"Type/section mismatch: doc declares Type='{declared_type}' "
                        f"but section '{section}' expects Type='{expected_type.value}'"
                    ),
                    doc_path=doc_path,
                    field_name="Type",
                )
            )
        return issues

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_frontmatter(self, content: str) -> dict | None:
        """Parse the YAML-like frontmatter block.  Returns None if absent."""
        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            return None
        end_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_idx = i
                break
        if end_idx is None:
            return None
        fm: dict = {}
        for line in lines[1:end_idx]:
            if ":" in line:
                key, _, val = line.partition(":")
                fm[key.strip()] = val.strip().strip("'\"")
        return fm

    def _resolve_section(self, doc_path: Path) -> str | None:
        """Return the numbered section directory name (e.g. '20-architecture')."""
        for part in doc_path.parts:
            if re.match(r"^\d{2}-", part):
                return part
        return None


# ============================================================
# End Mechanism 1
# ============================================================
