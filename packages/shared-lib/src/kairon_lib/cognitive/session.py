"""Session management for agent toolkit (agentmesh toolkit/session migration)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    """Serializable session state snapshot."""

    id: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: int = 1


@dataclass
class Checkpoint:
    """Session checkpoint with metadata."""

    id: str
    session_id: str
    state: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    label: str = ""


class SessionManager:
    """Session lifecycle manager with checkpoint support."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._checkpoints: dict[str, list[Checkpoint]] = {}

    def create_session(self, session_id: str | None = None) -> SessionState:
        sid = session_id or str(uuid.uuid4())
        session = SessionState(id=sid)
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def update_session(self, session_id: str, data: dict[str, Any]) -> SessionState | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        session.data.update(data)
        session.updated_at = time.time()
        session.version += 1
        return session

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def save_checkpoint(self, session_id: str, label: str = "") -> Checkpoint | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        cp = Checkpoint(
            id=str(uuid.uuid4()),
            session_id=session_id,
            state=dict(session.data),
            label=label,
        )
        self._checkpoints.setdefault(session_id, []).append(cp)
        return cp

    def list_checkpoints(self, session_id: str) -> list[Checkpoint]:
        return list(self._checkpoints.get(session_id, []))

    def restore_checkpoint(self, session_id: str, checkpoint_id: str) -> SessionState | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        for cp in self._checkpoints.get(session_id, []):
            if cp.id == checkpoint_id:
                session.data = dict(cp.state)
                session.updated_at = time.time()
                session.version += 1
                return session
        return None

    def list_sessions(self) -> list[SessionState]:
        return list(self._sessions.values())

    @property
    def session_count(self) -> int:
        return len(self._sessions)
