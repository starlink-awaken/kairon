from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Domain: D-Governance
Summary: "Hive router - handles hive/* routes (members, share, delegate, federate, insights)."
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Hive ≡ Module
# 内涵 ≝ {Hive}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Hive)}
# 功能 ⊢ {Init_Hive, Execute_Hive, Validate_Hive}
# =============================================================================


import importlib
import logging
import uuid
from typing import Any

from .base import BaseGovernanceRouter  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)


class HiveRouter(BaseGovernanceRouter):
    """Router for hive/* endpoints (members, share, delegate, federate, insights)."""

    def __init__(self) -> None:
        super().__init__()
        self._hive_network = None
        self._cross_twin_memory = None
        self._delegation_manager = None
        self._deliberation = None
        self._federated_learning = None
        self._emergent_intelligence = None

    def _get_hive_network(self) -> Any:
        if self._hive_network is None:
            mod = importlib.import_module("organs.D_Governance.organs.governance.federation.family_hive")
            self._hive_network = mod.FamilyHiveNetwork()
        return self._hive_network

    def _get_cross_twin_memory(self) -> Any:
        if self._cross_twin_memory is None:
            mod = importlib.import_module("organs.D_Governance.organs.governance.federation.family_hive")
            self._cross_twin_memory = mod.CrossTwinMemory()
        return self._cross_twin_memory

    def _get_delegation_manager(self) -> Any:
        if self._delegation_manager is None:
            mod = importlib.import_module("organs.D_Governance.organs.governance.federation.family_hive")
            self._delegation_manager = mod.DelegationChainManager(_hive_network=self._get_hive_network())
        return self._delegation_manager

    def _get_deliberation(self) -> Any:
        if self._deliberation is None:
            mod = importlib.import_module("organs.D_Governance.organs.governance.collaboration.collective_mind")
            self._deliberation = mod.MultiTwinDeliberation()
        return self._deliberation

    def _get_federated_learning(self) -> Any:
        if self._federated_learning is None:
            mod = importlib.import_module("organs.D_Governance.organs.governance.collaboration.collective_mind")
            self._federated_learning = mod.FederatedLearning()
        return self._federated_learning

    def _get_emergent_intelligence(self) -> Any:
        if self._emergent_intelligence is None:
            mod = importlib.import_module("organs.D_Governance.organs.governance.collaboration.collective_mind")
            self._emergent_intelligence = mod.EmergentIntelligence()
        return self._emergent_intelligence

    def _serialize_hive_member(self, member: Any) -> dict[str, object] | None:
        if member is None:
            return None
        trust_level = getattr(member, "trust_level", None)
        if hasattr(trust_level, "value"):
            trust_level = trust_level.value
        registered_at = getattr(member, "registered_at", None)
        if hasattr(registered_at, "isoformat"):
            registered_at = registered_at.isoformat()
        return {
            "node_id": getattr(member, "node_id", ""),
            "twin_id": getattr(member, "twin_id", ""),
            "member_name": getattr(member, "member_name", ""),
            "role": getattr(member, "role", ""),
            "permissions": list(getattr(member, "permissions", [])),
            "trust_level": trust_level,
            "registered_at": registered_at,
        }

    def _serialize_delegation_chain(self, chain: Any) -> dict[str, object]:
        return {
            "chain_id": getattr(chain, "chain_id", ""),
            "delegator": getattr(chain, "delegator", ""),
            "delegate": getattr(chain, "delegate", ""),
            "scope": getattr(chain, "scope", ""),
            "permissions": list(getattr(chain, "permissions", [])),
            "expires_at": getattr(chain, "expires_at", None),
            "chain_depth": getattr(chain, "chain_depth", 1),
            "created_at": getattr(chain, "created_at", None),
        }

    def _serialize_deliberation_session(self, session: Any) -> dict[str, object] | None:
        if session is None:
            return None
        status = getattr(session, "status", None)
        if hasattr(status, "value"):
            status = status.value
        consensus_mode = getattr(session, "consensus_mode", None)
        if hasattr(consensus_mode, "value"):
            consensus_mode = consensus_mode.value
        proposals = [self._serialize_proposal(p) for p in getattr(session, "proposals", [])]
        votes = [self._serialize_vote(v) for v in getattr(session, "votes", [])]
        return {
            "session_id": getattr(session, "session_id", ""),
            "topic": getattr(session, "topic", ""),
            "participants": list(getattr(session, "participants", [])),
            "participant_count": len(getattr(session, "participants", [])),
            "proposals": proposals,
            "proposal_count": len(proposals),
            "votes": votes,
            "vote_count": len(votes),
            "status": status,
            "consensus_mode": consensus_mode,
            "created_at": getattr(session, "created_at", None),
        }

    def _serialize_proposal(self, proposal: Any) -> dict[str, object]:
        return {
            "proposal_id": getattr(proposal, "proposal_id", ""),
            "twin_id": getattr(proposal, "twin_id", ""),
            "content": getattr(proposal, "content", ""),
            "submitted_at": getattr(proposal, "submitted_at", None),
        }

    def _serialize_vote(self, vote: Any) -> dict[str, object]:
        vote_type = getattr(vote, "vote_type", None)
        if hasattr(vote_type, "value"):
            vote_type = vote_type.value
        return {
            "twin_id": getattr(vote, "twin_id", ""),
            "proposal_id": getattr(vote, "proposal_id", ""),
            "vote_type": vote_type,
            "weight": getattr(vote, "weight", 1.0),
            "voted_at": getattr(vote, "voted_at", None),
        }

    def _serialize_deliberation_outcome(self, outcome: Any) -> dict[str, object] | None:
        if outcome is None:
            return None
        return {
            "outcome_id": getattr(outcome, "outcome_id", ""),
            "session_id": getattr(outcome, "session_id", ""),
            "decision": getattr(outcome, "decision", ""),
            "consensus_level": getattr(outcome, "consensus_level", 0.0),
            "minority_position": getattr(outcome, "minority_position", ""),
        }

    def _serialize_federated_round(self, round_state: Any) -> dict[str, object] | None:
        if round_state is None:
            return None
        return {
            "round_id": getattr(round_state, "round_id", ""),
            "participants": list(getattr(round_state, "participants", [])),
            "gradients_received": len(getattr(round_state, "gradients", {})),
            "aggregated_at": getattr(round_state, "aggregated_at", None),
            "loss": getattr(round_state, "loss", 0.0),
        }

    def _serialize_emergent_insight(self, insight: Any) -> dict[str, object]:
        return {
            "insight_id": getattr(insight, "insight_id", ""),
            "description": getattr(insight, "description", ""),
            "supporting_evidence": list(getattr(insight, "supporting_evidence", [])),
            "confidence": getattr(insight, "confidence", 0.0),
            "emerged_at": getattr(insight, "emerged_at", None),
        }

    def _cluster_approval_required_response(self, params: dict[str, object]) -> dict[str, object] | None:
        governance_scope = params.get("governance_scope", "family")
        if governance_scope != "cluster":
            return None
        consent_acknowledged = params.get("consent_acknowledged", False)
        approval_receipt = params.get("approval_receipt")
        has_receipt = isinstance(approval_receipt, str) and bool(approval_receipt.strip())
        if consent_acknowledged is True and has_receipt:
            return None
        action = str(params.get("action", "") or "").strip()
        resource_uri = "bos://hive/federate"
        if action:
            resource_uri = f"{resource_uri}/{action}"
        return {
            "status": "approval_required",
            "proposal_id": f"hive-federate-{uuid.uuid4().hex[:12]}",
            "requested_by": "governance:hive-federation",
            "summary": f"Approval required for {resource_uri} ({governance_scope})",
            "approval_type": "governance",
            "governance_scope": "cluster",
            "required_fields": ["consent_acknowledged", "approval_receipt"],
            "ownership": {
                "truth_owner": "organs/D-Governance/organs/voting/approval_router.py",
                "runtime_owner": "nucleus/Z-Microkernel/infrastructure/bos_daemon/control_plane.py",
                "ingress_surface": "organs/D-Governance/organs/governance/routes/hive.py",
            },
        }

    async def _members_handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        try:
            mod = importlib.import_module("organs.D_Governance.organs.governance.federation.family_hive")
            network = self._get_hive_network()
            params = params or {}

            action = params.get("action")
            if action == "register":
                member = network.register_member(
                    twin_id=params["twin_id"],
                    member_name=params["member_name"],
                    role=params.get("role", "member"),
                    permissions=params.get("permissions", []),
                )
                return {"status": "success", "member": self._serialize_hive_member(member)}
            if action == "remove":
                removed = network.remove_member(params["twin_id"])
                return {"status": "success", "removed": removed, "twin_id": params["twin_id"]}
            if action == "trust":
                updated = network.update_trust_level(params["twin_id"], mod.TrustLevel(params["trust_level"]))
                if not updated:
                    return {"status": "error", "message": "Hive member not found"}
                member = network.get_member(params["twin_id"])
                return {"status": "success", "member": self._serialize_hive_member(member)}
            if action == "get":
                member = network.get_member(params["twin_id"])
                return {"status": "success", "member": self._serialize_hive_member(member)}
            if action == "list":
                members = [self._serialize_hive_member(m) for m in network.get_all_members()]
                return {"status": "success", "members": members}

            return {"status": "error", "message": f"Unknown hive member action: {action}"}
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            _log.error(f"[D-Governance URI] hive_members_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    async def _share_handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        try:
            mod = importlib.import_module("organs.D_Governance.organs.governance.federation.family_hive")
            memory = self._get_cross_twin_memory()
            params = params or {}

            action = params.get("action")
            if action == "share":
                shared = memory.share_memory(
                    source_twin_id=params["source_twin_id"],
                    target_twin_id=params["target_twin_id"],
                    memory_id=params["memory_id"],
                    access_level=mod.AccessLevel(params.get("access_level", "read")),
                )
                return {"status": "success" if shared else "error", "shared": shared}
            if action == "revoke":
                revoked = memory.revoke_access(twin_id=params["source_twin_id"], memory_id=params["memory_id"])
                return {"status": "success" if revoked else "error", "revoked": revoked}
            if action == "shared_with":
                return {"status": "success", "shares": memory.get_shared_with(params["twin_id"])}
            if action == "accessible":
                return {"status": "success", "shares": memory.get_accessible_memories(params["twin_id"])}

            return {"status": "error", "message": f"Unknown hive share action: {action}"}
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            _log.error(f"[D-Governance URI] hive_share_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    async def _delegate_handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        try:
            manager = self._get_delegation_manager()
            params = params or {}

            action = params.get("action")
            if action == "delegate":
                chain = manager.delegate(
                    from_twin_id=params["from_twin_id"],
                    to_twin_id=params["to_twin_id"],
                    scope=params["scope"],
                    permissions=params.get("permissions", []),
                    expires_at=params.get("expires_at"),
                )
                return {"status": "success", "chain": self._serialize_delegation_chain(chain)}
            if action == "list":
                chains = [self._serialize_delegation_chain(c) for c in manager.get_delegation_chain(params["twin_id"])]
                return {"status": "success", "chains": chains}
            if action == "validate":
                allowed = manager.validate_chain(params["twin_id"], params["action_scope"])
                return {"status": "success", "allowed": allowed}

            return {"status": "error", "message": f"Unknown hive delegate action: {action}"}
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            _log.error(f"[D-Governance URI] hive_delegate_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    async def _revoke_handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        try:
            manager = self._get_delegation_manager()
            params = params or {}

            action = params.get("action")
            if action == "delegation":
                revoked = manager.revoke_delegation(params["chain_id"])
                return {"status": "success" if revoked else "error", "revoked": revoked}

            return {"status": "error", "message": f"Unknown hive revoke action: {action}"}
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            _log.error(f"[D-Governance URI] hive_revoke_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    async def _deliberate_handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        try:
            mod = importlib.import_module("organs.D_Governance.organs.governance.collaboration.collective_mind")
            collective = self._get_deliberation()
            params = params or {}

            action = params.get("action")
            if action == "create_session":
                session = collective.create_session(
                    topic=params["topic"],
                    participant_twin_ids=params["participant_twin_ids"],
                    consensus_mode=mod.ConsensusMode(params.get("consensus_mode", "majority")),
                    anonymous=params.get("anonymous", False),
                )
                return {"status": "success", "session": self._serialize_deliberation_session(session)}
            if action == "submit_proposal":
                submitted = collective.submit_proposal(params["session_id"], params["twin_id"], params["content"])
                if not submitted:
                    return {"status": "error", "message": "Unable to submit proposal"}
                session = collective.get_session(params["session_id"])
                proposal = session.proposals[-1] if session and session.proposals else None
                return {"status": "success", "proposal": self._serialize_proposal(proposal)}
            if action == "vote":
                voted = collective.vote(
                    params["session_id"],
                    params["twin_id"],
                    params["proposal_id"],
                    mod.VoteType(params["vote_type"]),
                    weight=float(params.get("weight", 1.0)),
                )
                return {"status": "success" if voted else "error"}
            if action == "resolve":
                outcome = collective.resolve_session(params["session_id"])
                return {"status": "success", "outcome": self._serialize_deliberation_outcome(outcome)}
            if action == "active":
                sessions = [self._serialize_deliberation_session(s) for s in collective.get_active_sessions()]
                return {"status": "success", "sessions": sessions}

            return {"status": "error", "message": f"Unknown hive deliberate action: {action}"}
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            _log.error(f"[D-Governance URI] hive_deliberate_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    async def _federate_handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        """Handle hive federation actions with cluster-scope approval gating.

        `family` scope executes directly once the request is otherwise valid.
        `cluster` scope must pass through `_cluster_approval_required_response()`,
        which surfaces an operator-facing `approval_required` envelope until the
        replayed request carries both `consent_acknowledged=True` and a non-empty
        `approval_receipt`.
        """
        try:
            federated = self._get_federated_learning()
            params = params or {}
            governance_scope = params.get("governance_scope", "family")
            if governance_scope not in {"family", "cluster"}:
                return {"status": "error", "message": "governance_scope must be one of: family, cluster"}

            approval_required = self._cluster_approval_required_response(params)
            if approval_required is not None:
                return approval_required

            action = params.get("action")
            if action == "init_round":
                round_state = federated.init_round(params["participant_twin_ids"])
                return {
                    "status": "success",
                    "round": self._serialize_federated_round(round_state),
                    "governance_scope": governance_scope,
                }
            if action == "submit_gradient":
                accepted = federated.submit_gradient(params["round_id"], params["twin_id"], params.get("gradient"))
                return {
                    "status": "success" if accepted else "error",
                    "accepted": accepted,
                    "governance_scope": governance_scope,
                }
            if action == "status":
                round_status = federated.get_round_status(params["round_id"])
                if not round_status:
                    return {"status": "error", "message": "Federated round not found"}
                return {"status": "success", "round": round_status, "governance_scope": governance_scope}
            if action == "aggregate":
                aggregation = federated.aggregate_gradients(params["round_id"])
                if not aggregation:
                    return {"status": "error", "message": "Federated round has no gradients to aggregate"}
                return {"status": "success", "aggregation": aggregation, "governance_scope": governance_scope}
            if action == "apply":
                result = federated.apply_aggregation(params["round_id"], params["global_model"])
                return {"status": "success", "result": result, "governance_scope": governance_scope}

            return {"status": "error", "message": f"Unknown hive federate action: {action}"}
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            _log.error(f"[D-Governance URI] hive_federate_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    async def _insights_handler(self, uri: str, params: dict | None = None) -> dict[str, object]:
        try:
            insights = self._get_emergent_intelligence()
            params = params or {}

            action = params.get("action")
            if action == "detect":
                detected = insights.detect_insights(params.get("pattern_cluster", []))
                return {"status": "success", "insights": [self._serialize_emergent_insight(i) for i in detected]}
            if action == "list":
                all_insights = insights.get_all_insights()
                return {"status": "success", "insights": [self._serialize_emergent_insight(i) for i in all_insights]}
            if action == "recommend":
                recommendation = insights.generate_recommendation(insights.get_all_insights())
                return {"status": "success", "recommendation": recommendation}
            if action == "wisdom":
                score = insights.evaluate_collective_wisdom(params["deliberation_id"])
                return {"status": "success", "score": score}

            return {"status": "error", "message": f"Unknown hive insights action: {action}"}
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            _log.error(f"[D-Governance URI] hive_insights_handler error: {exc}")
            return {"status": "error", "message": str(exc)}

    def register_routes(self, register: Any) -> None:
        register("hive", "members", self._members_handler)
        register("hive", "share", self._share_handler)
        register("hive", "delegate", self._delegate_handler)
        register("hive", "revoke", self._revoke_handler)
        register("hive", "deliberate", self._deliberate_handler)
        register("hive", "federate", self._federate_handler)
        register("hive", "insights", self._insights_handler)
