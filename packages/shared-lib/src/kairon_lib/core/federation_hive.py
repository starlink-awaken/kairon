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
# Family Hive ≡ Module
# 内涵 ≝ {Family, Hive}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, FamilyHive)}
# 功能 ⊢ {Family_Hive, Init_Family, Validate_Hive}
# =============================================================================

"""Family Hive Network — multi-member digital twin network.

---
Type: Organ
Layer: L4
Domain: D-Governance
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Authority: EC-7/PB-3
Keywords: [family, hive, network, twin, delegation, trust]
BOS-URI:
  - bos://hive/members   — FamilyHiveNetwork registry
  - bos://hive/share      — CrossTwinMemory share endpoint
  - bos://hive/delegate   — DelegationChain delegate endpoint
  - bos://hive/revoke     — DelegationChain revoke endpoint
---

# P8.1 Family Hive Network
## family_hive_v1 — FamilyHiveNode + FamilyHiveNetwork
## cross_twin_memory — CrossTwinMemory
## delegation_chain — DelegationChainManager

S5 公理参考: 用户主权优先 — 所有成员注册、内存共享、委托授权均须用户授权。
"""

import sqlite3
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

_FACT_GRAPH_OPERATIONAL_ERRORS = (OSError, RuntimeError, sqlite3.Error)
MAX_RETRY_QUEUE_SIZE = 1000


# === Trust levels ===
class TrustLevel(StrEnum):
    TRUSTED = "trusted"  # 1.0
    FAMILY = "family"  # 0.9
    ACQUAINTANCE = "acquaintance"  # 0.7
    UNTRUSTED = "untrusted"  # 0.0


# === Memory access levels ===
class AccessLevel(StrEnum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NONE = "none"


# === FamilyHiveNode ===
@dataclass
class FamilyHiveNode:
    """Represents a member node in the Family Hive Network."""

    node_id: str
    twin_id: str
    member_name: str
    role: str
    permissions: list[str]
    trust_level: TrustLevel
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, object] = field(default_factory=dict)


# === FamilyHiveNetwork ===
class FamilyHiveNetwork:
    """Manages member registration, trust levels, and roles within the family hive.

    BOS-URI: bos://hive/members
    """

    def __init__(self, metadata_path: str = "organs/D-Governance/organs/family_hive.py") -> None:
        self._lock = threading.RLock()
        self._nodes: dict[str, FamilyHiveNode] = {}
        self._fact_graph: Any = None  # Lazy-loaded
        self._persist_failure_count: int = 0  # 降级计数器
        self._persist_retry_queue: list[dict] = []  # 重试队列
        _log.info("FamilyHiveNetwork initialised")

    def _get_fact_graph(self) -> Any:
        """Lazily load FactGraph to avoid circular imports."""
        if self._fact_graph is None:
            try:
                from organs.D_Memory.organs.fact_graph import FactGraph  # type: ignore[import-not-found]

                self._fact_graph = FactGraph()
            except (ImportError, OSError):
                self._fact_graph = True  # Mark as unavailable
        return self._fact_graph if self._fact_graph is not True else None

    def _persist_to_fact_graph(self, node: FamilyHiveNode) -> None:
        """Persist member registration to FactGraph."""
        fg = self._get_fact_graph()
        if fg is None:
            return
        try:
            fg.add_fact(
                sub=f"twin:{node.twin_id}",
                pred="hive:memberOf",
                obj="hive:FamilyHive",
                metadata={
                    "member_name": node.member_name,
                    "role": node.role,
                    "trust_level": node.trust_level.value,
                    "registered_at": node.registered_at.isoformat(),
                },
            )
            fg.add_fact(
                sub=f"twin:{node.twin_id}",
                pred="hive:hasTrustLevel",
                obj=f"hive:{node.trust_level.value}",
            )
        except _FACT_GRAPH_OPERATIONAL_ERRORS as exc:
            self._persist_failure_count += 1
            if len(self._persist_retry_queue) >= MAX_RETRY_QUEUE_SIZE:
                self._persist_retry_queue.pop(0)
            self._persist_retry_queue.append({"type": "node", "node": node})
            _log.warning(
                "[FamilyHive] FactGraph persistence degraded for %s, queued for retry (queue size=%d): %s",
                node.twin_id,
                len(self._persist_retry_queue),
                exc,
            )

    @staticmethod
    def _member_subject(twin_id: str) -> str:
        return f"twin:{twin_id}"

    def _delete_member_facts(self, node: FamilyHiveNode) -> None:
        """Delete only FamilyHive-owned facts for a member."""
        fg = self._get_fact_graph()
        if fg is None:
            return
        member_subject = self._member_subject(node.twin_id)
        fg.delete(sub=member_subject, pred="hive:memberOf", obj="hive:FamilyHive")
        fg.delete(sub=member_subject, pred="hive:hasTrustLevel", obj=None)

    def _refresh_member_in_fact_graph(self, node: FamilyHiveNode) -> None:
        """Replace FamilyHive-owned facts for a member with current state."""
        fg = self._get_fact_graph()
        if fg is None:
            return
        try:
            self._delete_member_facts(node)
            self._persist_to_fact_graph(node)
        except _FACT_GRAPH_OPERATIONAL_ERRORS as exc:
            self._persist_failure_count += 1
            if len(self._persist_retry_queue) >= MAX_RETRY_QUEUE_SIZE:
                self._persist_retry_queue.pop(0)
            self._persist_retry_queue.append({"type": "node", "node": node})
            _log.warning(
                "[FamilyHive] FactGraph trust sync degraded for %s, queued for retry (queue size=%d): %s",
                node.twin_id,
                len(self._persist_retry_queue),
                exc,
            )

    def register_member(
        self,
        twin_id: str,
        member_name: str,
        role: str = "member",
        permissions: list[str] | None = None,
    ) -> FamilyHiveNode:
        """Register a new member in the family hive network.

        Args:
            twin_id: Unique identifier of the digital twin.
            member_name: Display name of the member.
            role: Role assigned to the member (default: 'member').
            permissions: List of permission strings granted to the member.

        Returns:
            The newly created FamilyHiveNode.
        """
        node = FamilyHiveNode(
            node_id=str(uuid.uuid4()),
            twin_id=twin_id,
            member_name=member_name,
            role=role,
            permissions=permissions if permissions is not None else [],
            trust_level=TrustLevel.ACQUAINTANCE,
        )
        with self._lock:
            self._nodes[twin_id] = node
        self._persist_to_fact_graph(node)
        _log.info("[FamilyHive] Registered member %s as %s", twin_id, role)
        return node

    def remove_member(self, twin_id: str) -> bool:
        """Remove a member from the family hive network.

        Args:
            twin_id: The twin ID of the member to remove.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            if twin_id not in self._nodes:
                return False
            node = self._nodes[twin_id]
            del self._nodes[twin_id]
        self._delete_from_fact_graph(node)
        _log.info("[FamilyHive] Removed member %s", twin_id)
        return True

    def _delete_from_fact_graph(self, node: FamilyHiveNode) -> None:
        """Delete all FG records for a member node."""
        fg = self._get_fact_graph()
        if fg is None:
            return
        try:
            self._delete_member_facts(node)
        except _FACT_GRAPH_OPERATIONAL_ERRORS as exc:
            _log.warning(
                "[FamilyHive] Failed to delete FG records for %s: %s",
                node.twin_id,
                exc,
            )

    def get_member(self, twin_id: str) -> FamilyHiveNode | None:
        """Retrieve a member by twin ID.

        Args:
            twin_id: The twin ID to look up.

        Returns:
            FamilyHiveNode if found, None otherwise.
        """
        return self._nodes.get(twin_id)

    def get_all_members(self) -> list[FamilyHiveNode]:
        """Return all registered members.

        Returns:
            List of all FamilyHiveNode instances.
        """
        with self._lock:
            return list(self._nodes.values())

    def update_trust_level(self, twin_id: str, new_level: TrustLevel) -> bool:
        """Update the trust level for a member.

        Args:
            twin_id: The twin ID of the member.
            new_level: The new TrustLevel to assign.

        Returns:
            True if updated, False if member not found.
        """
        with self._lock:
            if twin_id in self._nodes:
                node = self._nodes[twin_id]
                node.trust_level = new_level
                self._refresh_member_in_fact_graph(node)
                _log.info("[FamilyHive] Updated trust level for %s to %s", twin_id, new_level.value)
                return True
        return False

    def get_metrics(self) -> dict[str, object]:
        """Return degradation and operational metrics."""
        return {
            "persist_failure_count": self._persist_failure_count,
            "registered_members": len(self._nodes),
        }


# === CrossTwinMemory ===
class CrossTwinMemory:
    """Manages cross-twin memory sharing with access-level controls.

    BOS-URI: bos://hive/share

    Integration: fact_graph for shared memory triples.
    """

    def __init__(self, metadata_path: str = "organs/D-Governance/organs/family_hive.py") -> None:
        self._lock = threading.RLock()
        # key: f"{source_twin_id}::{target_twin_id}::{memory_id}"
        self._shares: dict[str, dict] = {}
        self._fact_graph: Any = None  # Lazy-loaded
        self._persist_retry_queue: list[dict] = []  # 重试队列
        _log.info("CrossTwinMemory initialised")

    @staticmethod
    def _share_key(source_twin_id: str, target_twin_id: str, memory_id: str) -> str:
        return f"{source_twin_id}::{target_twin_id}::{memory_id}"

    @staticmethod
    def _share_target_object(target_twin_id: str, memory_id: str) -> str:
        return f"twin:{target_twin_id}#memory:{memory_id}"

    @staticmethod
    def _shared_memory_object(target_twin_id: str, memory_id: str) -> str:
        return f"memory:{memory_id}#target:{target_twin_id}"

    def _get_fact_graph(self) -> Any:
        """Lazily load FactGraph to avoid circular imports."""
        if self._fact_graph is None:
            try:
                from organs.D_Memory.organs.fact_graph import FactGraph

                self._fact_graph = FactGraph()
            except (ImportError, OSError):
                self._fact_graph = True
        return self._fact_graph if self._fact_graph is not True else None

    def _persist_share_to_fact_graph(self, source: str, target: str, memory_id: str, access_level: AccessLevel) -> None:
        """Persist memory share to FactGraph."""
        fg = self._get_fact_graph()
        if fg is None:
            return
        try:
            fg.add_fact(
                sub=f"twin:{source}",
                pred="hive:sharesMemoryWith",
                obj=self._share_target_object(target, memory_id),
                metadata={
                    "memory_id": memory_id,
                    "access_level": access_level.value,
                    "shared_at": datetime.now(UTC).isoformat(),
                },
            )
            fg.add_fact(
                sub=f"twin:{source}",
                pred="hive:sharedMemory",
                obj=self._shared_memory_object(target, memory_id),
            )
        except _FACT_GRAPH_OPERATIONAL_ERRORS as exc:
            if len(self._persist_retry_queue) >= MAX_RETRY_QUEUE_SIZE:
                self._persist_retry_queue.pop(0)
            self._persist_retry_queue.append(
                {
                    "type": "share",
                    "source": source,
                    "target": target,
                    "memory_id": memory_id,
                    "access_level": access_level,
                }
            )
            _log.warning(
                "[CrossTwin] FactGraph persistence degraded for %s -> %s (%s), queued for retry (queue size=%d): %s",
                source,
                target,
                memory_id,
                len(self._persist_retry_queue),
                exc,
            )

    def share_memory(
        self,
        source_twin_id: str,
        target_twin_id: str,
        memory_id: str,
        access_level: AccessLevel = AccessLevel.READ,
    ) -> bool:
        """Share a memory with another twin.

        Args:
            source_twin_id: The twin sharing the memory.
            target_twin_id: The twin being granted access.
            memory_id: Identifier of the memory to share.
            access_level: Level of access granted (READ, WRITE, EXECUTE).

        Returns:
            True on success.
        """
        key = self._share_key(source_twin_id, target_twin_id, memory_id)
        with self._lock:
            self._shares[key] = {
                "source": source_twin_id,
                "target": target_twin_id,
                "memory_id": memory_id,
                "access_level": access_level.value,
                "shared_at": datetime.now(UTC).isoformat(),
            }
        self._persist_share_to_fact_graph(source_twin_id, target_twin_id, memory_id, access_level)
        _log.info(
            "[CrossTwin] %s shared %s with %s (%s)",
            source_twin_id,
            memory_id,
            target_twin_id,
            access_level.value,
        )
        return True

    def revoke_access(self, twin_id: str, memory_id: str) -> bool:
        """Revoke all access grants for a specific memory from a given twin.

        Args:
            twin_id: The source twin whose share is being revoked.
            memory_id: The memory ID to revoke.

        Returns:
            True if revoked, False if no matching share found.
        """
        revoked_shares: list[dict[str, object]] = []
        with self._lock:
            for key in list(self._shares.keys()):
                share = self._shares[key]
                if share["source"] == twin_id and share["memory_id"] == memory_id:
                    revoked_shares.append(share)
                    del self._shares[key]
        for share_data in revoked_shares:
            self._delete_share_from_fact_graph(share_data["source"], share_data["target"], share_data["memory_id"])
        if revoked_shares:
            _log.info("[CrossTwin] Revoked %s::%s", twin_id, memory_id)
        return bool(revoked_shares)

    def _delete_share_from_fact_graph(self, source: str, target: str, memory_id: str) -> None:
        """Delete all FG records for a revoked memory share."""
        fg = self._get_fact_graph()
        if fg is None:
            return
        try:
            share_subject = f"twin:{source}"
            fg.delete(
                sub=share_subject,
                pred="hive:sharesMemoryWith",
                obj=self._share_target_object(target, memory_id),
            )
            fg.delete(
                sub=share_subject,
                pred="hive:sharedMemory",
                obj=self._shared_memory_object(target, memory_id),
            )
        except _FACT_GRAPH_OPERATIONAL_ERRORS as exc:
            _log.warning(
                "[CrossTwin] Failed to delete FG records for share %s: %s",
                source,
                exc,
            )

    def get_shared_with(self, twin_id: str) -> list[dict]:
        """Get all memories shared BY a given twin.

        Args:
            twin_id: The source twin.

        Returns:
            List of share records where twin_id is the source.
        """
        with self._lock:
            return [s for s in self._shares.values() if s["source"] == twin_id]

    def get_accessible_memories(self, twin_id: str) -> list[dict]:
        """Get all memories accessible TO a given twin.

        Args:
            twin_id: The target twin.

        Returns:
            List of share records where twin_id is the target.
        """
        with self._lock:
            return [s for s in self._shares.values() if s["target"] == twin_id]


# === DelegationChain ===
@dataclass
class DelegationChain:
    """Represents a delegation relationship between two twins."""

    chain_id: str
    delegator: str
    delegate: str
    scope: str
    permissions: list[str]
    expires_at: str | None
    chain_depth: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class DelegationChainManager:
    """Manages delegation chains with depth limits and expiration.

    BOS-URI:
      - bos://hive/delegate  — delegate action
      - bos://hive/revoke    — revoke action
    """

    CHAIN_DEPTH_MAX: int = 5  # S5 公理: 用户主权优先

    def __init__(
        self,
        metadata_path: str = "organs/D-Governance/organs/family_hive.py",
        _hive_network: FamilyHiveNetwork | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._chains: dict[str, DelegationChain] = {}
        self._hive_network = _hive_network
        _log.info("DelegationChainManager initialised")

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def validate_access(self, operation: str, context: dict[str, object]) -> bool:
        return True

    def get_metadata(self) -> dict[str, object]:
        return {
            "organ": "DelegationChainManager",
            "domain": "D-Governance",
            "max_chain_depth": self.CHAIN_DEPTH_MAX,
        }

    def get_registry_info(self) -> dict[str, object]:
        return {
            "bos_uri": ["bos://hive/delegate", "bos://hive/revoke"],
            "status": "active",
        }

    def delegate(
        self,
        from_twin_id: str,
        to_twin_id: str,
        scope: str,
        permissions: list[str],
        expires_at: str | None = None,
        _permission_check: (Callable[[str, str], bool] | None) = None,
    ) -> DelegationChain:
        """Create a delegation from one twin to another.

        Args:
            from_twin_id: The delegating twin.
            to_twin_id: The delegated twin.
            scope: Action scope being delegated (e.g., 'memory.read', '*').
            permissions: List of permission strings granted.
            expires_at: ISO timestamp for expiration, or None for no expiration.
            _permission_check: Optional callable(from_twin_id, permission) -> bool.
                Must return True if from_twin holds that permission.
                If not provided, permission check is skipped (backward-compatible).

        Returns:
            The created DelegationChain.

        Raises:
            PermissionError: If _permission_check returns False for any
                permission being delegated (S5 axiom: user sovereignty).
        """
        # Build permission checker: explicit callback > hive_network > skip
        effective_checker: Callable[[str, str], bool] | None = _permission_check
        if effective_checker is None and self._hive_network is not None:

            def _hive_checker(from_id: str, perm: str) -> bool:
                nodes = getattr(self._hive_network, "_nodes", None)
                if nodes is None:
                    return False
                node = nodes.get(from_id)
                return node is not None and perm in node.permissions

            effective_checker = _hive_checker

        if effective_checker is not None:
            for perm in permissions:
                if not effective_checker(from_twin_id, perm):
                    _log.warning(
                        "[Delegation] Permission denied: %s lacks '%s' (tried to delegate to %s)",
                        from_twin_id,
                        perm,
                        to_twin_id,
                    )
                    raise PermissionError(
                        f"Twin '{from_twin_id}' does not hold permission '{perm}' and cannot delegate it"
                    )
        # Validate chain depth before adding
        existing_chains = self.get_delegation_chain(from_twin_id)
        current_depth = max((c.chain_depth for c in existing_chains if c.delegator == from_twin_id), default=0)
        proposed_depth = current_depth + 1
        if proposed_depth > self.CHAIN_DEPTH_MAX:
            _log.warning(
                "[Delegation] Chain depth limit exceeded: %s (max=%d, proposed=%d)",
                from_twin_id,
                self.CHAIN_DEPTH_MAX,
                proposed_depth,
            )
            raise ValueError(
                f"Delegation chain depth limit exceeded for '{from_twin_id}' "
                f"(max={self.CHAIN_DEPTH_MAX}, proposed={proposed_depth})"
            )
        chain = DelegationChain(
            chain_id=str(uuid.uuid4()),
            delegator=from_twin_id,
            delegate=to_twin_id,
            scope=scope,
            permissions=permissions,
            expires_at=expires_at,
            chain_depth=proposed_depth,
        )
        with self._lock:
            self._chains[chain.chain_id] = chain
        _log.info(
            "[Delegation] %s delegated %s to %s (expires=%s)",
            from_twin_id,
            scope,
            to_twin_id,
            expires_at,
        )
        return chain

    def revoke_delegation(self, chain_id: str) -> bool:
        """Revoke a delegation chain by ID.

        Args:
            chain_id: The delegation chain ID to revoke.

        Returns:
            True if revoked, False if not found.
        """
        with self._lock:
            if chain_id in self._chains:
                del self._chains[chain_id]
                _log.info("[Delegation] Revoked chain %s", chain_id)
                return True
        return False

    def get_delegation_chain(self, twin_id: str) -> list[DelegationChain]:
        """Get all delegation chains involving a twin (as delegator or delegate).

        Args:
            twin_id: The twin of interest.

        Returns:
            List of DelegationChain records.
        """
        with self._lock:
            return [c for c in self._chains.values() if c.delegator == twin_id or c.delegate == twin_id]

    def validate_chain(self, twin_id: str, action: str) -> bool:
        """Validate whether a twin has a valid (non-expired) delegation for an action.

        Args:
            twin_id: The twin attempting the action.
            action: The action scope being performed.

        Returns:
            True if a valid delegation covers the action, False otherwise.
        """
        chains = self.get_delegation_chain(twin_id)
        now = datetime.now(UTC)
        for chain in chains:
            if chain.scope == action or chain.scope == "*":
                if chain.expires_at is None:
                    return True
                try:
                    expires = datetime.fromisoformat(chain.expires_at)
                    if expires > now:
                        return True
                except ValueError:
                    _log.warning("[Delegation] Invalid expires_at format: %s", chain.expires_at)
        return False
