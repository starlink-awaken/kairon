from __future__ import annotations

import logging

_log = logging.getLogger(__name__)
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
# Decision Receipt ≡ Module
# 内涵 ≝ {Decision, Receipt}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, DecisionReceipt)}
# 功能 ⊢ {Decision_Receipt, Init_Decision, Validate_Receipt}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import hashlib
import hmac
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class DecisionReceipt:
    """Tamper-proof receipt for a governance decision."""

    receipt_id: str
    request_id: str
    decision: str
    rationale: str
    decided_by: str
    decided_at: str
    change_summary: str
    compliance_ref: str = ""
    fingerprint: str = ""


_VALID_DECISIONS: frozenset[str] = frozenset({
    "approved",
    "rejected",
    "deferred",
    "escalated",
    "needs_revision",
    "conditional_approved",
    "abstained",
})


class DecisionReceiptManager:
    """Manages creation, storage, and verification of decision receipts.

    Each receipt carries an HMAC-SHA256 fingerprint so downstream consumers
    can verify the record has not been tampered with.
    """

    def __init__(
        self,
        secret_key: str = "bos-governance-demo-key",
        metadata_path: str = "organs/D_Governance/organs/decision_receipt.py",
    ) -> None:
        self._secret_key = secret_key
        self._receipts: dict[str, DecisionReceipt] = {}
        self._lock = threading.RLock()
        self.status = "ACTIVE"
        _log.info("DecisionReceiptManager initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_receipt(
        self,
        request_id: str,
        decision: str,
        rationale: str,
        decided_by: str,
        change_summary: str,
        compliance_ref: str = "",
    ) -> DecisionReceipt:
        if decision not in _VALID_DECISIONS:  # noqa: F821
            raise ValueError(f"Invalid decision '{decision}'. Must be one of: {', '.join(sorted(_VALID_DECISIONS))}")  # noqa: F821

        receipt = DecisionReceipt(
            receipt_id=str(uuid.uuid4()),
            request_id=request_id,
            decision=decision,
            rationale=rationale,
            decided_by=decided_by,
            decided_at=datetime.now(UTC).isoformat(),
            change_summary=change_summary,
            compliance_ref=compliance_ref,
        )
        receipt.fingerprint = self._compute_fingerprint(receipt)

        with self._lock:
            self._receipts[receipt.receipt_id] = receipt

        _log.info(
            "Receipt %s created for request %s (decision=%s)",
            receipt.receipt_id,
            request_id,
            decision,
        )
        return receipt

    def verify_receipt(self, receipt: DecisionReceipt) -> bool:
        expected = self._compute_fingerprint(receipt)
        return hmac.compare_digest(expected, receipt.fingerprint)

    def get_receipt(self, receipt_id: str) -> DecisionReceipt | None:
        with self._lock:
            return self._receipts.get(receipt_id)

    def list_receipts(self, filter_by: dict[str, Any] | None = None) -> list[DecisionReceipt]:
        with self._lock:
            receipts = list(self._receipts.values())

        if not filter_by:
            return receipts

        result: list[DecisionReceipt] = []
        for r in receipts:
            if all(getattr(r, k, None) == v for k, v in filter_by.items()):
                result.append(r)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_fingerprint(self, receipt: DecisionReceipt) -> str:
        payload = "|".join(
            [
                receipt.receipt_id,
                receipt.request_id,
                receipt.decision,
                receipt.rationale,
                receipt.decided_by,
                receipt.decided_at,
                receipt.change_summary,
            ]
        )
        return hmac.new(
            self._secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
