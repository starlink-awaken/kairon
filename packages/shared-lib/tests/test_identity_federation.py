"""Tests for kairon_lib.identity_federation — IdentityFederationBridge."""

import pytest

try:
    from kairon_lib.identity_federation import FederatedIdentity, IdentityFederationBridge
except ImportError:
    pytestmark = pytest.mark.skip(reason="test requires archived kairon_lib module")  # type: ignore[name-defined]


class TestFederatedIdentity:
    def test_defaults(self):
        fi = FederatedIdentity(local_id="local-1", remote_id="remote-abc", provider="github")
        assert fi.trust_level == 0.5
        assert fi.metadata == {}


class TestIdentityFederationBridge:
    def test_link_identity(self):
        bridge = IdentityFederationBridge()
        link = bridge.link_identity("local-1", "remote-abc", "github", trust_level=0.8)
        assert link.local_id == "local-1"
        assert link.remote_id == "remote-abc"
        assert link.provider == "github"
        assert link.trust_level == 0.8

    def test_link_identity_clamps_trust(self):
        bridge = IdentityFederationBridge()
        link = bridge.link_identity("local-1", "remote-abc", "github", trust_level=1.5)
        assert link.trust_level == 1.0
        link2 = bridge.link_identity("local-2", "remote-xyz", "gitlab", trust_level=-0.5)
        assert link2.trust_level == 0.0

    def test_resolve_local_found(self):
        bridge = IdentityFederationBridge()
        bridge.link_identity("local-1", "remote-abc", "github")
        assert bridge.resolve_local("remote-abc", "github") == "local-1"

    def test_resolve_local_not_found(self):
        bridge = IdentityFederationBridge()
        assert bridge.resolve_local("nonexistent", "github") is None

    def test_resolve_remote_found(self):
        bridge = IdentityFederationBridge()
        bridge.link_identity("local-1", "remote-abc", "github")
        assert bridge.resolve_remote("local-1", "github") == "remote-abc"

    def test_resolve_remote_not_found(self):
        bridge = IdentityFederationBridge()
        assert bridge.resolve_remote("local-1", "github") is None

    def test_get_linked_identities(self):
        bridge = IdentityFederationBridge()
        bridge.link_identity("local-1", "remote-1", "github")
        bridge.link_identity("local-1", "remote-2", "gitlab")
        bridge.link_identity("local-2", "remote-3", "github")
        links = bridge.get_linked_identities("local-1")
        assert len(links) == 2

    def test_unlink(self):
        bridge = IdentityFederationBridge()
        bridge.link_identity("local-1", "remote-abc", "github")
        bridge.unlink("local-1", "github")
        assert bridge.resolve_remote("local-1", "github") is None

    def test_unlink_nonexistent(self):
        bridge = IdentityFederationBridge()
        bridge.unlink("local-1", "github")  # should not raise

    def test_get_trust_level(self):
        bridge = IdentityFederationBridge()
        bridge.link_identity("local-1", "remote-abc", "github", trust_level=0.9)
        assert bridge.get_trust_level("local-1", "github") == 0.9
        assert bridge.get_trust_level("local-1", "unknown") == 0.0

    def test_update_trust(self):
        bridge = IdentityFederationBridge()
        bridge.link_identity("local-1", "remote-abc", "github", trust_level=0.5)
        bridge.update_trust("local-1", "github", 0.95)
        assert bridge.get_trust_level("local-1", "github") == 0.95

    def test_update_trust_nonexistent(self):
        bridge = IdentityFederationBridge()
        with pytest.raises(KeyError):
            bridge.update_trust("local-1", "github", 0.5)

    def test_get_providers(self):
        bridge = IdentityFederationBridge()
        bridge.link_identity("local-1", "r1", "github")
        bridge.link_identity("local-1", "r2", "gitlab")
        providers = bridge.get_providers()
        assert providers == ["github", "gitlab"]

    def test_get_federation_stats(self):
        bridge = IdentityFederationBridge()
        bridge.link_identity("local-1", "r1", "github", trust_level=0.8)
        bridge.link_identity("local-1", "r2", "gitlab", trust_level=0.6)
        bridge.link_identity("local-2", "r3", "github", trust_level=0.9)
        stats = bridge.get_federation_stats()
        assert stats["total_links"] == 3
        assert stats["unique_local_ids"] == 2
        assert stats["providers"]["github"] == 2
        assert stats["providers"]["gitlab"] == 1
        assert abs(stats["average_trust"] - 0.7667) < 0.01
