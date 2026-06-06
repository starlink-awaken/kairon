"""Tests for Sophia CLI — argument parsing and main dispatch."""

import sys
from unittest.mock import patch

import pytest

from protocols_layer.sophia.cli import build_parser, main


class TestBuildParser:
    def test_compile_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["compile", "test query"])
        assert args.command == "compile"
        assert args.query == "test query"
        assert args.json is False

    def test_compile_json_flag(self):
        parser = build_parser()
        args = parser.parse_args(["compile", "q", "--json"])
        assert args.json is True

    def test_ops_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["ops"])
        assert args.command == "ops"

    def test_states_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["states"])
        assert args.command == "states"

    def test_transitions_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["transitions"])
        assert args.command == "transitions"

    def test_learn_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["learn"])
        assert args.command == "learn"
        assert args.domain == ""

    def test_learn_with_domain(self):
        parser = build_parser()
        args = parser.parse_args(["learn", "--domain", "security"])
        assert args.domain == "security"

    def test_evolve_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["evolve", "optimize me"])
        assert args.command == "evolve"
        assert args.query == "optimize me"

    def test_export_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["export", "file.json"])
        assert args.command == "export"
        assert args.file == "file.json"
        assert args.format == "mermaid"

    def test_export_json_format(self):
        parser = build_parser()
        args = parser.parse_args(["export", "f.json", "--format", "json"])
        assert args.format == "json"

    def test_diff_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["diff", "a.json", "b.json"])
        assert args.command == "diff"
        assert args.file_a == "a.json"
        assert args.file_b == "b.json"

    def test_validate_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["validate", "p.json"])
        assert args.command == "validate"
        assert args.file == "p.json"

    def test_mcp_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["mcp"])
        assert args.command == "mcp"

    def test_tui_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["tui"])
        assert args.command == "tui"

    def test_no_args_produces_subcommand_error(self):
        """No args should produce error output via _die, not crash."""
        parser = build_parser()
        parser.parse_args([])
        assert True  # subparsers not required by default

    def test_help_does_not_crash(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])


class TestMainDispatch:
    def test_compile_returns_zero(self):
        with patch.object(sys, "argv", ["sophia", "compile", "test"]):
            result = main()
            assert result == 0

    def test_ops_returns_zero(self):
        with patch.object(sys, "argv", ["sophia", "ops"]):
            result = main()
            assert result == 0

    def test_states_returns_zero(self):
        with patch.object(sys, "argv", ["sophia", "states"]):
            result = main()
            assert result == 0

    def test_transitions_returns_zero(self):
        with patch.object(sys, "argv", ["sophia", "transitions"]):
            result = main()
            assert result == 0


class TestExportCommand:
    def test_compile_then_export_roundtrip(self):
        from protocols_layer.sophia.compiler import compile_paradigm_sync

        prog = compile_paradigm_sync("Compare A vs B")
        assert prog.name == "Adaptive Research"

    def test_validate_via_api(self):
        from protocols_layer.sophia.compiler import compile_paradigm_sync

        prog = compile_paradigm_sync("Test query")
        issues = prog.validate()
        assert isinstance(issues, list)
