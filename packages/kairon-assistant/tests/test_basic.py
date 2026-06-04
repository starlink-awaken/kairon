"""Basic tests for kairon-assistant package."""

from __future__ import annotations

from kairon_assistant import (
    AssistantSession,
    CommandParser,
    CommandType,
    ContextManager,
    ConversationContext,
    ConversationTurn,
    ParsedCommand,
    SessionManager,
)


class TestKaironAssistantBasic:
    """Core functionality and edge case tests."""

    def test_import(self):
        """All expected exports are importable."""
        assert AssistantSession is not None
        assert CommandParser is not None
        assert CommandType is not None
        assert ContextManager is not None
        assert ConversationContext is not None
        assert ConversationTurn is not None
        assert ParsedCommand is not None
        assert SessionManager is not None

    def test_command_type_enum_values(self):
        """CommandType enum has expected members."""
        assert isinstance(CommandType.QUERY, CommandType)
        assert isinstance(CommandType.ACTION, CommandType)
        assert isinstance(CommandType.UNKNOWN, CommandType)

    def test_parser_empty_string(self):
        """Parsing an empty string returns UNKNOWN."""
        parser = CommandParser()
        result = parser.parse("")
        assert result.command_type == CommandType.UNKNOWN

    def test_parser_whitespace_only(self):
        """Parsing whitespace returns UNKNOWN."""
        parser = CommandParser()
        result = parser.parse("   ")
        assert result.command_type == CommandType.UNKNOWN

    def test_session_manager_empty_stats(self):
        """SessionManager with no sessions returns zero stats."""
        sm = SessionManager()
        stats = sm.get_stats()
        assert stats["active_sessions"] == 0
        assert stats["unique_users"] == 0
        assert stats["avg_commands_per_session"] == 0

    def test_context_manager_get_unknown_session(self):
        """Getting context for unknown session creates new one with empty state."""
        cm = ContextManager()
        ctx = cm.get_context("unknown-session")
        assert ctx.session_id == "unknown-session"
        assert ctx.turn_count == 0
        assert ctx.last_command_type is None
