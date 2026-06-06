"""Tests for Sophia paradigm compiler."""

import pytest
from protocols_layer.sophia.compiler import compile_paradigm_sync, recompile_from_dict


class TestCompileParadigmSync:
    def test_comparative(self):
        prog = compile_paradigm_sync("Compare Python vs Go")
        op_names = [o.value for o in prog.operations]
        assert "compare" in op_names

    def test_problem_solving(self):
        prog = compile_paradigm_sync("Why does PostgreSQL deadlock?")
        op_names = [o.value for o in prog.operations]
        assert "hypothesize" in op_names
        assert "eliminate" in op_names

    def test_survey(self):
        prog = compile_paradigm_sync("Survey AI agents 2026")
        op_names = [o.value for o in prog.operations]
        assert "synthesize" in op_names

    def test_default(self):
        prog = compile_paradigm_sync("How does deep learning work?")
        ops = [o.value for o in prog.operations]
        assert "decompose" in ops
        assert "search" in ops
        assert "verify" in ops
        assert "conclude" in ops

    def test_empty_query_raises(self):
        with pytest.raises(ValueError):
            compile_paradigm_sync("")
        with pytest.raises(ValueError):
            compile_paradigm_sync("   ")

    def test_program_is_valid(self):
        prog = compile_paradigm_sync("Compare Rust vs Go")
        issues = prog.validate()
        assert issues == []


class TestTemplatePattern:
    def test_survey_pattern(self):
        from protocols_layer.sophia.compiler import compile_paradigm_sync

        prog = compile_paradigm_sync("Survey of ML techniques 2026")
        ops = [o.value for o in prog.operations]
        assert "synthesize" in ops

    def test_problem_pattern_debug(self):
        from protocols_layer.sophia.compiler import compile_paradigm_sync

        prog = compile_paradigm_sync("Why does my API timeout?")
        ops = [o.value for o in prog.operations]
        assert "hypothesize" in ops
        assert "eliminate" in ops

    def test_comparative_vs(self):
        from protocols_layer.sophia.compiler import compile_paradigm_sync

        prog = compile_paradigm_sync("Python versus Java performance")
        ops = [o.value for o in prog.operations]
        assert "compare" in ops

    def test_versus_keyword(self):
        from protocols_layer.sophia.compiler import compile_paradigm_sync

        prog = compile_paradigm_sync("difference between SQL and NoSQL")
        ops = [o.value for o in prog.operations]
        assert "compare" in ops

    def test_llm_fallback_manual_ops(self):
        from protocols_layer.sophia.compiler import _default_ops

        ops = _default_ops("How does gravity work?")
        op_vals = [o.value for o in ops]
        assert "decompose" in op_vals
        assert "search" in op_vals
        assert "verify" in op_vals
        assert "conclude" in op_vals


class TestRecompileFromDict:
    def test_with_query(self):
        prog = compile_paradigm_sync("Compare A vs B")
        d = prog.to_dict(include_query="Compare A vs B")
        prog2 = recompile_from_dict(d)
        assert prog2.name == prog.name
        assert len(prog2.operations) == len(prog.operations)

    def test_without_query(self):
        prog = compile_paradigm_sync("Test query")
        d = prog.to_dict()
        prog2 = recompile_from_dict(d)
        assert prog2.name == "Adaptive Research"

    def test_recompile_empty_dict(self):
        prog = recompile_from_dict({"name": "empty"})
        assert prog.name == "empty"
        assert prog.operations == []

    def test_recompile_no_query_no_ops(self):
        prog = recompile_from_dict({"name": "test"})
        assert len(prog.operations) == 0


class TestMatchingTransitions:
    def test_matching_ops_filter(self):
        from protocols_layer.sophia.compiler import _matching_transitions
        from protocols_layer.sophia.symbols import AtomicOp

        ops = [AtomicOp.DECOMPOSE]
        matches = _matching_transitions(ops)
        assert len(matches) >= 1
        for t in matches:
            assert t.operation in ops
