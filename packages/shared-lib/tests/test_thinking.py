"""Tests for kairon_lib.thinking — ThinkingPath library."""

import pytest
from kairon_lib.thinking import (
    ReasoningMode,
    ThinkingMode,
    ThinkingPath,
    ThinkingPathLibrary,
    ThinkingStep,
    adversarial_review_path,
    constraint_first_path,
    creative_divergence_path,
    first_principles_path,
    multi_perspective_path,
    retrospective_extraction_path,
    scientific_validation_path,
)


class TestThinkingMode:
    """Tests for the ThinkingMode enum."""

    def test_all_17_modes_exist(self):
        assert len(ThinkingMode) == 17

    def test_path_level_modes(self):
        assert ThinkingMode.COUNCIL == "council"
        assert ThinkingMode.RED_TEAM == "red_team"
        assert ThinkingMode.SOCRATIC == "socratic"
        assert ThinkingMode.DELPHI == "delphi"
        assert ThinkingMode.DESIGN_THINKING == "design_thinking"
        assert ThinkingMode.SYSTEMS_THINKING == "systems_thinking"

    def test_step_level_modes(self):
        assert ThinkingMode.OBSERVE == "observe"
        assert ThinkingMode.FIRST_PRINCIPLES == "first_principles"
        assert ThinkingMode.ASSUMPTION_AUDIT == "assumption_audit"
        assert ThinkingMode.DEVILS_ADVOCATE == "devils_advocate"
        assert ThinkingMode.CONSTRAINT_MAPPING == "constraint_mapping"
        assert ThinkingMode.RISK_DECOMPOSITION == "risk_decomposition"
        assert ThinkingMode.DIVERGE == "diverge"
        assert ThinkingMode.CONVERGE == "converge"
        assert ThinkingMode.SYNTHESIS == "synthesis"
        assert ThinkingMode.VALIDATE == "validate"
        assert ThinkingMode.RETROSPECT == "retrospect"

    def test_reasoning_mode_is_alias(self):
        assert ReasoningMode is ThinkingMode
        assert ReasoningMode.OBSERVE == ThinkingMode.OBSERVE

    def test_str_enum_values(self):
        assert isinstance(ThinkingMode.OBSERVE, str)
        assert ThinkingMode.OBSERVE == "observe"


class TestThinkingStep:
    """Tests for ThinkingStep dataclass."""

    def test_default_values(self):
        step = ThinkingStep(ThinkingMode.OBSERVE, "test prompt")
        assert step.mode == ThinkingMode.OBSERVE
        assert step.prompt == "test prompt"
        assert step.output_format == "free"
        assert step.required is True
        assert step.min_depth == 1
        assert step.step_id == ""
        assert step.perspective == ""

    def test_positional_construction(self):
        step = ThinkingStep(ThinkingMode.VALIDATE, "Validate this")
        assert step.mode == ThinkingMode.VALIDATE
        assert step.prompt == "Validate this"

    def test_named_construction(self):
        step = ThinkingStep(
            ThinkingMode.OBSERVE,
            "Observe this",
            step_id="fp-1",
            perspective="architect",
        )
        assert step.step_id == "fp-1"
        assert step.perspective == "architect"

    def test_render_prompt_free(self):
        step = ThinkingStep(ThinkingMode.OBSERVE, "What do you see?")
        rendered = step.render_prompt()
        assert "[OBSERVE]" in rendered
        assert "What do you see?" in rendered

    def test_render_prompt_with_context(self):
        step = ThinkingStep(ThinkingMode.OBSERVE, "Analyze this")
        rendered = step.render_prompt("Previous analysis complete")
        assert "Context: Previous analysis complete" in rendered
        assert "[OBSERVE]" in rendered

    def test_render_prompt_bullet_list(self):
        step = ThinkingStep(ThinkingMode.OBSERVE, "List items", "bullet_list")
        rendered = step.render_prompt()
        assert "bullet list" in rendered.lower()

    def test_render_prompt_scored_options(self):
        step = ThinkingStep(ThinkingMode.DIVERGE, "Generate options", "scored_options")
        rendered = step.render_prompt()
        assert "scored 1-10" in rendered

    def test_render_prompt_decision(self):
        step = ThinkingStep(ThinkingMode.SYNTHESIS, "Decide", "decision")
        rendered = step.render_prompt()
        assert "DECISION" in rendered


class TestThinkingPath:
    """Tests for ThinkingPath dataclass."""

    def test_empty_path_defaults(self):
        path = ThinkingPath(name="Test", description="A test path")
        assert path.name == "Test"
        assert path.description == "A test path"
        assert path.best_for == []
        assert path.steps == []
        assert path.mode is None
        assert path.avoid_when == []
        assert path.typical_duration_min == 30

    def test_step_names(self):
        path = ThinkingPath(
            name="Test",
            description="Test",
            steps=[
                ThinkingStep(ThinkingMode.OBSERVE, "Step 1"),
                ThinkingStep(ThinkingMode.SYNTHESIS, "Step 2"),
                ThinkingStep(ThinkingMode.VALIDATE, "Step 3"),
            ],
        )
        assert path.step_names() == ["observe", "synthesis", "validate"]

    def test_required_steps(self):
        path = ThinkingPath(
            name="Test",
            description="Test",
            steps=[
                ThinkingStep(ThinkingMode.OBSERVE, "Required"),
                ThinkingStep(ThinkingMode.SYNTHESIS, "Optional", required=False),
            ],
        )
        required = path.required_steps()
        assert len(required) == 1
        assert required[0].prompt == "Required"

    def test_render_full_prompt(self):
        path = ThinkingPath(
            name="Test Path",
            description="Test description",
            steps=[
                ThinkingStep(ThinkingMode.OBSERVE, "Observe the situation."),
                ThinkingStep(ThinkingMode.SYNTHESIS, "Synthesize findings."),
            ],
        )
        rendered = path.render_full_prompt("Some context")
        assert "# Test Path" in rendered
        assert "_Test description_" in rendered
        assert "## Step 1: Observe" in rendered
        assert "## Step 2: Synthesis" in rendered
        assert "Context: Some context" in rendered

    def test_to_dict(self):
        path = ThinkingPath(
            name="Test",
            description="Desc",
            best_for=["testing"],
            steps=[ThinkingStep(ThinkingMode.OBSERVE, "Observe")],
        )
        d = path.to_dict()
        assert d["name"] == "Test"
        assert d["description"] == "Desc"
        assert d["best_for"] == ["testing"]
        assert len(d["steps"]) == 1
        assert d["steps"][0]["mode"] == "observe"

    def test_get_step(self):
        path = ThinkingPath(
            name="Test",
            description="Test",
            steps=[
                ThinkingStep(ThinkingMode.OBSERVE, "Step A", step_id="a"),
                ThinkingStep(ThinkingMode.SYNTHESIS, "Step B", step_id="b"),
            ],
        )
        assert path.get_step("a") is not None
        assert path.get_step("a").prompt == "Step A"  # type: ignore[union-attr]
        assert path.get_step("non-existent") is None

    def test_summary(self):
        path = ThinkingPath(
            name="My Path",
            description="A very long description that exceeds sixty characters easily",
            steps=[ThinkingStep(ThinkingMode.OBSERVE, "S1"), ThinkingStep(ThinkingMode.SYNTHESIS, "S2")],
        )
        summary = path.summary()
        assert "My Path" in summary
        assert "2 steps" in summary


class TestFactoryFunctions:
    """Tests for the 7 factory functions."""

    def test_all_factories_return_thinking_path(self):
        factories = [
            first_principles_path,
            adversarial_review_path,
            constraint_first_path,
            multi_perspective_path,
            scientific_validation_path,
            retrospective_extraction_path,
            creative_divergence_path,
        ]
        for fn in factories:
            path = fn()
            assert isinstance(path, ThinkingPath)
            assert path.name
            assert path.description
            assert len(path.steps) > 0

    def test_first_principles_path(self):
        path = first_principles_path()
        assert path.name == "First Principles"
        assert path.mode == ThinkingMode.FIRST_PRINCIPLES
        assert len(path.steps) == 4
        assert path.steps[0].mode == ThinkingMode.OBSERVE
        assert path.steps[-1].mode == ThinkingMode.SYNTHESIS

    def test_adversarial_review_path(self):
        path = adversarial_review_path()
        assert path.name == "Adversarial Review"
        assert path.mode == ThinkingMode.RED_TEAM
        assert len(path.steps) == 5

    def test_constraint_first_path(self):
        path = constraint_first_path()
        assert path.name == "Constraint First"
        assert path.mode == ThinkingMode.CONSTRAINT_MAPPING

    def test_multi_perspective_path(self):
        path = multi_perspective_path()
        assert path.mode == ThinkingMode.COUNCIL

    def test_scientific_validation_path(self):
        path = scientific_validation_path()
        assert path.mode == ThinkingMode.DELPHI

    def test_retrospective_extraction_path(self):
        path = retrospective_extraction_path()
        assert path.mode == ThinkingMode.RETROSPECT

    def test_creative_divergence_path(self):
        path = creative_divergence_path()
        assert path.mode == ThinkingMode.DIVERGE
        # Should have many steps for creative ideation
        assert len(path.steps) >= 5


class TestThinkingPathLibrary:
    """Tests for ThinkingPathLibrary."""

    def test_get_returns_path(self):
        path = ThinkingPathLibrary.get("First Principles")
        assert path.name == "First Principles"
        assert len(path.steps) == 4

    def test_get_raises_keyerror(self):
        with pytest.raises(KeyError):
            ThinkingPathLibrary.get("Non-existent Path")

    def test_all_paths(self):
        paths = ThinkingPathLibrary.all_paths()
        assert len(paths) == 7

    def test_names(self):
        names = ThinkingPathLibrary.names()
        assert "First Principles" in names
        assert "Adversarial Review" in names
        assert len(names) == 7

    def test_register_custom_path(self):
        custom = ThinkingPath(name="Custom", description="Custom path")
        ThinkingPathLibrary.register(custom)
        assert ThinkingPathLibrary.get("Custom") == custom

    def test_for_context(self):
        results = ThinkingPathLibrary.for_context("security")
        assert len(results) >= 1
        names = {p.name for p in results}
        assert "Adversarial Review" in names

    def test_for_context_case_insensitive(self):
        results = ThinkingPathLibrary.for_context("BRAINSTORMING")
        names = {p.name for p in results}
        assert "Creative Divergence" in names

    def test_recommend_architecture(self):
        path = ThinkingPathLibrary.recommend("architecture")
        assert path.name == "Council of Perspectives"

    def test_recommend_root_cause(self):
        path = ThinkingPathLibrary.recommend("root_cause")
        assert path.name == "Socratic Method"

    def test_recommend_security(self):
        path = ThinkingPathLibrary.recommend("security")
        assert path.name == "Red Team Challenge"

    def test_recommend_unknown_falls_back_to_council(self):
        path = ThinkingPathLibrary.recommend("unknown_type")
        assert path.name == "Council of Perspectives"

    def test_from_mode_valid(self):
        path = ThinkingPathLibrary.from_mode("first_principles")
        assert path is not None
        assert path.name == "First Principles Analysis"

    def test_from_mode_invalid(self):
        path = ThinkingPathLibrary.from_mode("non_existent")
        assert path is None

    def test_from_name(self):
        path = ThinkingPathLibrary.from_name("First Principles")
        assert path is not None

    def test_from_name_missing_returns_none(self):
        path = ThinkingPathLibrary.from_name("Not Real")
        assert path is None

    # ── Nucleus-style constructor tests ──────────────────────────

    def test_nucleus_first_principles(self):
        path = ThinkingPathLibrary.first_principles()
        assert path.name == "First Principles Analysis"
        assert path.mode == ThinkingMode.FIRST_PRINCIPLES
        assert len(path.steps) == 5
        assert path.typical_duration_min == 45
        assert "time pressure" in path.avoid_when[0]

    def test_nucleus_council(self):
        path = ThinkingPathLibrary.council()
        assert path.name == "Council of Perspectives"
        assert path.mode == ThinkingMode.COUNCIL
        assert len(path.steps) == 6
        # Check perspectives
        perspectives = [s.perspective for s in path.steps if s.perspective]
        assert "architect" in perspectives
        assert "product_manager" in perspectives
        assert "user" in perspectives
        assert "risk_manager" in perspectives
        assert "innovator" in perspectives
        assert "synthesizer" in perspectives

    def test_nucleus_red_team(self):
        path = ThinkingPathLibrary.red_team()
        assert path.name == "Red Team Challenge"
        assert path.mode == ThinkingMode.RED_TEAM
        assert len(path.steps) == 6

    def test_nucleus_socratic(self):
        path = ThinkingPathLibrary.socratic()
        assert path.name == "Socratic Method"
        assert path.mode == ThinkingMode.SOCRATIC
        assert len(path.steps) == 6

    def test_nucleus_delphi(self):
        path = ThinkingPathLibrary.delphi()
        assert path.name == "Delphi Consensus"
        assert path.mode == ThinkingMode.DELPHI
        assert len(path.steps) == 6

    def test_nucleus_synthesis(self):
        path = ThinkingPathLibrary.synthesis()
        assert path.name == "Synthesis Integration"
        assert path.mode == ThinkingMode.SYNTHESIS
        assert len(path.steps) == 6

    def test_nucleus_systems_thinking(self):
        path = ThinkingPathLibrary.systems_thinking()
        assert path.name == "Systems Thinking"
        assert path.mode == ThinkingMode.SYSTEMS_THINKING
        assert len(path.steps) == 6

    def test_all_nucleus_paths_have_step_ids(self):
        methods = [
            ThinkingPathLibrary.first_principles,
            ThinkingPathLibrary.council,
            ThinkingPathLibrary.red_team,
            ThinkingPathLibrary.socratic,
            ThinkingPathLibrary.delphi,
            ThinkingPathLibrary.synthesis,
            ThinkingPathLibrary.systems_thinking,
        ]
        for method in methods:
            path = method()
            for step in path.steps:
                assert step.step_id, f"{path.name}: all steps must have step_id"

    def test_library_coherence(self):
        """All nucleus paths should have non-empty best_for and avoid_when."""
        methods = [
            ThinkingPathLibrary.first_principles,
            ThinkingPathLibrary.council,
            ThinkingPathLibrary.red_team,
            ThinkingPathLibrary.socratic,
            ThinkingPathLibrary.delphi,
            ThinkingPathLibrary.synthesis,
            ThinkingPathLibrary.systems_thinking,
        ]
        for method in methods:
            path = method()
            assert len(path.best_for) > 0, f"{path.name}: best_for is empty"
            assert path.typical_duration_min >= 30, f"{path.name}: duration too short"
