from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from kairon_assistant.types import CommandType

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Single conversation turn."""

    timestamp: float
    user_message: str
    assistant_response: str
    action_taken: bool = False
    command_type: CommandType | None = None
    entities: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    """Conversation context for a session."""

    session_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def last_command_type(self) -> CommandType | None:
        """Get the last command type from conversation."""
        for turn in reversed(self.turns):
            if turn.command_type:
                return turn.command_type
        return None

    @property
    def last_entities(self) -> dict[str, Any]:
        """Get entities from the last turn."""
        if self.turns:
            return self.turns[-1].entities
        return {}

    @property
    def turn_count(self) -> int:
        """Get number of turns."""
        return len(self.turns)

    def to_prompt_context(self, max_turns: int = 5) -> str:
        """Convert context to prompt format for LLM."""
        recent_turns = self.turns[-max_turns:] if len(self.turns) > max_turns else self.turns

        context_parts = []
        for turn in recent_turns:
            context_parts.append(f"User: {turn.user_message}")
            context_parts.append(f"Assistant: {turn.assistant_response}")

        return "\n".join(context_parts)


class ContextManager:
    """Manage conversation contexts for multi-turn dialogues.

    Features:
    1. Context persistence across turns
    2. Automatic context summarization
    3. Context expiration/cleanup
    4. Entity carryover between turns
    """

    def __init__(self, max_turns: int = 10, ttl_seconds: float = 3600) -> None:
        self.max_turns = max_turns
        self.ttl_seconds = ttl_seconds
        self._contexts: dict[str, ConversationContext] = {}

    def get_context(self, session_id: str) -> ConversationContext | None:
        """Get or create conversation context."""
        if session_id not in self._contexts:
            self._contexts[session_id] = ConversationContext(session_id=session_id)

        context = self._contexts[session_id]

        # Check TTL
        if time.time() - context.last_activity > self.ttl_seconds:
            logger.info("[ContextManager] Context expired for session %s", session_id)
            self._contexts[session_id] = ConversationContext(session_id=session_id)

        return self._contexts[session_id]

    def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        action_taken: bool = False,
        command_type: CommandType | None = None,
        entities: dict[str, Any] | None = None,
    ) -> None:
        """Add a new turn to conversation."""
        context = self.get_context(session_id)

        turn = ConversationTurn(
            timestamp=time.time(),
            user_message=user_message,
            assistant_response=assistant_response,
            action_taken=action_taken,
            command_type=command_type,
            entities=entities or {},
        )

        context.turns.append(turn)
        context.last_activity = time.time()

        # Trim to max turns
        if len(context.turns) > self.max_turns:
            context.turns = context.turns[-self.max_turns :]

        logger.debug("[ContextManager] Added turn %d for session %s", len(context.turns), session_id)

    def update_entities(self, session_id: str, entities: dict[str, Any]) -> None:
        """Update entities in the last turn."""
        context = self._contexts.get(session_id)
        if context and context.turns:
            context.turns[-1].entities.update(entities)

    def get_referenced_entities(self, session_id: str) -> dict[str, Any]:
        """Get all entities referenced in conversation."""
        context = self._contexts.get(session_id)
        if not context:
            return {}

        all_entities: dict[str, Any] = {}
        for turn in context.turns:
            all_entities.update(turn.entities)

        return all_entities

    def clear_context(self, session_id: str) -> None:
        """Clear conversation context."""
        if session_id in self._contexts:
            del self._contexts[session_id]
            logger.info("[ContextManager] Cleared context for session %s", session_id)

    def cleanup_expired(self) -> int:
        """Clean up expired contexts. Returns count cleared."""
        now = time.time()
        expired = [sid for sid, ctx in self._contexts.items() if now - ctx.last_activity > self.ttl_seconds]

        for sid in expired:
            del self._contexts[sid]

        if expired:
            logger.info("[ContextManager] Cleaned up %d expired contexts", len(expired))

        return len(expired)

    def get_summary(self, session_id: str) -> dict[str, Any]:
        """Get conversation summary."""
        context = self._contexts.get(session_id)
        if not context:
            return {"error": "Context not found"}

        return {
            "session_id": session_id,
            "turn_count": len(context.turns),
            "duration_seconds": time.time() - context.created_at,
            "last_activity_seconds_ago": time.time() - context.last_activity,
            "entities": self.get_referenced_entities(session_id),
            "actions_taken": sum(1 for t in context.turns if t.action_taken),
        }

    def get_total_count(self) -> int:
        """Get total number of tracked contexts."""
        return len(self._contexts)

    def export_context(self, session_id: str) -> dict[str, Any] | None:
        """Export context for persistence."""
        context = self._contexts.get(session_id)
        if not context:
            return None

        return {
            "session_id": context.session_id,
            "turns": [
                {
                    "timestamp": t.timestamp,
                    "user_message": t.user_message,
                    "assistant_response": t.assistant_response,
                    "action_taken": t.action_taken,
                    "command_type": t.command_type.value if t.command_type else None,
                    "entities": t.entities,
                }
                for t in context.turns
            ],
            "created_at": context.created_at,
            "metadata": context.metadata,
        }

    def import_context(self, data: dict[str, Any]) -> ConversationContext:
        """Import context from persistence."""
        context = ConversationContext(
            session_id=data["session_id"],
            created_at=data.get("created_at", time.time()),
            metadata=data.get("metadata", {}),
        )

        for turn_data in data.get("turns", []):
            turn = ConversationTurn(
                timestamp=turn_data["timestamp"],
                user_message=turn_data["user_message"],
                assistant_response=turn_data["assistant_response"],
                action_taken=turn_data.get("action_taken", False),
                command_type=CommandType(turn_data["command_type"]) if turn_data.get("command_type") else None,
                entities=turn_data.get("entities", {}),
            )
            context.turns.append(turn)

        self._contexts[context.session_id] = context
        return context
