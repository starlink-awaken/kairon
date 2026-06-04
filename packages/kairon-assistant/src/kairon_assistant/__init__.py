"""kairon_assistant — Smart Assistant subsystem extracted from SharedBrain D_Intelligence.

Provides command parsing with intent recognition, conversation context management
for multi-turn dialogue, and session lifecycle management.
"""

from kairon_assistant.command_parser import CommandParser, ParsedCommand
from kairon_assistant.context_manager import ContextManager, ConversationContext, ConversationTurn
from kairon_assistant.session_manager import AssistantSession, SessionManager
from kairon_assistant.types import CommandType

__all__ = [
    "AssistantSession",
    "CommandParser",
    "CommandType",
    "ContextManager",
    "ConversationContext",
    "ConversationTurn",
    "ParsedCommand",
    "SessionManager",
]

__version__ = "1.0.0"
