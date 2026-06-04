from __future__ import annotations

"""
---
Type: Organ
Layer: L3
Domain: D-Intelligence
Status: ACTIVE
Version: 1.0.0
Summary: Smart Assistant core - Main orchestrator
Source: SharedBrain D_Intelligence/organs/smart_assistant/core.py
Migrated: Wave 2 → kairon kairon-assistant
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Core ≡ Module
# 内涵 ≝ {Core}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Core)}
# 功能 ⊢ {Init_Core, Execute_Core, Validate_Core}
# =============================================================================


import logging
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

# NOTE: 以下依赖模块尚未在 Wave 2 迁移中，待后续 Wave 补充
from kairon_assistant.command_parser import CommandParser, ParsedCommand
from kairon_assistant.context_manager import ContextManager, ConversationContext
from kairon_assistant.governance_integration import GovernanceIntegration
from kairon_assistant.recommendation_engine import RecommendationEngine
from kairon_assistant.session_manager import AssistantSession, SessionManager
from kairon_assistant.types import CommandType

logger = logging.getLogger(__name__)


@dataclass
class AssistantConfig:
    """Smart Assistant configuration."""

    max_context_turns: int = 10
    enable_recommendations: bool = True
    enable_proactive_suggestions: bool = True
    response_timeout_seconds: float = 30.0
    governance_check: bool = True
    command_confidence_threshold: float = 0.7


@dataclass
class AssistantResponse:
    """Assistant response structure."""

    response_text: str
    action_taken: bool = False
    action_result: Any = None
    suggestions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    context_used: bool = False


class SmartAssistant:
    """Smart Assistant - Natural language interface for B-OS.

    Features:
    1. Natural language command parsing
    2. Context-aware multi-turn conversations
    3. Role-based access control via D-Governance
    4. Intelligent recommendations
    5. Integration with all B-OS organs
    """

    def __init__(self, config: AssistantConfig | None = None) -> None:
        self.config = config or AssistantConfig()
        self.command_parser = CommandParser()
        self.context_manager = ContextManager(max_turns=self.config.max_context_turns)
        self.recommendation_engine = RecommendationEngine()
        self.governance = GovernanceIntegration(enabled=self.config.governance_check)
        self.session_manager = SessionManager()

        self._command_handlers: dict[CommandType, Callable] = {}
        self._running = False

    async def initialize(self) -> None:
        """Initialize the smart assistant."""
        logger.info("[SmartAssistant] Initializing...")

        # Register default command handlers
        self._register_default_handlers()

        # Initialize sub-components
        await self.governance.initialize()

        self._running = True
        logger.info("[SmartAssistant] Initialized successfully")

    async def shutdown(self) -> None:
        """Shutdown the smart assistant."""
        logger.info("[SmartAssistant] Shutting down...")
        self._running = False
        await self.governance.shutdown()
        logger.info("[SmartAssistant] Shutdown complete")

    async def process_message(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AssistantResponse:
        """Process a user message and return response.

        Args:
            message: User input message
            session_id: Optional session ID for continuity
            user_id: User ID for governance checks
            context: Additional context data

        Returns:
            AssistantResponse with text and optional actions
        """
        start_time = time.time()

        # Get or create session
        session = self.session_manager.get_or_create_session(session_id, user_id)

        # Build conversation context
        conversation = self.context_manager.get_context(session.session_id)

        # Parse command from message
        parsed = self.command_parser.parse(message, conversation)

        logger.info(
            "[SmartAssistant] Parsed command: %s (confidence: %.2f)", parsed.command_type.value, parsed.confidence
        )

        # Check governance permissions
        if self.config.governance_check and user_id:
            allowed = await self.governance.check_permission(user_id, parsed.command_type, parsed.parameters)
            if not allowed:
                return AssistantResponse(
                    response_text="I don't have permission to perform this action. Please check your role permissions.",
                    confidence=1.0,
                )

        # Handle low confidence
        if parsed.confidence < self.config.command_confidence_threshold:
            suggestions = self._generate_clarification_suggestions(parsed)
            return AssistantResponse(
                response_text="I'm not sure what you mean. Did you want to:\n"
                + "\n".join(f"- {s}" for s in suggestions),
                suggestions=suggestions,
                confidence=parsed.confidence,
                context_used=bool(conversation),
            )

        # Execute command
        response = await self._execute_command(parsed, session, conversation)

        # Update context
        self.context_manager.add_turn(
            session.session_id,
            user_message=message,
            assistant_response=response.response_text,
            action_taken=response.action_taken,
        )

        # Add recommendations if enabled
        if self.config.enable_recommendations:
            recommendations = self.recommendation_engine.get_recommendations(session, conversation, parsed)
            response.suggestions.extend([r.text for r in recommendations[:3]])

        elapsed = time.time() - start_time
        logger.info("[SmartAssistant] Processed message in %.2fs", elapsed)

        return response

    async def process_message_stream(
        self, message: str, session_id: str | None = None, user_id: str | None = None
    ) -> AsyncIterator[str]:
        """Process message with streaming response."""
        # This would integrate with an LLM for streaming
        # For now, just yield the full response
        response = await self.process_message(message, session_id, user_id)
        yield response.response_text

    def register_command_handler(self, command_type: CommandType, handler: Callable) -> None:
        """Register a handler for a specific command type."""
        self._command_handlers[command_type] = handler
        logger.info("[SmartAssistant] Registered handler for %s", command_type.value)

    def _register_default_handlers(self) -> None:
        """Register default command handlers."""
        from kairon_assistant.system_handlers import (
            handle_action,
            handle_config,
            handle_help,
            handle_query,
            handle_status,
        )

        self._command_handlers = {
            CommandType.QUERY: handle_query,
            CommandType.ACTION: handle_action,
            CommandType.HELP: handle_help,
            CommandType.STATUS: handle_status,
            CommandType.CONFIG: handle_config,
            CommandType.GREETING: self._handle_greeting,
            CommandType.UNKNOWN: self._handle_unknown,
        }

    async def _execute_command(
        self, parsed: ParsedCommand, session: AssistantSession, conversation: ConversationContext | None
    ) -> AssistantResponse:
        """Execute a parsed command."""
        handler = self._command_handlers.get(parsed.command_type)

        if not handler:
            return AssistantResponse(response_text=f"I'm not sure how to handle '{parsed.raw_text}'", confidence=0.5)

        try:
            import inspect

            if inspect.iscoroutinefunction(handler):
                result = await handler(parsed, session, conversation, self)
            else:
                result = handler(parsed, session, conversation, self)

            if isinstance(result, AssistantResponse):
                return result
            else:
                return AssistantResponse(
                    response_text=str(result), action_taken=True, action_result=result, confidence=parsed.confidence
                )

        except (OSError, ValueError, RuntimeError, KeyError) as e:
            logger.error("[SmartAssistant] Command execution error: %s", str(e))
            return AssistantResponse(response_text=f"Sorry, I encountered an error: {str(e)}", confidence=0.0)

    def _handle_greeting(
        self,
        parsed: ParsedCommand,
        session: AssistantSession,
        conversation: ConversationContext | None,
        assistant: SmartAssistant,
    ) -> AssistantResponse:
        """Handle greeting commands."""
        greetings = [
            "Hello! I'm your B-OS assistant. How can I help you today?",
            "Hi there! Ready to help you manage your B-OS system.",
            "Greetings! What would you like to do?",
        ]
        import random

        return AssistantResponse(response_text=random.choice(greetings), confidence=1.0)

    def _handle_unknown(
        self,
        parsed: ParsedCommand,
        session: AssistantSession,
        conversation: ConversationContext | None,
        assistant: SmartAssistant,
    ) -> AssistantResponse:
        """Handle unknown commands."""
        return AssistantResponse(
            response_text=f"I'm not sure how to help with '{parsed.raw_text}'. Try asking 'help' to see what I can do.",
            suggestions=["help", "status", "list commands"],
            confidence=0.3,
        )

    def _generate_clarification_suggestions(self, parsed: ParsedCommand) -> list[str]:
        """Generate clarification suggestions for ambiguous commands."""
        suggestions = []

        # Based on intent matching scores
        for intent, score in parsed.intent_scores.items():
            if score > 0.3 and score < self.config.command_confidence_threshold:
                suggestions.append(f"{intent.value}? (confidence: {score:.0%})")

        if not suggestions:
            suggestions = ["Get system status", "Show help", "List active organs"]

        return suggestions[:3]

    def get_stats(self) -> dict[str, Any]:
        """Get assistant statistics."""
        return {
            "sessions_active": self.session_manager.get_active_count(),
            "total_conversations": self.context_manager.get_total_count(),
            "command_handlers": len(self._command_handlers),
            "recommendations_enabled": self.config.enable_recommendations,
            "governance_enabled": self.config.governance_check,
        }
