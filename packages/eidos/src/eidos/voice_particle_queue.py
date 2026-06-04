from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Summary: Execution-owned, in-memory queue for session-aware voice particle handoff
Authority: organs/D-Continuity/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Voice Session Particle Queue ≡ Module
# 内涵 ≝ {Voice, Session, Particle, Queue}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, VoiceSessionParticleQueue)}
# 功能 ⊢ {Voice_Session, Session_Particle, Particle_Init}
# =============================================================================


import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from eidos.base_membrane import BaseMembrane


class SessionParticleLike(Protocol):
    id: str


@dataclass
class QueuedSessionParticle:
    """Ephemeral session-aware handoff record for a queued voice particle."""

    session_id: str
    particle: SessionParticleLike
    continuity_context: dict[str, Any] = field(default_factory=dict)
    source_surface: str = "voice"
    enqueued_at: float = field(default_factory=time.time)

    @property
    def particle_id(self) -> str:
        return self.particle.id


class VoiceSessionParticleQueue(BaseMembrane):
    """Execution-owned, in-memory queue for session-aware voice particle handoff."""

    def __init__(self) -> None:
        super().__init__(metadata_path="eidos/voice_particle_queue.py")
        self._lock = threading.RLock()
        self._session_queues: dict[str, list[QueuedSessionParticle]] = {}

    def enqueue_particle(
        self,
        *,
        session_id: str,
        particle: SessionParticleLike,
        continuity_context: dict[str, Any] | None = None,
        source_surface: str = "voice",
    ) -> QueuedSessionParticle:
        """Append a particle to a session FIFO queue."""
        entry = QueuedSessionParticle(
            session_id=session_id,
            particle=particle,
            continuity_context=dict(continuity_context or {}),
            source_surface=source_surface,
        )
        with self._lock:
            self._session_queues.setdefault(session_id, []).append(entry)
        return entry

    def peek_particles_for_session(self, session_id: str) -> list[QueuedSessionParticle]:
        """Return a stable snapshot of queued particles without removing them."""
        with self._lock:
            return list(self._session_queues.get(session_id, []))

    def dequeue_particles_for_session(self, session_id: str) -> list[QueuedSessionParticle]:
        """Drain all queued particles for a session."""
        with self._lock:
            return self._session_queues.pop(session_id, [])

    def remove_particle(self, session_id: str, particle_id: str) -> bool:
        """Acknowledge a successfully handed-off particle."""
        with self._lock:
            queue = self._session_queues.get(session_id, [])
            remaining = [entry for entry in queue if entry.particle_id != particle_id]
            removed = len(remaining) != len(queue)
            if not remaining:
                self._session_queues.pop(session_id, None)
            else:
                self._session_queues[session_id] = remaining
            return removed

    def get_pending_sessions(self) -> list[str]:
        """Return all session ids that currently have queued particles."""
        with self._lock:
            return [session_id for session_id, queue in self._session_queues.items() if queue]

    def size(self, session_id: str) -> int:
        """Return the queue depth for a given session."""
        with self._lock:
            return len(self._session_queues.get(session_id, []))

    def clear(self) -> None:
        """Drop all queued particles."""
        with self._lock:
            self._session_queues.clear()

    # --------------------------------------------------------------------------
    # Convenience aliases
    # --------------------------------------------------------------------------

    def enqueue(
        self,
        *,
        session_id: str,
        particle: SessionParticleLike,
        continuity_context: dict[str, Any] | None = None,
        source_surface: str = "voice",
    ) -> QueuedSessionParticle:
        """Alias for enqueue_particle()."""
        return self.enqueue_particle(
            session_id=session_id,
            particle=particle,
            continuity_context=continuity_context,
            source_surface=source_surface,
        )

    def peek(self, session_id: str) -> list[QueuedSessionParticle]:
        """Alias for peek_particles_for_session()."""
        return self.peek_particles_for_session(session_id)

    def dequeue(self, session_id: str) -> list[QueuedSessionParticle]:
        """Alias for dequeue_particles_for_session()."""
        return self.dequeue_particles_for_session(session_id)


_DEFAULT_QUEUE: VoiceSessionParticleQueue | None = None
_DEFAULT_QUEUE_LOCK = threading.Lock()


def get_default_voice_session_particle_queue() -> VoiceSessionParticleQueue:
    """Return the process-local default queue instance."""
    global _DEFAULT_QUEUE
    with _DEFAULT_QUEUE_LOCK:
        if _DEFAULT_QUEUE is None:
            _DEFAULT_QUEUE = VoiceSessionParticleQueue()
    return _DEFAULT_QUEUE


__all__ = [
    "QueuedSessionParticle",
    "VoiceSessionParticleQueue",
    "get_default_voice_session_particle_queue",
]
