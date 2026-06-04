"""Tests for kairon_lib.committee — Committee, CommitteeRole, CommitteeFactory."""

import pytest
from kairon_lib.committee import (
    Committee,
    CommitteeFactory,
    CommitteeRole,
    DecisionAuthority,
    RoleType,
)


class TestCommitteeRole:
    def test_defaults(self):
        role = CommitteeRole(name="@Tester")
        assert role.name == "@Tester"
        assert role.decision_weight == 1.0
        assert role.authority == DecisionAuthority.ADVISORY

    def test_named_constructors(self):
        prime = CommitteeRole.prime()
        assert prime.name == "@Prime"
        assert prime.role_type == RoleType.CTO
        assert prime.decision_weight == 1.5
        assert "architecture" in prime.veto_domains

        nyx = CommitteeRole.nyx()
        assert nyx.name == "@Nyx"
        assert nyx.role_type == RoleType.CPO

        forge = CommitteeRole.forge()
        assert forge.name == "@Forge"

        guardian = CommitteeRole.guardian()
        assert guardian.name == "@Guardian"

        omega = CommitteeRole.omega()
        assert omega.name == "@Omega"

    def test_to_dict(self):
        role = CommitteeRole(name="@Devil", archetype="QA", authority=DecisionAuthority.MAJORITY)
        d = role.to_dict()
        assert d["name"] == "@Devil"
        assert d["authority"] == "majority"


class TestCommittee:
    def test_create_empty(self):
        c = Committee(name="Test Committee", purpose="Testing")
        assert c.name == "Test Committee"
        assert c.roles == []

    def test_add_role(self):
        c = Committee(name="Test", purpose="Test")
        role = CommitteeRole(name="@Builder", role_type=RoleType.TECH_LEAD)
        c.add_role(role)
        assert len(c.roles) == 1
        assert c.roles[0].name == "@Builder"

    def test_get_role_by_name(self):
        c = Committee(name="Test", purpose="Test")
        c.add_role(CommitteeRole(name="@Sage"))
        role = c.get_role("@Sage")
        assert role is not None
        assert role.name == "@Sage"

    def test_get_role_by_type(self):
        c = Committee(name="Test", purpose="Test")
        c.add_role(CommitteeRole(name="@Arch", role_type=RoleType.CTO))
        role = c.get_role(RoleType.CTO)
        assert role is not None
        assert role.name == "@Arch"

    def test_get_nonexistent_role(self):
        c = Committee(name="Test", purpose="Test")
        assert c.get_role("GHOST") is None

    def test_role_names(self):
        c = Committee(name="Test", purpose="Test")
        c.add_role(CommitteeRole(name="@A"))
        c.add_role(CommitteeRole(name="@B"))
        assert set(c.role_names()) == {"@A", "@B"}

    def test_deliberate_returns_result(self):
        c = Committee.create_standard("Deliberation Test")
        result = c.deliberate("Should we adopt async workers?")
        assert "topic" in result
        assert "decision" in result or "outcome" in result or "status" in result

    def test_decision_log(self):
        c = Committee(name="Log Test", purpose="Testing")
        c.record_decision("Use FastAPI", voter="CTO", approved=True)
        c.record_decision("Use Redis", voter="CTO", approved=False)
        log = c.get_decision_log()
        assert len(log) == 2
        assert log[0]["decision"] == "Use FastAPI"

    def test_summary(self):
        c = Committee(name="Summ", purpose="Test purposes")
        c.add_role(CommitteeRole(name="@One"))
        c.add_role(CommitteeRole(name="@Two"))
        s = c.summary()
        assert "Summ" in s
        assert "2 roles" in s or "2" in s

    def test_decision_makers(self):
        c = Committee(name="Makers", purpose="Test")
        maker = CommitteeRole(name="@Decider", authority=DecisionAuthority.CONSENSUS)
        advisor = CommitteeRole(name="@Advisor", authority=DecisionAuthority.ADVISORY)
        c.add_role(maker)
        c.add_role(advisor)
        makers = c.decision_makers()
        assert len(makers) == 1
        assert makers[0].name == "@Decider"


class TestStandardCommittee:
    def test_create_standard(self):
        c = Committee.create_standard("My Project")
        assert c.name == "My Project"
        assert len(c.roles) >= 3  # @Prime, @Nyx, @Forge minimum
        assert c.get_role("@Prime") is not None

    def test_standard_committee_deliberate(self):
        c = Committee.create_standard("Test")
        result = c.deliberate("Should we refactor the auth module?")
        assert result is not None


class TestCommitteeFactory:
    def test_full_committee(self):
        c = CommitteeFactory.full_committee()
        assert c.name == "Full B-OS Committee"
        assert len(c.roles) > 0

    def test_product_committee(self):
        c = CommitteeFactory.product_committee()
        assert c.name == "Product Committee"
        assert c.get_role("@Nyx") is not None

    def test_execution_committee(self):
        c = CommitteeFactory.execution_committee()
        assert c.name == "Execution Committee"

    def test_advisory_committee(self):
        c = CommitteeFactory.advisory_committee("security")
        assert c.name == "Security Advisory Committee"
        assert len(c.roles) > 0

    def test_list_domains(self):
        domains = CommitteeFactory.list_domains()
        assert len(domains) > 0

    def test_from_template_valid(self):
        c = CommitteeFactory.from_template("product")
        assert c is not None
        assert len(c.roles) > 0

    def test_from_template_invalid(self):
        with pytest.raises(ValueError, match="Unknown template"):
            CommitteeFactory.from_template("nonexistent")

    def test_for_domain(self):
        c = CommitteeFactory.for_domain("ml-ops", goal="Deploy ML pipeline")
        assert c is not None

    def test_from_config(self):
        config = {
            "name": "Config Committee",
            "purpose": "From config",
            "roles": [
                {"name": "@Alpha", "archetype": "CTO"},
                {"name": "@Beta", "archetype": "CPO"},
            ],
        }
        c = CommitteeFactory.from_config(config)
        assert c.name == "Config Committee"
        assert len(c.roles) == 2

    def test_register_template(self):
        CommitteeFactory.register_template("custom_test", lambda **kw: Committee("Custom", "Custom"))
        c = CommitteeFactory.from_template("custom_test")
        assert c.name == "Custom"
