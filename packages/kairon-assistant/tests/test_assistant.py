"""Tests for kairon_assistant package."""

from kairon_assistant.command_parser import CommandParser
from kairon_assistant.context_manager import ContextManager
from kairon_assistant.session_manager import SessionManager
from kairon_assistant.types import CommandType


class TestCommandType:
    """Tests for CommandType enum."""

    def test_all_members_exist(self):
        """Verify all expected command types are defined."""
        assert hasattr(CommandType, "QUERY")
        assert hasattr(CommandType, "ACTION")
        assert hasattr(CommandType, "CONFIG")
        assert hasattr(CommandType, "STATUS")
        assert hasattr(CommandType, "HELP")
        assert hasattr(CommandType, "GREETING")
        assert hasattr(CommandType, "UNKNOWN")

    def test_values_are_unique(self):
        """Verify all command types have unique values."""
        values = [member.value for member in CommandType]
        assert len(values) == len(set(values))


class TestCommandParser:
    """Tests for CommandParser."""

    def test_parse_greeting(self):
        """Parse a simple greeting."""
        parser = CommandParser()
        result = parser.parse("hello")
        assert result.command_type == CommandType.GREETING
        assert result.intent == "greeting"
        assert result.confidence > 0.5

    def test_parse_query(self):
        """Parse an information query."""
        parser = CommandParser()
        result = parser.parse("show me the weather")
        assert result.command_type == CommandType.QUERY
        assert result.intent == "information_retrieval"
        assert result.confidence > 0.5

    def test_parse_unknown(self):
        """Parse unrecognized input."""
        parser = CommandParser()
        result = parser.parse("xyzzy blarg florb")
        assert result.command_type == CommandType.UNKNOWN

    def test_parse_action_with_entities(self):
        """Parse an action command with entity extraction."""
        parser = CommandParser()
        result = parser.parse("start the D_Intelligence organ")
        assert result.command_type == CommandType.ACTION
        assert "action" in result.parameters
        assert result.parameters["action"] == "start"
        assert "target" in result.parameters

    def test_add_custom_pattern(self):
        """Add and use a custom pattern."""
        parser = CommandParser()
        parser.add_pattern(CommandType.ACTION, "deploy", 0.95)
        result = parser.parse("deploy the application")
        assert result.command_type == CommandType.ACTION

    def test_parse_help(self):
        """Parse a help request."""
        parser = CommandParser()
        result = parser.parse("help")
        assert result.command_type == CommandType.HELP
        assert result.confidence > 0.5


class TestContextManager:
    """Tests for ContextManager."""

    def test_get_context_creates_new(self):
        """Getting context for unknown session creates new one."""
        cm = ContextManager()
        ctx = cm.get_context("sess-1")
        assert ctx is not None
        assert ctx.session_id == "sess-1"
        assert ctx.turn_count == 0

    def test_add_turn_and_get_context(self):
        """Add a turn and retrieve context."""
        cm = ContextManager()
        cm.add_turn("sess-1", "hello", "Hi there!", command_type=CommandType.GREETING)
        ctx = cm.get_context("sess-1")
        assert ctx.turn_count == 1
        assert ctx.last_command_type == CommandType.GREETING

    def test_clear_context(self):
        """Clear a context."""
        cm = ContextManager()
        cm.add_turn("sess-1", "hello", "Hi!")
        cm.clear_context("sess-1")
        ctx = cm.get_context("sess-1")
        assert ctx.turn_count == 0  # New context created

    def test_export_import_roundtrip(self):
        """Export and import context preserves data."""
        cm = ContextManager()
        cm.add_turn("sess-1", "hello", "Hi!", command_type=CommandType.GREETING)
        data = cm.export_context("sess-1")
        assert data is not None
        assert data["session_id"] == "sess-1"

        cm2 = ContextManager()
        imported = cm2.import_context(data)
        assert imported.session_id == "sess-1"
        assert imported.turn_count == 1

    def test_to_prompt_context(self):
        """Convert context to prompt format."""
        ctx = cm = ContextManager()
        cm.add_turn("sess-1", "what is the status?", "It is running.", command_type=CommandType.STATUS)
        cm.add_turn("sess-1", "thank you", "You're welcome!", command_type=CommandType.GREETING)
        ctx = cm.get_context("sess-1")
        prompt = ctx.to_prompt_context()
        assert "User: what is the status?" in prompt
        assert "Assistant: It is running." in prompt


class TestSessionManager:
    """Tests for SessionManager."""

    def test_create_session(self):
        """Create a new session."""
        sm = SessionManager()
        session = sm.get_or_create_session(user_id="user-1")
        assert session.session_id.startswith("sess-")
        assert session.user_id == "user-1"
        assert session.active is True

    def test_get_existing_session(self):
        """Get an existing session by ID."""
        sm = SessionManager()
        sess1 = sm.get_or_create_session(user_id="user-1")
        sess2 = sm.get_or_create_session(session_id=sess1.session_id)
        assert sess2.session_id == sess1.session_id

    def test_end_session(self):
        """End a session."""
        sm = SessionManager()
        session = sm.get_or_create_session()
        session_id = session.session_id
        assert sm.end_session(session_id) is True
        assert sm.get_session(session_id) is None

    def test_get_stats(self):
        """Get session manager statistics."""
        sm = SessionManager()
        sm.get_or_create_session(user_id="user-1")
        sm.get_or_create_session(user_id="user-2")
        stats = sm.get_stats()
        assert stats["active_sessions"] == 2
        assert stats["unique_users"] == 2

    def test_increment_command_count(self):
        """Increment command count for a session."""
        sm = SessionManager()
        session = sm.get_or_create_session()
        sm.increment_command_count(session.session_id)
        sm.increment_command_count(session.session_id)
        sess = sm.get_session(session.session_id)
        assert sess.command_count == 2

    def test_export_import_roundtrip(self):
        """Export and import session preserves data."""
        sm = SessionManager()
        session = sm.get_or_create_session(user_id="user-1")
        sm.increment_command_count(session.session_id)
        data = sm.export_session(session.session_id)
        assert data is not None
        assert data["session_id"] == session.session_id

        sm2 = SessionManager()
        imported = sm2.import_session(data)
        assert imported.user_id == "user-1"
        assert imported.command_count == 1
