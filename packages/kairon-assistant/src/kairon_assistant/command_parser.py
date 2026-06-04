from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from kairon_assistant.context_manager import ConversationContext
from kairon_assistant.types import CommandType

logger = logging.getLogger(__name__)


@dataclass
class ParsedCommand:
    """Parsed command structure."""

    raw_text: str
    command_type: CommandType
    intent: str
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    intent_scores: dict[CommandType, float] = field(default_factory=dict, repr=False)
    entities: dict[str, Any] = field(default_factory=dict)


class CommandParser:
    """Natural language command parser.

    Features:
    1. Pattern-based intent recognition
    2. Entity extraction
    3. Context-aware parsing
    4. Confidence scoring
    """

    def __init__(self) -> None:
        self._patterns: dict[CommandType, list[tuple[str, float]]] = self._load_patterns()
        self._entity_patterns: dict[str, re.Pattern] = self._load_entity_patterns()

    def parse(self, text: str, context: ConversationContext | None = None) -> ParsedCommand:
        """Parse natural language text into command.

        Args:
            text: User input text
            context: Optional conversation context

        Returns:
            ParsedCommand with intent, parameters, and confidence
        """
        text_lower = text.lower().strip()

        # Score each command type
        scores: dict[CommandType, float] = {}

        for cmd_type, patterns in self._patterns.items():
            max_score = 0.0
            for pattern, weight in patterns:
                if pattern in text_lower:
                    max_score = max(max_score, weight)
                elif self._fuzzy_match(pattern, text_lower):
                    max_score = max(max_score, weight * 0.7)
            scores[cmd_type] = max_score

        # Determine best match
        best_type = max(scores, key=lambda k: scores[k])
        best_score = scores[best_type]

        # Extract entities
        entities = self._extract_entities(text)

        # Extract parameters based on command type
        parameters = self._extract_parameters(text, best_type, entities)

        # Context boost for follow-up questions
        if context and best_score < 0.8:
            best_type, best_score = self._apply_context_boost(text, best_type, best_score, context)

        # Map to specific intent
        intent = self._map_to_intent(best_type, text, parameters)

        return ParsedCommand(
            raw_text=text,
            command_type=best_type if best_score > 0.1 else CommandType.UNKNOWN,
            intent=intent,
            parameters=parameters,
            confidence=best_score,
            intent_scores=scores,
            entities=entities,
        )

    def _load_patterns(self) -> dict[CommandType, list[tuple[str, float]]]:
        """Load intent recognition patterns."""
        return {
            CommandType.GREETING: [
                ("hello", 1.0),
                ("hi", 0.9),
                ("hey", 0.9),
                ("good morning", 0.9),
                ("good afternoon", 0.9),
                ("howdy", 0.8),
                ("greetings", 0.9),
            ],
            CommandType.QUERY: [
                ("what is", 0.9),
                ("what's", 0.9),
                ("show me", 0.9),
                ("tell me", 0.9),
                ("list", 0.8),
                ("get", 0.8),
                ("find", 0.8),
                ("search", 0.8),
                ("display", 0.8),
                ("how many", 0.85),
                ("how much", 0.85),
                ("status of", 0.85),
                ("information about", 0.85),
            ],
            CommandType.ACTION: [
                ("start", 0.9),
                ("stop", 0.9),
                ("restart", 0.9),
                ("run", 0.85),
                ("execute", 0.9),
                ("perform", 0.85),
                ("create", 0.85),
                ("delete", 0.85),
                ("update", 0.85),
                ("enable", 0.85),
                ("disable", 0.85),
                ("trigger", 0.8),
                ("initiate", 0.8),
            ],
            CommandType.STATUS: [
                ("status", 1.0),
                ("health", 0.9),
                ("state", 0.85),
                ("how is", 0.8),
                ("check", 0.85),
                ("monitor", 0.8),
                ("working", 0.7),
                ("running", 0.7),
            ],
            CommandType.CONFIG: [
                ("configure", 0.9),
                ("set", 0.85),
                ("change", 0.8),
                ("update config", 0.9),
                ("modify", 0.8),
                ("adjust", 0.8),
                ("tune", 0.75),
            ],
            CommandType.HELP: [
                ("help", 1.0),
                ("?", 0.9),
                ("assist", 0.85),
                ("how do i", 0.8),
                ("how to", 0.8),
                ("what can you do", 0.9),
                ("commands", 0.85),
            ],
        }

    def _load_entity_patterns(self) -> dict[str, re.Pattern]:
        """Load entity extraction patterns."""
        return {
            "organ": re.compile(r"\b(D-[A-Z][a-zA-Z]+)\b"),
            "file_path": re.compile(r"\b[\w\-/.]+\.(json|yaml|py|md|txt)\b"),
            "url": re.compile(r"https?://\S+"),
            "number": re.compile(r"\b(\d+(?:\.\d+)?)\s*(MB|GB|TB|ms|s|min|%)?\b", re.IGNORECASE),
            "role": re.compile(r"\b(admin|operator|viewer|builder)\b", re.IGNORECASE),
            "boolean": re.compile(r"\b(true|false|on|off|yes|no|enable|disable)\b", re.IGNORECASE),
        }

    def _fuzzy_match(self, pattern: str, text: str) -> bool:
        """Simple fuzzy matching."""
        # Check for word variations
        words = pattern.split()
        return all(any(w.startswith(word[:3]) for w in text.split()) for word in words)

    def _extract_entities(self, text: str) -> dict[str, Any]:
        """Extract entities from text."""
        entities = {}

        for entity_type, pattern in self._entity_patterns.items():
            matches = pattern.findall(text)
            if matches:
                entities[entity_type] = matches if len(matches) > 1 else matches[0]

        return entities

    def _extract_parameters(self, text: str, cmd_type: CommandType, entities: dict[str, Any]) -> dict[str, Any]:
        """Extract command-specific parameters."""
        params = dict(entities)

        # Extract target (what the command applies to)
        words = text.lower().split()

        if cmd_type == CommandType.QUERY:
            # Find what to query about
            for i, word in enumerate(words):
                if word in ["about", "for", "of"] and i + 1 < len(words):
                    params["target"] = words[i + 1]
                    break

        elif cmd_type == CommandType.ACTION:
            # Find action target
            for i, word in enumerate(words):
                if word in ["the", "organ", "service"] and i + 1 < len(words):
                    params["target"] = words[i + 1]
                    break
            # Find action verb
            action_verbs = ["start", "stop", "restart", "run", "execute", "create", "delete"]
            for word in words:
                if word in action_verbs:
                    params["action"] = word
                    break

        elif cmd_type == CommandType.CONFIG:
            # Extract key=value pairs
            kv_pattern = re.compile(r'(\w+)\s*=\s*["\']?([^"\']+)["\']?')
            for match in kv_pattern.finditer(text):
                params[match.group(1)] = match.group(2)

        return params

    def _apply_context_boost(
        self,
        text: str,
        current_type: CommandType,
        current_score: float,
        context: ConversationContext,
    ) -> tuple[CommandType, float]:
        """Apply context-based scoring boost."""
        # Check for follow-up indicators
        follow_up_words = ["it", "that", "this", "them", "those", "also", "too"]
        is_follow_up = any(word in text.lower().split() for word in follow_up_words)

        if is_follow_up and context.last_command_type:
            # Boost previous command type
            return context.last_command_type, min(current_score + 0.2, 1.0)

        return current_type, current_score

    def _map_to_intent(self, cmd_type: CommandType, text: str, params: dict) -> str:
        """Map command type to specific intent."""
        intent_map = {
            CommandType.QUERY: "information_retrieval",
            CommandType.ACTION: f"execute_{params.get('action', 'action')}",
            CommandType.STATUS: "system_status_check",
            CommandType.CONFIG: "configuration_change",
            CommandType.HELP: "help_request",
            CommandType.GREETING: "greeting",
            CommandType.UNKNOWN: "unknown",
        }

        base_intent = intent_map.get(cmd_type, "unknown")

        # Refine based on target
        if "target" in params:
            return f"{base_intent}_{params['target']}"

        return base_intent

    def add_pattern(self, cmd_type: CommandType, pattern: str, weight: float) -> None:
        """Add a custom pattern for intent recognition."""
        if cmd_type not in self._patterns:
            self._patterns[cmd_type] = []
        self._patterns[cmd_type].append((pattern.lower(), weight))
        logger.info("[CommandParser] Added pattern for %s: %s", cmd_type.value, pattern)
