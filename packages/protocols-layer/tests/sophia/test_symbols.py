"""Tests for Sophia symbol system."""

from protocols_layer.sophia.symbols import (
    BASE_TRANSITIONS,
    AtomicOp,
    ParadigmProgram,
    ResearchState,
    gate_always,
    gate_has_contradictions,
    gate_has_entities,
    gate_has_sources,
    gate_quality_pass,
)


class TestAtomicOp:
    def test_from_string_lowercase(self):
        assert AtomicOp.from_string("decompose") == AtomicOp.DECOMPOSE
        assert AtomicOp.from_string("search") == AtomicOp.SEARCH
        assert AtomicOp.from_string("verify") == AtomicOp.VERIFY

    def test_from_string_uppercase(self):
        assert AtomicOp.from_string("DECOMPOSE") == AtomicOp.DECOMPOSE
        assert AtomicOp.from_string("CONCLUDE") == AtomicOp.CONCLUDE

    def test_from_string_invalid(self):
        assert AtomicOp.from_string("nonexistent") is None


class TestGates:
    def test_gate_has_sources(self):
        assert gate_has_sources({"source_count": 5}) is True
        assert gate_has_sources({"source_count": 1}) is False
        assert gate_has_sources({}) is False

    def test_gate_has_entities(self):
        assert gate_has_entities({"entity_count": 1}) is True
        assert gate_has_entities({"entity_count": 0}) is False

    def test_gate_quality_pass(self):
        assert gate_quality_pass({"quality_score": 80}) is True
        assert gate_quality_pass({"quality_score": 40}) is False

    def test_gate_always(self):
        assert gate_always({}) is True


class TestParadigmProgram:
    def test_validate_empty(self):
        p = ParadigmProgram(name="empty")
        issues = p.validate()
        assert len(issues) >= 2

    def test_validate_valid(self):
        ops = [AtomicOp.DECOMPOSE, AtomicOp.SEARCH, AtomicOp.VERIFY]
        transitions = [t for t in BASE_TRANSITIONS if t.operation in ops]
        p = ParadigmProgram(name="test", operations=ops, transitions=transitions)
        assert p.validate() == []

    def test_to_dict(self):
        ops = [AtomicOp.DECOMPOSE, AtomicOp.SEARCH]
        p = ParadigmProgram(name="test", operations=ops)
        d = p.to_dict(include_query="test query")
        assert d["name"] == "test"
        assert "test query" in d["query"]
        assert len(d["ops"]) == 2

    def test_from_dict(self):
        d = {"name": "test", "ops": ["decompose", "search"]}
        p = ParadigmProgram.from_dict(d)
        assert p.name == "test"
        assert len(p.operations) == 2

    def test_to_mermaid(self):
        ops = [AtomicOp.DECOMPOSE, AtomicOp.SEARCH]
        transitions = [t for t in BASE_TRANSITIONS if t.operation in ops]
        p = ParadigmProgram(name="test", operations=ops, transitions=transitions)
        m = p.to_mermaid()
        assert m.startswith("stateDiagram-v2")
        assert "decompose" in m

    def test_diff(self):
        ops = [AtomicOp.DECOMPOSE, AtomicOp.CONCLUDE]
        p1 = ParadigmProgram(name="a", operations=ops, transitions=[])
        p2 = ParadigmProgram(name="b", operations=[AtomicOp.DECOMPOSE, AtomicOp.SEARCH], transitions=[])
        delta = p1.diff(p2)
        assert delta["added_ops"] == ["search"]
        assert delta["removed_ops"] == ["conclude"]
        assert delta["common_ops"] == ["decompose"]


class TestGatesExtended:
    def test_gate_always_true(self):
        assert gate_always(None) is True
        assert gate_always({}) is True

    def test_gate_has_sources_boundary(self):
        assert gate_has_sources({"source_count": 2}) is True
        assert gate_has_sources({"source_count": 3}) is True
        assert gate_has_sources({"source_count": 1}) is False

    def test_gate_quality_pass_boundary(self):
        assert gate_quality_pass({"quality_score": 60}) is True
        assert gate_quality_pass({"quality_score": 59}) is False

    def test_gate_has_contradictions(self):
        assert gate_has_contradictions({"contradiction_count": 1}) is True
        assert gate_has_contradictions({"contradiction_count": 0}) is False


class TestResearchState:
    def test_all_states_have_meaningful_names(self):
        for state in ResearchState:
            assert len(state.value) > 0

    def test_state_count(self):
        assert len(list(ResearchState)) == 12


class TestAtomicOpExtended:
    def test_from_string_edge_cases(self):
        assert AtomicOp.from_string("DECOMPOSE") == AtomicOp.DECOMPOSE
        assert AtomicOp.from_string("SEARCH") == AtomicOp.SEARCH
        assert AtomicOp.from_string("") is None
        assert AtomicOp.from_string("  ") is None

    def test_all_ops_recognizable(self):
        values = [m.value for m in AtomicOp]
        assert len(values) == len(set(values)), "Duplicate operation values"

    def test_from_string_mixed_case(self):
        assert AtomicOp.from_string("VeRiFy") == AtomicOp.VERIFY


class TestTransitionRule:
    def test_rule_has_description(self):
        for t in BASE_TRANSITIONS:
            assert len(t.description) > 0, f"Missing description for {t.operation}"

    def test_all_rules_end_at_valid_state(self):
        valid_states = set(ResearchState)
        for t in BASE_TRANSITIONS:
            assert t.to_state in valid_states, f"Invalid to_state: {t.to_state}"
            assert t.from_state in valid_states, f"Invalid from_state: {t.from_state}"
            assert t.on_fail in valid_states, f"Invalid on_fail: {t.on_fail}"


class TestParadigmProgramExtended:
    def test_state_count_empty(self):
        from protocols_layer.sophia.symbols import ParadigmProgram

        p = ParadigmProgram(name="empty")
        assert p.state_count == 0

    def test_state_count_with_transitions(self):
        p = ParadigmProgram(
            name="test",
            operations=[AtomicOp.DECOMPOSE, AtomicOp.SEARCH],
            transitions=[t for t in BASE_TRANSITIONS if t.operation in (AtomicOp.DECOMPOSE, AtomicOp.SEARCH)],
        )
        assert p.state_count >= 1

    def test_validate_ops_without_transitions(self):
        ops = [AtomicOp.SYNTHESIZE]
        p = ParadigmProgram(name="incomplete", operations=ops, transitions=[])
        issues = p.validate()
        assert len(issues) >= 2

    def test_to_dict_without_query(self):
        p = ParadigmProgram(name="no-query", operations=[AtomicOp.DECOMPOSE])
        d = p.to_dict()
        assert "query" not in d

    def test_to_dict_all_fields(self):
        p = ParadigmProgram(
            name="full",
            description="full test",
            operations=[AtomicOp.DECOMPOSE, AtomicOp.CONCLUDE],
            transitions=[t for t in BASE_TRANSITIONS if t.operation in (AtomicOp.DECOMPOSE,)],
            max_iterations=5,
        )
        d = p.to_dict(include_query="test query")
        assert d["name"] == "full"
        assert d["description"] == "full test"
        assert d["max_iterations"] == 5
        assert d["transition_count"] >= 1
        assert d["state_count"] >= 1

    def test_from_dict_preserves_ops(self):
        d = {"name": "test", "ops": ["decompose", "search", "verify", "conclude"]}
        p = ParadigmProgram.from_dict(d)
        assert len(p.operations) == 4

    def test_from_dict_skips_invalid_ops(self):
        d = {"name": "test", "ops": ["decompose", "nonexistent_op", "verify"]}
        p = ParadigmProgram.from_dict(d)
        assert len(p.operations) == 2

    def test_to_mermaid_without_transitions(self):
        p = ParadigmProgram(name="empty")
        m = p.to_mermaid()
        assert m.startswith("stateDiagram-v2")

    def test_to_mermaid_one_transition(self):
        t = [tr for tr in BASE_TRANSITIONS if tr.operation == AtomicOp.DECOMPOSE][:1]
        p = ParadigmProgram(name="single", operations=[AtomicOp.DECOMPOSE], transitions=t)
        m = p.to_mermaid()
        assert "question --> decomposed" in m

    def test_diff_identical(self):
        ops = [AtomicOp.DECOMPOSE]
        p1 = ParadigmProgram(name="a", operations=ops, transitions=[])
        p2 = ParadigmProgram(name="b", operations=list(ops), transitions=[])
        delta = p1.diff(p2)
        assert delta["added_ops"] == []
        assert delta["removed_ops"] == []
        assert delta["common_ops"] == ["decompose"]

    def test_diff_completely_different(self):
        p1 = ParadigmProgram(name="a", operations=[AtomicOp.DECOMPOSE], transitions=[])
        p2 = ParadigmProgram(name="b", operations=[AtomicOp.CONCLUDE], transitions=[])
        delta = p1.diff(p2)
        assert delta["added_ops"] == ["conclude"]
        assert delta["removed_ops"] == ["decompose"]


class TestBaseTransitions:
    def test_transition_count(self):
        assert len(BASE_TRANSITIONS) >= 13

    def test_all_ops_have_transitions(self):
        op_set = {t.operation for t in BASE_TRANSITIONS}
        assert AtomicOp.DECOMPOSE in op_set
        assert AtomicOp.CONCLUDE in op_set

    def test_every_operation_covered(self):
        base_ops = {
            AtomicOp.DECOMPOSE,
            AtomicOp.SEARCH,
            AtomicOp.EXTRACT,
            AtomicOp.COMPARE,
            AtomicOp.HYPOTHESIZE,
            AtomicOp.VERIFY,
            AtomicOp.SYNTHESIZE,
            AtomicOp.ELIMINATE,
            AtomicOp.ITERATE,
            AtomicOp.CONCLUDE,
        }
        covered = {t.operation for t in BASE_TRANSITIONS}
        assert (base_ops - covered) == set(), f"Uncovered operations: {base_ops - covered}"
