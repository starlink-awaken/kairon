from __future__ import annotations

from enum import Enum, auto


class CommandType(Enum):
    """Command types supported by the assistant."""

    QUERY = auto()  # Information retrieval
    ACTION = auto()  # Execute action
    CONFIG = auto()  # Configuration changes
    STATUS = auto()  # System status check
    HELP = auto()  # Help request
    GREETING = auto()  # Greeting
    UNKNOWN = auto()  # Unknown intent
