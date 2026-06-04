from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Claude-Code'
Authority: organs/D-Memory/AGENTS.md
Layer: L3
Constraint: "[!!] PERSONAL_CONTEXT_MEMORY"
Summary: 'EmotionalMemory — 情感状态追踪与情感历史记录'
Tags:
- emotion
- sentiment
- memory
- affect
- context
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Emotional Memory ≡ Module
# 内涵 ≝ {Emotional, Memory}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, EmotionalMemory)}
# 功能 ⊢ {Emotional_Memory, Init_Emotional, Validate_Memory}
# =============================================================================

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from storage_dal import SQLiteError, SQLiteRelationalProvider  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)

# Predicate URI for emotional state triples
PRED_EMOTIONAL_STATE = ":emotionalState"


class EmotionLabel(StrEnum):
    """Core emotion categories (circumplex model based)."""

    JOY = "joy"
    EUPHORIA = "euphoria"
    CONTENTMENT = "contentment"
    SATISFACTION = "satisfaction"
    NEUTRAL = "neutral"
    AMBIGUITY = "ambiguity"
    DISAPPOINTMENT = "disappointment"
    SADNESS = "sadness"
    GRIEF = "grief"
    ANXIETY = "anxiety"
    FEAR = "fear"
    STRESS = "stress"
    ANGER = "anger"
    FRUSTRATION = "frustration"
    BOREDOM = "boredom"
    CONFUSION = "confusion"
    SURPRISE = "surprise"
    HOPE = "hope"
    GRATITUDE = "gratitude"
    PRIDE = "pride"
    SHAME = "shame"
    REGRET = "regret"


# Valence-Arousal mapping (circumplex model)
EMOTION_VALENCE: dict[EmotionLabel, tuple[float, float]] = {
    # valence [-1,1], arousal [0,1]
    EmotionLabel.EUPHORIA: (1.0, 0.9),
    EmotionLabel.JOY: (0.9, 0.7),
    EmotionLabel.GRATITUDE: (0.8, 0.5),
    EmotionLabel.PRIDE: (0.7, 0.7),
    EmotionLabel.HOPE: (0.6, 0.6),
    EmotionLabel.CONTENTMENT: (0.6, 0.3),
    EmotionLabel.SATISFACTION: (0.5, 0.4),
    EmotionLabel.NEUTRAL: (0.0, 0.5),
    EmotionLabel.AMBIGUITY: (0.0, 0.4),
    EmotionLabel.SURPRISE: (0.2, 0.9),
    EmotionLabel.CONFUSION: (-0.2, 0.6),
    EmotionLabel.BOREDOM: (-0.3, 0.1),
    EmotionLabel.DISAPPOINTMENT: (-0.5, 0.4),
    EmotionLabel.REGRET: (-0.5, 0.3),
    EmotionLabel.ANXIETY: (-0.4, 0.8),
    EmotionLabel.STRESS: (-0.5, 0.9),
    EmotionLabel.SADNESS: (-0.7, 0.3),
    EmotionLabel.FEAR: (-0.7, 0.8),
    EmotionLabel.FRUSTRATION: (-0.6, 0.7),
    EmotionLabel.ANGER: (-0.7, 0.8),
    EmotionLabel.SHAME: (-0.6, 0.5),
    EmotionLabel.GRIEF: (-0.9, 0.4),
}


@dataclass
class EmotionSnapshot:
    """Point-in-time emotional state snapshot."""

    snapshot_id: str
    timestamp: float = field(default_factory=time.time)
    primary: EmotionLabel = EmotionLabel.NEUTRAL
    valence: float = 0.0  # [-1.0, 1.0] negative to positive
    arousal: float = 0.5  # [0.0, 1.0] low energy to high energy
    intensity: float = 0.5  # [0.0, 1.0]
    secondary: list[EmotionLabel] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)  # What caused this state
    notes: str = ""
    context_tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_label(
        label: EmotionLabel | str,
        intensity: float = 0.5,
        triggers: list[str] | None = None,
        secondary: list[EmotionLabel] | None = None,
    ) -> EmotionSnapshot:
        """Create a snapshot from an emotion label using circumplex mapping."""
        if isinstance(label, str):
            try:
                label = EmotionLabel(label)
            except ValueError:
                label = EmotionLabel.NEUTRAL
        v, a = EMOTION_VALENCE.get(label, (0.0, 0.5))
        import uuid

        return EmotionSnapshot(
            snapshot_id=f"emo_{uuid.uuid4().hex[:12]}",
            primary=label,
            valence=v * intensity,
            arousal=a * intensity,
            intensity=intensity,
            secondary=secondary or [],
            triggers=triggers or [],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "primary": self.primary.value,
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "intensity": round(self.intensity, 3),
            "secondary": [e.value for e in self.secondary],
            "triggers": self.triggers,
            "notes": self.notes,
            "context_tags": self.context_tags,
        }


class EmotionalMemory:
    """情感状态追踪层 — 记录情感快照、跟踪情感历史、注入情感上下文。

    架构:
    - 当前状态: _current_state (EmotionSnapshot)
    - 历史快照: _history (list, capped)
    - FactGraph: 情感三元组持久化
    - HoloMemory: LTM 备份

    功能:
    - 情感状态记录与更新
    - 情感历史查询
    - 情感趋势分析
    - 情感上下文注入
    """

    MAX_HISTORY = 1000  # Keep last 1000 snapshots
    TREND_WINDOW_SIZE = 10  # Moving average window for trend analysis
    DEFAULT_DECAY_RATE = 0.0001  # Same as HoloMemory task_context

    def __init__(
        self,
        db_path: str | None = None,
        fact_graph: Any | None = None,
        holo_memory: Any | None = None,
        metadata_path: str = "organs/D-Memory/organs/emotional_memory.py",
    ) -> None:
        self.status = "active"
        self._current_state: EmotionSnapshot | None = None
        self._history: list[EmotionSnapshot] = []
        self._fact_graph = fact_graph
        self._holo_memory = holo_memory
        self._db_path = db_path
        self._db_provider: SQLiteRelationalProvider | None = SQLiteRelationalProvider(db_path) if db_path else None
        self._db_initialized = False
        self._history_locked = False  # When True, don't auto-update current state

    # ------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------

    def record(
        self,
        emotion: EmotionLabel | str,
        intensity: float = 0.5,
        triggers: list[str] | None = None,
        secondary: list[EmotionLabel] | None = None,
        notes: str = "",
        context_tags: list[str] | None = None,
        auto_commit: bool = True,
    ) -> EmotionSnapshot:
        """Record a new emotional state snapshot.

        Args:
            emotion: Primary emotion label
            intensity: Emotional intensity [0.0, 1.0]
            triggers: List of trigger descriptions
            secondary: Secondary emotion labels
            notes: Free-text notes
            context_tags: Contextual tags (e.g., "morning", "work", "weekend")
            auto_commit: Whether to auto-commit to history (False = just update current)

        Returns:
            The created EmotionSnapshot
        """
        if isinstance(emotion, str):
            try:
                emotion = EmotionLabel(emotion)
            except ValueError:
                emotion = EmotionLabel.NEUTRAL

        snapshot = EmotionSnapshot.from_label(
            label=emotion,
            intensity=intensity,
            triggers=triggers,
            secondary=secondary,
        )
        snapshot.notes = notes
        snapshot.context_tags = context_tags or []

        self._current_state = snapshot

        if auto_commit:
            self._append_history(snapshot)
            self._persist_snapshot(snapshot)
            self._persist_to_fact_graph(snapshot)

        self._log(
            f"Emotional state recorded: {emotion.value} (valence={snapshot.valence:.2f}, "
            f"arousal={snapshot.arousal:.2f}, intensity={intensity:.2f})"
        )
        return snapshot

    def update_current(
        self,
        valence_delta: float = 0.0,
        arousal_delta: float = 0.0,
        intensity_delta: float = 0.0,
    ) -> EmotionSnapshot | None:
        """Adjust current emotional state incrementally."""
        if self._current_state is None:
            return None

        self._current_state.valence = max(-1.0, min(1.0, self._current_state.valence + valence_delta))
        self._current_state.arousal = max(0.0, min(1.0, self._current_state.arousal + arousal_delta))
        self._current_state.intensity = max(0.0, min(1.0, self._current_state.intensity + intensity_delta))
        return self._current_state

    def commit_current(self) -> None:
        """Commit the current emotional state to history."""
        if self._current_state is not None and not self._history_locked:
            self._append_history(self._current_state)
            self._persist_snapshot(self._current_state)
            self._persist_to_fact_graph(self._current_state)

    def get_current(self) -> EmotionSnapshot | None:
        """Get the current emotional state."""
        return self._current_state

    def lock(self) -> None:
        """Lock the current state — prevents auto-updates."""
        self._history_locked = True

    def unlock(self) -> None:
        """Unlock — allow auto-updates again."""
        self._history_locked = False

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(
        self,
        limit: int = 50,
        since: float | None = None,
        until: float | None = None,
        emotion_filter: EmotionLabel | str | None = None,
        context_tag: str | None = None,
    ) -> list[EmotionSnapshot]:
        """Query emotional history with filters."""
        results = list(self._history)
        if since is not None:
            results = [s for s in results if s.timestamp >= since]
        if until is not None:
            results = [s for s in results if s.timestamp <= until]
        if emotion_filter is not None:
            if isinstance(emotion_filter, str):
                try:
                    emotion_filter = EmotionLabel(emotion_filter)
                except ValueError:
                    emotion_filter = EmotionLabel.NEUTRAL
            results = [s for s in results if s.primary == emotion_filter]
        if context_tag:
            results = [s for s in results if context_tag in s.context_tags]
        results.sort(key=lambda s: s.timestamp, reverse=True)
        return results[:limit]

    def get_dominant_emotion(self, since: float | None = None) -> tuple[EmotionLabel, int]:
        """Return the most frequent emotion since timestamp."""
        history = self.get_history(limit=1000, since=since)
        if not history:
            return EmotionLabel.NEUTRAL, 0
        counts: dict[EmotionLabel, int] = {}
        for snap in history:
            counts[snap.primary] = counts.get(snap.primary, 0) + 1
        dominant = max(counts, key=lambda k: counts[k])
        return dominant, counts[dominant]

    def get_trend(self, window_size: int | None = None) -> dict[str, Any]:
        """Compute emotional trend over recent history.

        Returns valence/arousal moving averages and direction.
        """
        ws = window_size or self.TREND_WINDOW_SIZE
        recent = self._history[-ws:] if self._history else []

        if len(recent) < 2:
            return {"trend": "insufficient_data", "valence_avg": 0.0, "arousal_avg": 0.5}

        v_avg = sum(s.valence for s in recent) / len(recent)
        a_avg = sum(s.arousal for s in recent) / len(recent)

        # Direction: compare first half vs second half
        mid = len(recent) // 2
        first_half = recent[:mid]
        second_half = recent[mid:]
        v_first = sum(s.valence for s in first_half) / len(first_half) if first_half else 0
        v_second = sum(s.valence for s in second_half) / len(second_half) if second_half else 0
        a_first = sum(s.arousal for s in first_half) / len(first_half) if first_half else 0.5
        a_second = sum(s.arousal for s in second_half) / len(second_half) if second_half else 0.5

        v_delta = v_second - v_first
        a_delta = a_second - a_first

        # Determine trend label
        if v_delta > 0.1 and a_delta > 0.1:
            trend = "improving_energized"
        elif v_delta > 0.1 and a_delta < -0.1:
            trend = "improving_calm"
        elif v_delta < -0.1 and a_delta > 0.1:
            trend = "declining_stressed"
        elif v_delta < -0.1 and a_delta < -0.1:
            trend = "declining_drained"
        elif abs(v_delta) < 0.05:
            trend = "stable"
        elif v_delta > 0:
            trend = "slight_improvement"
        else:
            trend = "slight_decline"

        return {
            "trend": trend,
            "valence_avg": round(v_avg, 3),
            "arousal_avg": round(a_avg, 3),
            "valence_delta": round(v_delta, 3),
            "arousal_delta": round(a_delta, 3),
            "samples": len(recent),
            "dominant_emotion": self.get_dominant_emotion()[0].value,
        }

    # ------------------------------------------------------------------
    # Context Injection
    # ------------------------------------------------------------------

    def inject_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Inject emotional context into a cognition context dict.

        Returns:
            Modified context dict with "_emotional_state" and "_emotional_trend" keys
        """
        if self._current_state:
            context["_emotional_state"] = self._current_state.to_dict()

        trend = self.get_trend()
        context["_emotional_trend"] = trend

        return context

    # ------------------------------------------------------------------
    # Time-series analysis helpers
    # ------------------------------------------------------------------

    def get_valence_series(self, limit: int = 100) -> list[float]:
        """Get valence time series for charting."""
        return [s.valence for s in self._history[-limit:]]

    def get_arousal_series(self, limit: int = 100) -> list[float]:
        """Get arousal time series for charting."""
        return [s.arousal for s in self._history[-limit:]]

    def get_timestamp_series(self, limit: int = 100) -> list[str]:
        """Get ISO timestamp series."""
        return [datetime.fromtimestamp(s.timestamp, tz=UTC).isoformat() for s in self._history[-limit:]]

    def get_statistics(self) -> dict[str, Any]:
        """Return emotional memory statistics."""
        if not self._history:
            return {
                "total_snapshots": 0,
                "dominant_emotion": "none",
                "avg_valence": 0.0,
                "avg_arousal": 0.5,
                "avg_intensity": 0.0,
            }
        import statistics

        valences = [s.valence for s in self._history]
        arousals = [s.arousal for s in self._history]
        intensities = [s.intensity for s in self._history]
        dominant, count = self.get_dominant_emotion()
        return {
            "total_snapshots": len(self._history),
            "dominant_emotion": dominant.value,
            "dominant_count": count,
            "avg_valence": round(statistics.mean(valences), 3),
            "avg_arousal": round(statistics.mean(arousals), 3),
            "avg_intensity": round(statistics.mean(intensities), 3),
            "std_valence": round(statistics.pstdev(valences), 3) if len(valences) > 1 else 0.0,
            "emotion_distribution": {e.value: len([s for s in self._history if s.primary == e]) for e in EmotionLabel},
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _append_history(self, snapshot: EmotionSnapshot) -> None:
        """Append snapshot to history, cap at MAX_HISTORY."""
        self._history.append(snapshot)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY :]

    def _init_db(self) -> None:
        """Initialize SQLite tables."""
        if self._db_initialized or self._db_provider is None:
            return
        try:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            provider = self._db_provider
            provider.execute(
                """
                CREATE TABLE IF NOT EXISTS emotion_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    primary_emotion TEXT NOT NULL,
                    valence REAL NOT NULL,
                    arousal REAL NOT NULL,
                    intensity REAL NOT NULL,
                    secondary_emotions TEXT NOT NULL DEFAULT '[]',
                    triggers TEXT NOT NULL DEFAULT '[]',
                    notes TEXT NOT NULL DEFAULT '',
                    context_tags TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """
            )
            provider.execute("CREATE INDEX IF NOT EXISTS idx_emo_timestamp ON emotion_snapshots(timestamp DESC)")
            provider.execute("CREATE INDEX IF NOT EXISTS idx_emo_emotion ON emotion_snapshots(primary_emotion)")
            self._db_initialized = True
        except (SQLiteError, OSError) as e:
            _log.warning("[EmotionalMemory] DB init failed (non-fatal): %s", e)

    def _persist_snapshot(self, snapshot: EmotionSnapshot) -> None:
        self._init_db()
        if self._db_provider is not None:
            try:
                self._db_provider.execute(
                    """
                    INSERT OR REPLACE INTO emotion_snapshots
                    (snapshot_id, timestamp, primary_emotion, valence, arousal, intensity,
                     secondary_emotions, triggers, notes, context_tags, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot.snapshot_id,
                        snapshot.timestamp,
                        snapshot.primary.value,
                        snapshot.valence,
                        snapshot.arousal,
                        snapshot.intensity,
                        json.dumps([e.value for e in snapshot.secondary]),
                        json.dumps(snapshot.triggers),
                        snapshot.notes,
                        json.dumps(snapshot.context_tags),
                        json.dumps(snapshot.metadata),
                    ),
                )
            except (SQLiteError, OSError) as e:
                _log.debug("[EmotionalMemory] Snapshot persist failed: %s", e)

    def _persist_to_fact_graph(self, snapshot: EmotionSnapshot) -> None:
        if self._fact_graph is None:
            return
        try:
            self._fact_graph.add_fact(
                "user",
                PRED_EMOTIONAL_STATE,
                snapshot.primary.value,
                snapshot.to_dict(),
            )
        except (AttributeError, TypeError) as e:
            _log.debug("[EmotionalMemory] FactGraph persist failed: %s", e)

    def load_from_db(self) -> int:
        """Load emotional history from SQLite on startup."""
        self._init_db()
        loaded = 0
        if self._db_provider is not None:
            try:
                if self._db_path and not os.path.exists(self._db_path):
                    return 0
                rows = self._db_provider.fetch_all("SELECT * FROM emotion_snapshots ORDER BY timestamp DESC")
                for row in rows:
                    secondary_list = []
                    for e_str in json.loads(row["secondary_emotions"]):
                        try:
                            secondary_list.append(EmotionLabel(e_str))
                        except ValueError:
                            pass
                    snapshot = EmotionSnapshot(
                        snapshot_id=row["snapshot_id"],
                        timestamp=row["timestamp"],
                        primary=EmotionLabel(row["primary_emotion"]),
                        valence=row["valence"],
                        arousal=row["arousal"],
                        intensity=row["intensity"],
                        secondary=secondary_list,
                        triggers=json.loads(row["triggers"]),
                        notes=row["notes"],
                        context_tags=json.loads(row["context_tags"]),
                        metadata=json.loads(row["metadata"]),
                    )
                    self._history.append(snapshot)
                    loaded += 1

                # Set current to most recent
                if self._history:
                    self._current_state = self._history[-1]

                self._log(f"Loaded {loaded} emotional snapshots")
            except (SQLiteError, OSError, json.JSONDecodeError) as e:
                _log.warning("[EmotionalMemory] Load from DB failed: %s", e)
        return loaded

    def _log(self, message: str) -> None:
        _log.info("[EmotionalMemory] %s", message)

    def validate_internal_state(self) -> bool:
        # Basic sanity: current state valence/arousal within bounds
        if self._current_state is not None:
            s = self._current_state
            if not (-1.0 <= s.valence <= 1.0):
                _log.warning("[EmotionalMemory] Valence out of bounds: %s", s.valence)
                return False
            if not (0.0 <= s.arousal <= 1.0):
                _log.warning("[EmotionalMemory] Arousal out of bounds: %s", s.arousal)
                return False
            if not (0.0 <= s.intensity <= 1.0):
                _log.warning("[EmotionalMemory] Intensity out of bounds: %s", s.intensity)
                return False
        return True


# ── Convenience singleton ──────────────────────────────────────────────
_emotional_memory_singleton: EmotionalMemory | None = None


def get_emotional_memory(
    db_path: str | None = None,
    fact_graph: Any | None = None,
    holo_memory: Any | None = None,
) -> EmotionalMemory:
    """Get the global EmotionalMemory singleton."""
    global _emotional_memory_singleton
    if _emotional_memory_singleton is None:
        _emotional_memory_singleton = EmotionalMemory(db_path=db_path, fact_graph=fact_graph, holo_memory=holo_memory)
        _emotional_memory_singleton.load_from_db()
    return _emotional_memory_singleton
