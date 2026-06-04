"""Tests for kairon_lib.capability_standardization — CapabilityStandard, ComplianceResult, CapabilityStandardization."""

import pytest
from kairon_lib.capability_standardization import (
    CapabilityStandard,
    CapabilityStandardization,
    ComplianceResult,
)


class TestCapabilityStandard:
    def test_creation(self):
        std = CapabilityStandard("mcp-v1", "MCP v1", "Basic MCP", ["tool_call", "list_tools"])
        assert std.standard_id == "mcp-v1"
        assert std.name == "MCP v1"
        assert len(std.required_interfaces) == 2
        assert std.version == "1.0"


class TestComplianceResult:
    def test_compliant(self):
        r = ComplianceResult(entity_id="agent-1", standard_id="mcp-v1", compliant=True)
        assert r.compliant is True
        assert r.missing == []
        assert r.extra == []

    def test_non_compliant_with_missing_extra(self):
        r = ComplianceResult(
            entity_id="agent-1", standard_id="mcp-v1", compliant=False,
            missing=["tool_call"], extra=["unknown_api"],
        )
        assert r.compliant is False
        assert "tool_call" in r.missing
        assert "unknown_api" in r.extra


class TestCapabilityStandardization:
    def test_define_standard(self):
        cs = CapabilityStandardization()
        std = CapabilityStandard("std-1", "Standard 1", "desc", ["a", "b"])
        cs.define_standard(std)
        assert cs.get_standard("std-1") is std

    def test_define_standard_overwrites(self):
        cs = CapabilityStandardization()
        cs.define_standard(CapabilityStandard("std-1", "v1", "d", ["a"]))
        cs.define_standard(CapabilityStandard("std-1", "v2", "d", ["a", "b"]))
        assert cs.get_standard("std-1").name == "v2"

    def test_list_standards(self):
        cs = CapabilityStandardization()
        cs.define_standard(CapabilityStandard("s1", "", "", []))
        cs.define_standard(CapabilityStandard("s2", "", "", []))
        assert len(cs.list_standards()) == 2

    def test_check_compliance_passes(self):
        cs = CapabilityStandardization()
        cs.define_standard(CapabilityStandard("mcp-v1", "MCP v1", "", ["tool_call", "list_tools"]))
        result = cs.check_compliance("agent-1", ["tool_call", "list_tools", "extra_api"], "mcp-v1")
        assert result.compliant is True
        assert result.missing == []
        assert "extra_api" in result.extra

    def test_check_compliance_fails(self):
        cs = CapabilityStandardization()
        cs.define_standard(CapabilityStandard("mcp-v1", "MCP v1", "", ["tool_call", "list_tools"]))
        result = cs.check_compliance("agent-2", ["tool_call"], "mcp-v1")
        assert result.compliant is False
        assert result.missing == ["list_tools"]

    def test_check_compliance_unknown_standard_raises(self):
        cs = CapabilityStandardization()
        with pytest.raises(KeyError, match="Unknown standard"):
            cs.check_compliance("agent-1", ["a"], "nonexistent")

    def test_get_standard_nonexistent(self):
        cs = CapabilityStandardization()
        assert cs.get_standard("ghost") is None

    def test_get_compliant_entities(self):
        cs = CapabilityStandardization()
        cs.define_standard(CapabilityStandard("s1", "", "", ["req"]))
        cs.check_compliance("e1", ["req", "extra"], "s1")
        cs.check_compliance("e2", ["req"], "s1")
        cs.check_compliance("e3", [], "s1")
        compliant = cs.get_compliant_entities("s1")
        assert "e1" in compliant
        assert "e2" in compliant
        assert "e3" not in compliant

    def test_get_non_compliant_entities(self):
        cs = CapabilityStandardization()
        cs.define_standard(CapabilityStandard("s1", "", "", ["req"]))
        cs.check_compliance("e1", ["req"], "s1")
        cs.check_compliance("e2", [], "s1")
        non_compliant = cs.get_non_compliant_entities("s1")
        assert "e2" in non_compliant
        assert "e1" not in non_compliant

    def test_get_compliance_matrix(self):
        cs = CapabilityStandardization()
        cs.define_standard(CapabilityStandard("s1", "", "", ["a"]))
        cs.define_standard(CapabilityStandard("s2", "", "", ["b"]))
        cs.check_compliance("e1", ["a", "b"], "s1")
        cs.check_compliance("e1", ["b"], "s2")
        matrix = cs.get_compliance_matrix()
        assert matrix["e1"]["s1"] is True
        assert matrix["e1"]["s2"] is True
