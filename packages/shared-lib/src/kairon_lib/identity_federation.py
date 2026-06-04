from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Identity Federation Bridge ≡ Module
# 内涵 ≝ {Identity, Federation, Bridge}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, IdentityFederationBridge)}
# 功能 ⊢ {Identity_Federation, Federation_Bridge, Bridge_Init}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

"""Identity Federation Bridge — cross-provider identity linking.

Maps local agent identities to remote federated identities across multiple
providers, tracks trust levels, and supports bidirectional resolution.

Usage:
    bridge = IdentityFederationBridge()
    link = bridge.link_identity("local-1", "remote-abc", "github", trust_level=0.8)
    assert bridge.resolve_local("remote-abc", "github") == "local-1"
"""

import time
from dataclasses import dataclass, field


@dataclass
class FederatedIdentity:
    """A link between a local identity and a remote federated identity."""

    local_id: str
    remote_id: str
    provider: str
    trust_level: float = 0.5
    metadata: dict = field(default_factory=dict)
    linked_at: float = 0.0


class IdentityFederationBridge:
    """Manages cross-provider identity linkage and trust."""

    def __init__(self) -> None:
        # (local_id, provider) -> FederatedIdentity
        self._links: dict[tuple[str, str], FederatedIdentity] = {}

    def link_identity(
        self,
        local_id: str,
        remote_id: str,
        provider: str,
        trust_level: float = 0.5,
        metadata: dict | None = None,
    ) -> FederatedIdentity:
        """Create or update a federated identity link."""
        ident = FederatedIdentity(
            local_id=local_id,
            remote_id=remote_id,
            provider=provider,
            trust_level=max(0.0, min(1.0, trust_level)),
            metadata=dict(metadata or {}),
            linked_at=time.time(),
        )
        self._links[(local_id, provider)] = ident
        return ident

    def resolve_local(self, remote_id: str, provider: str) -> str | None:
        """Find the local ID linked to *remote_id* at *provider*."""
        for link in self._links.values():
            if link.remote_id == remote_id and link.provider == provider:
                return link.local_id
        return None

    def resolve_remote(self, local_id: str, provider: str) -> str | None:
        """Find the remote ID linked to *local_id* at *provider*."""
        link = self._links.get((local_id, provider))
        return link.remote_id if link else None

    def get_linked_identities(self, local_id: str) -> list[FederatedIdentity]:
        """Return all federated identities linked to *local_id*."""
        return [link for link in self._links.values() if link.local_id == local_id]

    def unlink(self, local_id: str, provider: str) -> None:
        """Remove a federated identity link."""
        self._links.pop((local_id, provider), None)

    def get_trust_level(self, local_id: str, provider: str) -> float:
        """Return trust level for a link, or 0.0 if not found."""
        link = self._links.get((local_id, provider))
        return link.trust_level if link else 0.0

    def update_trust(self, local_id: str, provider: str, new_level: float) -> None:
        """Update the trust level for an existing link."""
        link = self._links.get((local_id, provider))
        if link is None:
            raise KeyError(f"No link for ({local_id}, {provider})")
        link.trust_level = max(0.0, min(1.0, new_level))

    def get_providers(self) -> list[str]:
        """Return all known federation provider names."""
        return sorted({link.provider for link in self._links.values()})

    def get_federation_stats(self) -> dict:
        """Return aggregated federation statistics."""
        providers: dict[str, int] = {}
        locals_set: set[str] = set()
        for link in self._links.values():
            providers[link.provider] = providers.get(link.provider, 0) + 1
            locals_set.add(link.local_id)
        avg_trust = sum(link.trust_level for link in self._links.values()) / len(self._links) if self._links else 0.0
        return {
            "total_links": len(self._links),
            "providers": providers,
            "unique_local_ids": len(locals_set),
            "average_trust": round(avg_trust, 4),
        }
