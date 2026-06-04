"""Extended tests: governance, recommendations, core, system handlers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ── Governance Integration ──────────────────────────────────
from kairon_assistant.governance_integration import GovernanceIntegration
from kairon_assistant.types import CommandType


class TestGovernanceIntegration:
    def test_init_default_enabled(self):
        g = GovernanceIntegration()
        assert g.enabled is True

    def test_init_disabled(self):
        g = GovernanceIntegration(enabled=False)
        assert g.enabled is False

    @pytest.mark.asyncio
    async def test_initialize(self):
        g = GovernanceIntegration()
        await g.initialize()  # should not raise

    @pytest.mark.asyncio
    async def test_shutdown(self):
        g = GovernanceIntegration()
        await g.shutdown()  # should not raise

    @pytest.mark.asyncio
    async def test_check_permission_allowed(self):
        g = GovernanceIntegration()
        result = await g.check_permission("user1", CommandType.QUERY)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_disabled(self):
        g = GovernanceIntegration(enabled=False)
        result = await g.check_permission("user1", CommandType.ACTION)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_with_parameters(self):
        g = GovernanceIntegration()
        result = await g.check_permission("user1", CommandType.CONFIG, {"key": "value"})
        assert result is True


# ── Recommendation Engine ───────────────────────────────────

from kairon_assistant.command_parser import ParsedCommand
from kairon_assistant.recommendation_engine import Recommendation, RecommendationEngine


class _MockSession:
    def __init__(self):
        self.session_id = "sess-test"
        self.command_count = 0


class _MockContext:
    def __init__(self, turn_count=0):
        self.turn_count = turn_count
        self.turns = []
        self.last_entities = {}


class TestRecommendation:
    def test_fields(self):
        r = Recommendation(text="Check status", action="status", confidence=0.9,
                           category="test", reason="Testing")
        assert r.text == "Check status"
        assert r.confidence == 0.9


class TestRecommendationEngine:
    def test_get_recommendations_no_context(self):
        eng = RecommendationEngine()
        session = _MockSession()
        recs = eng.get_recommendations(session, None)
        assert len(recs) <= 5
        assert all(isinstance(r, Recommendation) for r in recs)

    def test_get_recommendations_follow_up_status(self):
        eng = RecommendationEngine()
        session = _MockSession()
        cmd = ParsedCommand(raw_text="status", command_type=CommandType.STATUS,
                            confidence=0.9, intent="status", parameters={})
        recs = eng.get_recommendations(session, None, last_command=cmd)
        texts = [r.text for r in recs]
        assert "Check specific organ status" in texts

    def test_get_recommendations_follow_up_action_start(self):
        eng = RecommendationEngine()
        session = _MockSession()
        cmd = ParsedCommand(raw_text="start D-Execution", command_type=CommandType.ACTION,
                            confidence=0.9, intent="start", parameters={"action": "start", "target": "D-Execution"})
        recs = eng.get_recommendations(session, None, last_command=cmd)
        texts = [r.text for r in recs]
        assert any("Check D-Execution status" in t for t in texts)

    def test_get_context_recommendations_new_user(self):
        eng = RecommendationEngine()
        ctx = _MockContext(turn_count=1)
        recs = eng._get_context_recommendations(ctx)
        texts = [r.text for r in recs]
        assert "See what I can do" in texts

    def test_get_context_recommendations_long(self):
        eng = RecommendationEngine()
        ctx = _MockContext(turn_count=10)
        recs = eng._get_context_recommendations(ctx)
        texts = [r.text for r in recs]
        assert "Start a new task" in texts

    def test_get_proactive_recommendations(self):
        eng = RecommendationEngine()
        recs = eng._get_proactive_recommendations()
        assert len(recs) >= 2

    def test_record_and_get_popular(self):
        eng = RecommendationEngine()
        eng.record_command(CommandType.QUERY, "info")
        eng.record_command(CommandType.QUERY, "info")
        eng.record_command(CommandType.ACTION, "start")
        popular = eng.get_popular_commands(limit=2)
        assert len(popular) == 2
        assert popular[0][1] == 2  # "query:info" has count 2

    def test_suggest_next_action(self):
        eng = RecommendationEngine()
        recs = eng.suggest_next_action("check_status")
        assert len(recs) >= 1

    def test_get_help_suggestions_organ(self):
        eng = RecommendationEngine()
        recs = eng.get_help_suggestions("how to manage organs")
        assert any("List all organs" in r.text for r in recs)

    def test_get_help_suggestions_general(self):
        eng = RecommendationEngine()
        recs = eng.get_help_suggestions("help")
        assert any("Get system status" in r.text for r in recs)


# ── Core ────────────────────────────────────────────────────

from kairon_assistant.core import AssistantConfig, AssistantResponse, SmartAssistant


class TestAssistantConfig:
    def test_defaults(self):
        cfg = AssistantConfig()
        assert cfg.max_context_turns == 10
        assert cfg.enable_recommendations is True
        assert cfg.response_timeout_seconds == 30.0
        assert cfg.governance_check is True

    def test_custom(self):
        cfg = AssistantConfig(max_context_turns=5, enable_recommendations=False)
        assert cfg.max_context_turns == 5
        assert cfg.enable_recommendations is False


class TestAssistantResponse:
    def test_defaults(self):
        r = AssistantResponse(response_text="hello")
        assert r.response_text == "hello"
        assert r.action_taken is False
        assert r.suggestions == []

    def test_with_action(self):
        r = AssistantResponse(response_text="done", action_taken=True, action_result={"status": "ok"})
        assert r.action_taken is True
        assert r.action_result["status"] == "ok"


class TestSmartAssistant:
    def test_init_defaults(self):
        sa = SmartAssistant()
        assert sa.config.enable_recommendations is True
        assert sa._running is False

    def test_get_stats(self):
        sa = SmartAssistant()
        stats = sa.get_stats()
        assert "sessions_active" in stats
        assert "command_handlers" in stats

    @pytest.mark.asyncio
    async def test_initialize_and_shutdown(self):
        sa = SmartAssistant()
        await sa.initialize()
        assert sa._running is True
        await sa.shutdown()
        assert sa._running is False

    def test_register_command_handler(self):
        sa = SmartAssistant()
        handler = MagicMock()
        sa.register_command_handler(CommandType.QUERY, handler)
        assert CommandType.QUERY in sa._command_handlers

    @pytest.mark.asyncio
    async def test_process_message_greeting(self):
        sa = SmartAssistant()
        await sa.initialize()
        resp = await sa.process_message("hello")
        assert resp.confidence > 0
        assert len(resp.response_text) > 0

    def test_handle_greeting(self):
        sa = SmartAssistant()
        cmd = ParsedCommand(raw_text="hello", command_type=CommandType.GREETING,
                            confidence=1.0, intent="greeting", parameters={})
        session = MagicMock()
        conv = MagicMock()
        resp = sa._handle_greeting(cmd, session, conv, sa)
        assert resp.confidence == 1.0

    def test_handle_unknown(self):
        sa = SmartAssistant()
        cmd = ParsedCommand(raw_text="xyzzy", command_type=CommandType.UNKNOWN,
                            confidence=0.3, intent="unknown", parameters={})
        session = MagicMock()
        conv = MagicMock()
        resp = sa._handle_unknown(cmd, session, conv, sa)
        assert "not sure" in resp.response_text

    def test_generate_clarification_suggestions(self):
        sa = SmartAssistant()
        cmd = ParsedCommand(raw_text="do something", command_type=CommandType.UNKNOWN,
                            confidence=0.4, intent="unknown", parameters={},
                            intent_scores={CommandType.QUERY: 0.5, CommandType.ACTION: 0.35})
        suggestions = sa._generate_clarification_suggestions(cmd)
        assert len(suggestions) > 0


# ── System Handlers ────────────────────────────────────────

from kairon_assistant.system_handlers import (
    _query_metrics,
    _query_session,
    handle_config,
    handle_help,
)


class TestSystemHandlers:
    def _make_parsed(self, **overrides):
        from kairon_assistant.command_parser import ParsedCommand
        params = {"raw_text": "test", "command_type": CommandType.HELP,
                  "confidence": 0.9, "intent": "help", "parameters": {},
                  "entities": set(), "intent_scores": {}}
        params.update(overrides)
        return ParsedCommand(**params)

    @pytest.mark.asyncio
    async def test_handle_help(self):
        resp = await handle_help(self._make_parsed(), MagicMock(), MagicMock(), MagicMock())
        assert "help" in resp.response_text.lower()
        assert resp.confidence > 0

    def test_query_session(self):
        import types
        session = types.SimpleNamespace(
            session_id="sess-1", user_id="user-1",
            command_count=5, duration_seconds=120.0,
        )
        conv = MagicMock()
        conv.turn_count = 3
        conv.last_entities = {"organ": "D-Execution"}
        resp = _query_session(session, conv)
        assert "sess-1" in resp.response_text

    @pytest.mark.asyncio
    async def test_handle_config_show(self):
        resp = await handle_config(self._make_parsed(), MagicMock(), MagicMock(), MagicMock())
        assert "Configuration" in resp.response_text or "config" in resp.response_text.lower()

    @pytest.mark.asyncio
    async def test_query_metrics(self):
        resp = await _query_metrics("", self._make_parsed())
        assert "Metrics" in resp.response_text or "CPU" in resp.response_text
