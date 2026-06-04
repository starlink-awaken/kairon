"""
Model validation utilities for supply-chain integrity checking.

Extracted from SharedBrain D_Harness organ (validation/model_validator.py).
All SharedBrain organ dependencies removed; standalone.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


# =============================================================================
# Enumerations
# =============================================================================


class ValidationStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"
    ERROR = "error"
    NOT_FOUND = "not_found"


# =============================================================================
# Result dataclass
# =============================================================================


@dataclass
class ValidationResult:
    """Result of a model validation operation.

    Attributes:
        is_valid: Convenience boolean derived from *status*.
        score: Confidence score (0.0 -- 1.0).
        issues: Human-readable issue descriptions.
        metadata: Arbitrary extra data attached by the validator.
        status: Structured status enum.
        model_id: Identifier of the validated model.
        computed_hash: SHA-256 of the model artefact (empty if not computed).
        expected_hash: Hash supplied by caller for comparison.
        signature_valid: Whether signature verification passed.
        message: Short description of the validation outcome.
    """

    is_valid: bool = True
    score: float = 1.0
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    status: ValidationStatus = ValidationStatus.VALID
    model_id: str = ""
    computed_hash: str = ""
    expected_hash: str | None = None
    signature_valid: bool = False
    message: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "issues": self.issues,
            "status": self.status.value,
            "model_id": self.model_id,
            "computed_hash": self.computed_hash,
            "signature_valid": self.signature_valid,
            "message": self.message,
            "metadata": self.metadata,
        }


# =============================================================================
# ModelValidator
# =============================================================================


class ModelValidator:
    """Validates model artefacts by computing SHA-256 hashes and optionally
    verifying against an expected hash.

    In *strict* mode every validation attempt is treated as UNKNOWN (not VALID)
    when the file is not found or verification cannot complete.
    In *disabled* mode all checks are skipped and the result is always VALID.

    Args:
        mode: Validation mode (``"strict"`` or ``"disabled"``).
        cache_dir: Optional directory for caching validation artefacts.
        signature_verification: Alternative mode name (compat with
            HarnessController instantiation).
        trusted_registry_url: Optional registry URL for future use.
    """

    def __init__(
        self,
        mode: str = "strict",
        cache_dir: str | None = None,
        signature_verification: str | None = None,
        trusted_registry_url: str | None = None,
        **_: Any,
    ) -> None:
        self.mode = signature_verification or mode
        self.cache_dir = cache_dir
        self.trusted_registry_url = trusted_registry_url

        if cache_dir:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------

    def validate(
        self,
        model_path: str,
        model_id: str,
        expected_hash: str | None = None,
        **_: Any,
    ) -> ValidationResult:
        """Validate a model artefact.

        Returns VALID when the file exists and (optionally) its hash matches
        *expected_hash*.  Returns NOT_FOUND or UNKNOWN otherwise.
        """
        if self.mode == "disabled":
            return ValidationResult(
                is_valid=True,
                score=1.0,
                status=ValidationStatus.VALID,
                model_id=model_id,
                signature_valid=True,
                message="validation disabled",
            )

        path = Path(model_path)
        if not path.exists():
            return ValidationResult(
                is_valid=False,
                score=0.0,
                issues=[f"File not found: {model_path}"],
                status=ValidationStatus.NOT_FOUND,
                model_id=model_id,
                message="model file not found",
            )

        computed_hash = self._hash_file(path)

        if expected_hash and computed_hash != expected_hash:
            return ValidationResult(
                is_valid=False,
                score=0.0,
                issues=["Hash mismatch"],
                status=ValidationStatus.INVALID,
                model_id=model_id,
                computed_hash=computed_hash,
                expected_hash=expected_hash,
                message="hash mismatch",
            )

        return ValidationResult(
            is_valid=True,
            score=1.0,
            status=ValidationStatus.VALID,
            model_id=model_id,
            computed_hash=computed_hash,
            expected_hash=expected_hash,
            signature_valid=(self.mode != "strict"),
            message="ok",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_file(path: Path, chunk_size: int = 65536) -> str:
        """Compute the SHA-256 hex digest of *path*."""
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()


__all__ = [
    "ValidationStatus",
    "ValidationResult",
    "ModelValidator",
]
