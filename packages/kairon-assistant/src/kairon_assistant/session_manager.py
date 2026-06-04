from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AssistantSession:
    """Assistant session state."""

    session_id: str
    user_id: str | None = None
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    metadata: dict[str, object] = field(default_factory=dict)
    command_count: int = 0
    active: bool = True

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()

    @property
    def idle_seconds(self) -> float:
        """Get seconds since last activity."""
        return time.time() - self.last_activity

    @property
    def duration_seconds(self) -> float:
        """Get total session duration."""
        return time.time() - self.created_at


class SessionManager:
    """Manage assistant sessions.

    Features:
    1. Session lifecycle management
    2. Idle timeout handling
    3. Session persistence
    4. Multi-user support
    """

    def __init__(self, default_ttl_seconds: float = 3600, max_sessions: int = 100) -> None:
        self.default_ttl = default_ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: dict[str, AssistantSession] = {}

    def get_or_create_session(self, session_id: str | None = None, user_id: str | None = None) -> AssistantSession:
        """Get existing session or create new one.

        Args:
            session_id: Existing session ID or None for new
            user_id: User ID to associate with session

        Returns:
            AssistantSession instance
        """
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]

            # Check if expired
            if session.idle_seconds > self.default_ttl:
                logger.info("[SessionManager] Session %s expired, creating new", session_id)
                return self._create_session(user_id)

            session.touch()
            return session

        return self._create_session(user_id)

    def _create_session(self, user_id: str | None = None) -> AssistantSession:
        """Create a new session."""
        # Cleanup if at limit
        if len(self._sessions) >= self.max_sessions:
            self._cleanup_oldest()

        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        session = AssistantSession(session_id=session_id, user_id=user_id)

        self._sessions[session_id] = session
        logger.info("[SessionManager] Created session %s for user %s", session_id, user_id)

        return session

    def get_session(self, session_id: str) -> AssistantSession | None:
        """Get session by ID."""
        session = self._sessions.get(session_id)
        if session:
            # Check expiry
            if session.idle_seconds > self.default_ttl:
                logger.info("[SessionManager] Session %s expired", session_id)
                self.end_session(session_id)
                return None

            session.touch()

        return session

    def end_session(self, session_id: str) -> bool:
        """End a session."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.active = False

            # In production, might persist session here
            logger.info(
                "[SessionManager] Ended session %s (duration: %.1fs, commands: %d)",
                session_id,
                session.duration_seconds,
                session.command_count,
            )

            del self._sessions[session_id]
            return True

        return False

    def increment_command_count(self, session_id: str) -> None:
        """Increment command count for session."""
        session = self._sessions.get(session_id)
        if session:
            session.command_count += 1

    def update_metadata(self, session_id: str, key: str, value: Any) -> None:
        """Update session metadata."""
        session = self._sessions.get(session_id)
        if session:
            session.metadata[key] = value

    def get_metadata(self, session_id: str, key: str, default: Any | None = None) -> Any | None:
        """Get session metadata."""
        session = self._sessions.get(session_id)
        if session:
            return session.metadata.get(key, default)
        return default

    def get_active_count(self) -> int:
        """Get number of active sessions."""
        return len(self._sessions)

    def get_user_sessions(self, user_id: str) -> list[AssistantSession]:
        """Get all sessions for a user."""
        return [s for s in self._sessions.values() if s.user_id == user_id]

    def cleanup_expired(self) -> int:
        """Clean up expired sessions. Returns count removed."""
        expired = [sid for sid, s in self._sessions.items() if s.idle_seconds > self.default_ttl]

        for sid in expired:
            self.end_session(sid)

        if expired:
            logger.info("[SessionManager] Cleaned up %d expired sessions", len(expired))

        return len(expired)

    def _cleanup_oldest(self, count: int = 5) -> None:
        """Clean up oldest sessions."""
        sorted_sessions = sorted(self._sessions.items(), key=lambda x: x[1].last_activity)

        for sid, _ in sorted_sessions[:count]:
            self.end_session(sid)

    def get_stats(self) -> dict[str, object]:
        """Get session manager statistics."""
        if not self._sessions:
            return {"active_sessions": 0, "unique_users": 0, "avg_commands_per_session": 0}

        users = {s.user_id for s in self._sessions.values() if s.user_id}
        total_commands = sum(s.command_count for s in self._sessions.values())

        return {
            "active_sessions": len(self._sessions),
            "unique_users": len(users),
            "avg_commands_per_session": total_commands / len(self._sessions),
            "oldest_session_age_seconds": max(s.duration_seconds for s in self._sessions.values()),
        }

    def list_sessions(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """List sessions."""
        sessions = self._sessions.values()

        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]

        return [
            {
                "session_id": s.session_id,
                "user_id": s.user_id,
                "created_at": s.created_at,
                "last_activity": s.last_activity,
                "idle_seconds": s.idle_seconds,
                "command_count": s.command_count,
                "active": s.active,
            }
            for s in sessions
        ]

    def export_session(self, session_id: str) -> dict[str, Any] | None:
        """Export session data for persistence."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "metadata": session.metadata,
            "command_count": session.command_count,
        }

    def import_session(self, data: dict[str, Any]) -> AssistantSession:
        """Import session from persisted data."""
        session = AssistantSession(
            session_id=data["session_id"],
            user_id=data.get("user_id"),
            created_at=data.get("created_at", time.time()),
            last_activity=data.get("last_activity", time.time()),
            metadata=data.get("metadata", {}),
            command_count=data.get("command_count", 0),
        )

        self._sessions[session.session_id] = session
        return session
