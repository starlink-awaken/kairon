from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Domain: D-Governance
Summary: "Veto router - handles governance/user/veto/* routes."
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Veto ≡ Module
# 内涵 ≝ {Veto}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Veto)}
# 功能 ⊢ {Init_Veto, Execute_Veto, Validate_Veto}
# =============================================================================


import logging
from typing import Any

from .base import BaseGovernanceRouter

_log = logging.getLogger(__name__)


class VetoRouter(BaseGovernanceRouter):
    """Router for governance/user/veto/* endpoints."""

    async def _handler(self, uri: str, params: dict | None = None) -> dict[str, Any]:
        try:
            from kairon_lib.governance.user_veto import UserVeto  # type: ignore[import-not-found]

            veto = UserVeto()
            params = params or {}

            action = params.get("action")
            if action == "veto":
                entry = veto.veto(
                    action_id=params["action_id"],
                    reason=params.get("reason", "User vetoed"),
                    vetoer=params.get("vetoer", "@Prime"),
                    metadata=params.get("metadata"),
                )
                return {"status": "success", "veto": entry.to_dict()}
            elif action == "pending":
                entries = veto.get_pending_veto()
                return {"status": "success", "pending": [e.to_dict() for e in entries]}
            elif action == "history":
                entries = veto.get_veto_history(
                    action_id=params.get("action_id"),
                    vetoer=params.get("vetoer"),
                    limit=params.get("limit", 100),
                )
                return {"status": "success", "history": [e.to_dict() for e in entries]}
            elif action == "register":
                action_obj = veto.register_vetoable_action(
                    action_id=params["action_id"],
                    action_type=params.get("action_type", "generic"),
                    description=params.get("description", ""),
                    risk_level=params.get("risk_level", "medium"),
                )
                return {
                    "status": "success",
                    "action": {
                        "action_id": action_obj.action_id,
                        "action_type": action_obj.action_type,
                        "risk_level": action_obj.risk_level,
                        "can_be_vetoed": action_obj.can_be_vetoed,
                    },
                }
            elif action == "stats":
                stats = veto.get_veto_stats()
                return {"status": "success", "stats": stats}
            elif action == "is_vetoed":
                is_vetoed = veto.is_action_vetoed(params["action_id"])
                return {"status": "success", "is_vetoed": is_vetoed}
            return {"status": "error", "message": f"Unknown veto action: {action}"}
        except Exception as exc:
            _log.error(f"[D-Governance URI] user_veto_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    def register_routes(self, register: Any) -> None:
        register("governance", "user/veto", self._handler)
        register("governance", "user/veto/pending", self._handler)
        register("governance", "user/veto/history", self._handler)
        register("governance", "user/veto/register", self._handler)
        register("governance", "user/veto/stats", self._handler)
        register("governance", "user/veto/is_vetoed", self._handler)
