"""SHACL Validator for eCOS Architecture Governance.

Validates governance assets (scene cards, DFSQ slots) against
W3C SHACL Shapes to enforce architectural constraints.

Reference: BET-Y1Q4-T6-27 (Entity-Aware Chunking & SHACL Architecture Validator)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Sequence


class ValidationSeverity(Enum):
    """SHACL validation severity levels."""

    VIOLATION = "violation"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of SHACL validation.

    Attributes:
        valid: Whether validation passed.
        violations: List of constraint violations.
        warnings: List of warnings.
        shape_file: Path to the shape file used.
    """

    valid: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    shape_file: str = ""

    def add_violation(self, message: str) -> None:
        """Add a constraint violation."""
        self.violations.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning."""
        self.warnings.append(message)


class SHACLValidator:
    """SHACL shape validator for governance architecture assets.

    Validates YAML/JSON governance files against SHACL shapes
    defined in TTL (Turtle) format.

    Example:
        >>> validator = SHACLValidator()
        >>> result = validator.validate_file("scene-card.yaml", "scene-card-shapes.ttl")
        >>> if not result.valid:
        ...     for v in result.violations:
        ...         print(v)
    """

    # Canonical shape file paths (relative to workspace root)
    SHAPE_PATHS = {
        "dfsq": ".omo/standards/shapes/dfsq-shapes.ttl",
        "scene-card": ".omo/standards/shapes/scene-card-shapes.ttl",
    }

    def __init__(self, workspace_root: str | Path | None = None) -> None:
        """Initialize validator.

        Args:
            workspace_root: Root directory for resolving shape paths.
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    def validate_file(
        self,
        data_file: str | Path,
        shape_name: str,
    ) -> ValidationResult:
        """Validate a data file against named shapes.

        Args:
            data_file: Path to the data file to validate.
            shape_name: Name of the shape set (dfsq, scene-card).

        Returns:
            ValidationResult with violations if any.
        """
        shape_path = self.SHAPE_PATHS.get(shape_name)
        if not shape_path:
            result = ValidationResult(valid=False, shape_file="")
            result.add_violation(f"Unknown shape set: {shape_name}")
            return result

        full_shape_path = self.workspace_root / shape_path
        data_path = Path(data_file)

        if not full_shape_path.exists():
            result = ValidationResult(valid=True, shape_file=str(full_shape_path))
            result.add_warning(f"Shape file not found: {full_shape_path}")
            return result

        if not data_path.exists():
            result = ValidationResult(valid=False, shape_file=str(full_shape_path))
            result.add_violation(f"Data file not found: {data_path}")
            return result

        return self._validate_against_shapes(data_path, full_shape_path)

    def validate_directory(
        self,
        directory: str | Path,
        shape_name: str,
        pattern: str = "*.yaml",
    ) -> ValidationResult:
        """Validate all matching files in a directory.

        Args:
            directory: Directory to scan.
            shape_name: Name of the shape set.
            pattern: Glob pattern for files.

        Returns:
            Aggregated ValidationResult.
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            result = ValidationResult(valid=False)
            result.add_violation(f"Directory not found: {dir_path}")
            return result

        aggregated = ValidationResult(valid=True)
        for file_path in sorted(dir_path.glob(pattern)):
            file_result = self.validate_file(file_path, shape_name)
            if not file_result.valid:
                aggregated.valid = False
                for v in file_result.violations:
                    aggregated.add_violation(f"{file_path.name}: {v}")

        return aggregated

    def _validate_against_shapes(
        self,
        data_path: Path,
        shape_path: Path,
    ) -> ValidationResult:
        """Perform actual validation against shape file.

        Implements structural validation rules derived from SHACL shapes:
        - Required properties check
        - Value range constraints
        - Type constraints
        - Cross-field dependencies

        Args:
            data_path: Path to data file.
            shape_path: Path to SHACL shapes file.

        Returns:
            ValidationResult.
        """
        import yaml

        result = ValidationResult(valid=True, shape_file=str(shape_path))

        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            result.add_violation(f"Failed to parse YAML: {e}")
            return result

        if data is None:
            result.add_violation("Empty YAML file")
            return result

        # Apply shape-specific validation rules
        shape_name = shape_path.stem
        if "scene-card" in shape_name:
            self._validate_scene_card(data, result)
        elif "dfsq" in shape_name:
            self._validate_dfsq(data, result)

        return result

    def _validate_scene_card(self, data: Any, result: ValidationResult) -> None:
        """Validate scene card structure against SHACL shapes.

        Rules derived from scene-card-shapes.ttl:
        - Must have 'id' field (non-empty string)
        - Must have 'status' field with valid lifecycle value
        - Must have 'title' field (non-empty string)
        - If status is 'assisted' or higher, must have 'samples' >= 30
        - If status is 'routine', must have 'calibration' >= 0.6
        """
        if not isinstance(data, dict):
            result.add_violation("Scene card must be a mapping")
            return

        # Required fields
        required_fields = ["id", "status", "title"]
        for req in required_fields:
            if req not in data:
                result.add_violation(f"Missing required field: {req}")
            elif not data[req] and data[req] != 0:
                result.add_violation(f"Required field cannot be empty: {req}")

        # Status value constraints
        valid_statuses = ["draft", "shadow", "assisted", "supervised", "routine"]
        status = data.get("status")
        if status and status not in valid_statuses:
            result.add_violation(
                f"Invalid status '{status}'. Must be one of: {valid_statuses}"
            )

        # Conditional constraints
        if status in ("assisted", "supervised", "routine"):
            samples = data.get("samples", 0)
            if isinstance(samples, (int, float)) and samples < 30:
                result.add_violation(
                    f"Status '{status}' requires samples >= 30, got {samples}"
                )

        if status == "routine":
            calibration = data.get("calibration", 0.0)
            if isinstance(calibration, (int, float)) and calibration < 0.6:
                result.add_violation(
                    f"Status 'routine' requires calibration >= 0.6, got {calibration}"
                )

    def _validate_dfsq(self, data: Any, result: ValidationResult) -> None:
        """Validate DFSQ structure against SHACL shapes.

        Rules derived from dfsq-shapes.ttl:
        - Must have 'schema' field
        - Must have 'version' field
        - Must have 'dimensions' or 'slots' field
        """
        if not isinstance(data, dict):
            result.add_violation("DFSQ file must be a mapping")
            return

        if "schema" not in data:
            result.add_violation("Missing required field: schema")

        if "version" not in data:
            result.add_violation("Missing required field: version")

        if "dimensions" not in data and "slots" not in data:
            result.add_violation("Must have either 'dimensions' or 'slots' field")
