from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Domain: D-Governance
Summary: "XAI router - handles governance/xai/* routes."
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Xai ≡ Module
# 内涵 ≝ {Xai}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Xai)}
# 功能 ⊢ {Init_Xai, Execute_Xai, Validate_Xai}
# =============================================================================


import importlib
import inspect
import logging
from typing import Any

from .base import BaseGovernanceRouter

_log = logging.getLogger(__name__)


class XAIRouter(BaseGovernanceRouter):
    """Router for governance/xai/* endpoints."""

    def __init__(self) -> None:
        super().__init__()
        self._framework = None

    def _get_framework(self) -> Any:
        if self._framework is None:
            mod = importlib.import_module("organs.D_Governance.organs.xai_framework")
            self._framework = mod.XAIFramework()
        return self._framework

    async def _initialize_handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        try:
            framework = self._get_framework()
            initialized = framework.initialize()
            if inspect.isawaitable(initialized):
                initialized = await initialized
            return {"status": "success" if initialized else "error", "initialized": initialized}
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            _log.error(f"[D-Governance URI] xai_initialize_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    def _handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        try:
            framework = self._get_framework()
            params = params or {}

            action = params.get("action")
            if action == "start_decision":
                decision_id = framework.start_decision(params["decision_type"], params.get("input_data", {}))
                return {"status": "success", "decision_id": decision_id}
            if action == "record_step":
                framework.record_step(
                    params["decision_id"],
                    params["component"],
                    params.get("input_data"),
                    params.get("output_data"),
                    params.get("metadata"),
                )
                return {"status": "success"}
            if action == "explain_decision":
                explanation = framework.explain_decision(
                    params["decision_id"],
                    params.get("output_data"),
                    params["confidence"],
                )
                return {"status": "success", "explanation": explanation.to_dict()}

            return {"status": "error", "message": f"Unknown XAI action: {action}"}
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            _log.error(f"[D-Governance URI] xai_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    def _xai_with_veto_handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        """XAI explain with user action buttons (veto/approve/reject)."""
        try:
            framework = self._get_framework()
            params = params or {}

            if params.get("action") == "explain":
                explanation = framework.get_explanation(params.get("decision_id", ""))
                if explanation is None:
                    return {"status": "error", "message": "Decision explanation not found"}
                exp_dict = explanation.to_dict()
                exp_dict["user_actions"] = {
                    "veto": {
                        "available": True,
                        "action": "bos governance user veto",
                        "params": {
                            "action_id": params.get("decision_id"),
                            "reason": "<user reason here>",
                        },
                        "description": "Veto this AI decision immediately",
                        "severity": "critical",
                    },
                    "request_review": {
                        "available": True,
                        "action": "bos governance approval request",
                        "params": {
                            "action": {"type": "ai_decision_review", "decision_id": params.get("decision_id")},
                            "context": {"risk_level": "HIGH"},
                        },
                        "description": "Submit for human review",
                    },
                }
                return {"status": "success", "explanation": exp_dict}

            return {"status": "error", "message": f"Unknown xai explain action: {params.get('action')}"}
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            _log.error(f"[D-Governance URI] xai_with_veto_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    def register_routes(self, register: Any) -> None:
        register("governance", "xai/initialize", self._initialize_handler)
        register("governance", "xai/start_decision", self._handler)
        register("governance", "xai/record_step", self._handler)
        register("governance", "xai/explain_decision", self._handler)
        register("governance", "xai/explain", self._xai_with_veto_handler)
