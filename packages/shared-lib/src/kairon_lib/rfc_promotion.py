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
# Rfc Promotion Orchestrator ≡ Orchestrator
# 内涵 ≝ {Rfc, Promotion, Orchestrator}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, RfcPromotionOrchestrator)}
# 功能 ⊢ {Rfc_Promotion, Promotion_Orchestrator, Orchestrator_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import threading
from datetime import UTC, datetime
from typing import Any


class RFCPromotionOrchestrator:
    """Bridges RFC lifecycle to PolicyRegistry.

    Promotes approved RFCs into enforceable policies and records every
    governance action via DecisionReceiptManager.
    """

    def __init__(
        self,
        policy_registry: Any,  # PolicyRegistry
        receipt_manager: Any,  # DecisionReceiptManager
        metadata_path: str = "organs/D_Governance/organs/rfc_promotion_orchestrator.py",
    ) -> None:
        self._registry = policy_registry
        self._receipt_manager = receipt_manager
        self._promotions: list[dict] = []
        self._lock = threading.RLock()
        self.status = "ACTIVE"
        _log.info("RFCPromotionOrchestrator initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def promote_rfc(
        self,
        rfc_id: str,
        rfc_title: str,
        rfc_rules: list[dict],
        enforced_by: str,
    ) -> Any:
        """Promote an RFC into an enforceable policy."""
        policy: dict[str, Any] = {
            "policy_id": f"rfc-{rfc_id}",
            "name": rfc_title,
            "description": f"Policy promoted from RFC {rfc_id}",
            "rules": rfc_rules,
        }
        self._registry.register_policy(policy)

        receipt = self._receipt_manager.create_receipt(
            request_id=rfc_id,
            decision="approved",
            rationale=f"RFC {rfc_id} promoted to policy",
            decided_by=enforced_by,
            change_summary=f"Promoted RFC {rfc_id}: {rfc_title}",
        )

        with self._lock:
            self._promotions.append(
                {
                    "rfc_id": rfc_id,
                    "policy_id": policy["policy_id"],
                    "receipt_id": receipt.receipt_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

        _log.info("RFC %s promoted to policy %s", rfc_id, policy["policy_id"])
        return policy

    def revoke_promotion(
        self,
        policy_id: str,
        reason: str,
        revoked_by: str,
    ) -> bool:
        """Retire a previously promoted policy."""
        retired = self._registry.retire_policy(policy_id)
        if not retired:
            return False

        self._receipt_manager.create_receipt(
            request_id=policy_id,
            decision="rejected",
            rationale=reason,
            decided_by=revoked_by,
            change_summary=f"Revoked policy {policy_id}",
        )

        _log.info("Policy %s revoked by %s: %s", policy_id, revoked_by, reason)
        return True

    def get_promotions(self) -> list[dict]:
        """Return all promotion records."""
        with self._lock:
            return list(self._promotions)
