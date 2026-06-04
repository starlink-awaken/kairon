from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
"""Preference learning from user behavior events in D-Memory.

---
Type: Organ
Layer: L3
Domain: D-Memory
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Memory/AGENTS.md
Keywords: [preference, learning, behavior, inference, reinforcement, personalization]
---

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# PreferenceLearner ≡ Organ
# 内涵 ≝ {user_id, preference_type, value, confidence, source, updated_at}
# 外延 ⊢ {p | p ∈ D-Memory ∧ preference_learned(p)}
# 功能 ⊢ {InferPreferences, UpdatePreference, GetPreference, GetAllPreferences}
# =============================================================================

Infers and maintains user preferences from observed behavior events.
Stores structured preferences in FactGraph as Triple semiconstants.
Used by cognition loops for context-aware personalization.

Usage::

    learner = PreferenceLearner()
    prefs = learner.infer_preferences("user-1", events)
    learner.update_preference("user-1", PreferenceType.RESPONSE_STYLE, "concise", 0.9)
    pref = learner.get_preference("user-1", PreferenceType.RESPONSE_STYLE)
    all_prefs = learner.get_all_preferences("user-1")
"""

import json
import logging
import math
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Preference type enum
# ---------------------------------------------------------------------------


class PreferenceType(StrEnum):
    """Categories of user preference inferred from behavior."""

    RESPONSE_STYLE = "response_style"  # concise | detailed | technical
    TOOL_PREFERENCE = "tool_preference"  # preferred tools / methods
    COMMUNICATION_TONE = "communication_tone"  # formal | casual | friendly
    WORKING_HOURS = "working_hours"  # active hours, timezone
    PRIORITY_FOCUS = "priority_focus"  # what user values most


# ---------------------------------------------------------------------------
# Preference dataclass
# ---------------------------------------------------------------------------


@dataclass
class Preference:
    """A structured user preference with confidence and provenance."""

    user_id: str
    preference_type: PreferenceType
    value: Any
    confidence: float = 0.5
    source: str = "inferred"  # inferred | explicit | observed
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "preference_type": self.preference_type.value,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Preference:
        """Reconstruct from a dict (e.g., loaded from FactGraph)."""
        return cls(
            user_id=d["user_id"],
            preference_type=PreferenceType(d["preference_type"]),
            value=d["value"],
            confidence=d.get("confidence", 0.5),
            source=d.get("source", "inferred"),
            created_at=_parse_dt(d.get("created_at")),
            updated_at=_parse_dt(d.get("updated_at")),
        )


def _parse_dt(value: Any) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# BehaviorEvent (lightweight; mirrors behavior_logger.py)
# ---------------------------------------------------------------------------


@dataclass
class BehaviorEvent:
    """Minimal behavior event used for preference inference."""

    user_id: str
    event_type: str
    action: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BehaviorEvent:
        ts = d.get("timestamp")
        if isinstance(ts, datetime):
            dt = ts
        elif isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = datetime.now(UTC)
        return cls(
            user_id=d.get("user_id", ""),
            event_type=d.get("event_type", ""),
            action=d.get("action", ""),
            timestamp=dt,
            metadata=d.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Inference weights
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "frequency": 0.35,  # Repeated behavior → preference signal
    "recency": 0.30,  # Recent behavior weighs more
    "consensus": 0.20,  # Agreement across observations
    "explicit": 0.50,  # Directly stated preference
}

# ---------------------------------------------------------------------------
# PreferenceLearner
# ---------------------------------------------------------------------------


class PreferenceLearner:
    """Learns and maintains structured user preferences from behavior events.

    Stores preferences in FactGraph as Triple semiconstants:
      (user:{user_id}, :has{PrefType}Preference, {value_json})

    Also keeps an in-memory index for fast reads.

    BOS-URI endpoints
    -----------------
    ``bos://memory/preferences/learn``     — infer preferences from events
    ``bos://memory/preferences/set``      — update a single preference
    ``bos://memory/preferences/get``       — get a preference
    ``bos://memory/preferences/all``       — get all preferences for a user
    """

    DEFAULT_CONFIDENCE_THRESHOLD = 0.4
    MAX_INFERENCE_EVENTS = 500
    CONFIDENCE_UPPER_BOUND = 0.98

    def __init__(
        self,
        metadata_path: str = "organs/D-Memory/organs/preference_learner.py",
        fact_graph: Any | None = None,
    ) -> None:
        self._fact_graph = fact_graph
        self._lock = threading.RLock()
        # In-memory index: (user_id, preference_type) -> Preference
        self._index: dict[tuple[str, PreferenceType], Preference] = {}
        self.status = "ACTIVE"
        _log.info("PreferenceLearner initialised")

    # -------------------------------------------------------------------------
    # FactGraph integration
    # -------------------------------------------------------------------------

    def _get_fact_graph(self) -> Any | None:
        """Lazily initialise or return the FactGraph singleton."""
        if self._fact_graph is not None:
            return self._fact_graph
        try:
            from eidos.organs.fact_graph import FactGraph

            self._fact_graph = FactGraph()
            return self._fact_graph
        except (ImportError, OSError) as exc:
            _log.warning("[PreferenceLearner] FactGraph unavailable: %s", exc)
            self._fact_graph = True  # Mark unavailable
            return None

    def _triple_subject(self, user_id: str) -> str:
        return f"user:{user_id}"

    def _triple_predicate(self, pref_type: PreferenceType) -> str:
        return f":has{pref_type.name}Preference"

    def _store_triple(self, pref: Preference) -> None:
        """Persist a preference to FactGraph as a Triple."""
        fg = self._get_fact_graph()
        if fg is None:
            return
        try:
            obj = json.dumps(
                {
                    "user_id": pref.user_id,
                    "preference_type": pref.preference_type.value,
                    "value": pref.value,
                    "confidence": pref.confidence,
                    "source": pref.source,
                    "created_at": pref.created_at.isoformat(),
                    "updated_at": pref.updated_at.isoformat(),
                }
            )
            subject = self._triple_subject(pref.user_id)
            predicate = self._triple_predicate(pref.preference_type)
            fg.upsert_triple(subject, predicate, obj)
        except (AttributeError, TypeError) as exc:
            _log.debug("[PreferenceLearner] FactGraph store failed: %s", exc)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def infer_preferences(
        self,
        user_id: str,
        events: list[BehaviorEvent | dict[str, Any]],
        min_confidence: float = 0.4,
    ) -> list[Preference]:
        """Infer structured preferences from a stream of behavior events.

        Parameters
        ----------
        user_id:
            The user whose preferences to infer.
        events:
            Chronologically ordered behavior events. Accepts both
            ``BehaviorEvent`` objects and plain dicts.
        min_confidence:
            Minimum inference confidence to include in results.

        Returns
        -------
        list[Preference]
            Inferred preferences that exceed ``min_confidence``.
        """
        if not events:
            return []

        # Normalize to BehaviorEvent
        parsed: list[BehaviorEvent] = [
            e if isinstance(e, BehaviorEvent) else BehaviorEvent.from_dict(e) for e in events
        ]

        # Group by event_type → list of values
        by_type: dict[str, list[tuple[Any, float, datetime]]] = {}
        for e in parsed[-self.MAX_INFERENCE_EVENTS :]:
            val = e.metadata.get("value") or e.action
            weight = e.metadata.get("weight", 1.0)
            by_type.setdefault(e.event_type, []).append((val, weight, e.timestamp))

        inferred: list[Preference] = []
        now = datetime.now(UTC)
        total = len(parsed)

        for event_type, observations in by_type.items():
            pref_type = self._match_type(event_type)
            if pref_type is None:
                continue

            # Frequency score
            freq_score = min(len(observations) / 10.0, 1.0) * _WEIGHTS["frequency"]

            # Recency score — exponential decay
            latest_ts = max(ts for _, _, ts in observations)
            recency_days = max(0.0, (now - latest_ts).total_seconds() / 86400.0)
            recency_score = math.exp(-0.1 * recency_days) * _WEIGHTS["recency"]

            # Consensus score — do observations agree?
            value_weights: dict[str, float] = {}
            for val, weight, _ in observations:
                key = json.dumps(val, sort_keys=True)
                value_weights[key] = value_weights.get(key, 0.0) + weight
            total_weight = sum(value_weights.values())
            consensus_score = (max(value_weights.values()) / total_weight) * _WEIGHTS["consensus"]

            confidence = min(freq_score + recency_score + consensus_score, self.CONFIDENCE_UPPER_BOUND)

            if confidence < min_confidence:
                continue

            # Pick the highest-weighted value
            best_value = json.loads(max(value_weights, key=value_weights.get))  # type: ignore[arg-type]

            pref = Preference(
                user_id=user_id,
                preference_type=pref_type,
                value=best_value,
                confidence=round(confidence, 4),
                source="inferred",
                created_at=now,
                updated_at=now,
            )

            # Merge with existing if new confidence is higher
            self._upsert(pref)
            inferred.append(pref)

        _log.info(
            "[PreferenceLearner] inferred %d preferences for user=%s from %d events",
            len(inferred),
            user_id,
            total,
        )
        return inferred

    def update_preference(
        self,
        user_id: str,
        preference_type: PreferenceType | str,
        value: Any,
        confidence: float = 0.8,
        source: str = "explicit",
    ) -> Preference:
        """Set or update a named preference for a user.

        Parameters
        ----------
        user_id:
            The user to update.
        preference_type:
            The type of preference to set.
        value:
            The preference value (JSON-serializable).
        confidence:
            Confidence in [0.0, 1.0]. Defaults to 0.8 for explicit updates.
        source:
            Provenance: ``explicit``, ``inferred``, or ``observed``.

        Returns
        -------
        Preference
            The updated preference.
        """
        pref_type = PreferenceType(preference_type) if isinstance(preference_type, str) else preference_type
        now = datetime.now(UTC)

        existing = self._index.get((user_id, pref_type))
        created_at = existing.created_at if existing else now

        pref = Preference(
            user_id=user_id,
            preference_type=pref_type,
            value=value,
            confidence=max(0.0, min(1.0, confidence)),
            source=source,
            created_at=created_at,
            updated_at=now,
        )

        self._upsert(pref)
        _log.info(
            "[PreferenceLearner] updated %s for user=%s value=%s conf=%.2f src=%s",
            pref_type.value,
            user_id,
            value,
            confidence,
            source,
        )
        return pref

    def get_preference(
        self,
        user_id: str,
        preference_type: PreferenceType | str,
    ) -> Preference | None:
        """Retrieve a single preference for a user.

        Parameters
        ----------
        user_id:
            The user.
        preference_type:
            The preference type to look up.

        Returns
        -------
        Preference | None
            The preference, or None if not found.
        """
        pref_type = PreferenceType(preference_type) if isinstance(preference_type, str) else preference_type
        return self._index.get((user_id, pref_type))

    def get_all_preferences(
        self,
        user_id: str,
        min_confidence: float = 0.0,
    ) -> list[Preference]:
        """Return all preferences for a user.

        Parameters
        ----------
        user_id:
            The user.
        min_confidence:
            Minimum confidence filter. Defaults to 0 (all preferences).

        Returns
        -------
        list[Preference]
            Preferences sorted by confidence descending.
        """
        results = [
            pref for (uid, _), pref in self._index.items() if uid == user_id and pref.confidence >= min_confidence
        ]
        results.sort(key=lambda p: p.confidence, reverse=True)
        return results

    def get_stats(self, user_id: str) -> dict[str, Any]:
        """Return statistics about a user's learned preferences."""
        prefs = self.get_all_preferences(user_id)
        return {
            "user_id": user_id,
            "total_preferences": len(prefs),
            "by_type": {pt.value: len([p for p in prefs if p.preference_type == pt]) for pt in PreferenceType},
            "avg_confidence": round(sum(p.confidence for p in prefs) / len(prefs), 4) if prefs else 0.0,
            "by_source": {
                src: len([p for p in prefs if p.source == src]) for src in {"explicit", "inferred", "observed"}
            },
        }

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _match_type(self, event_type: str) -> PreferenceType | None:
        """Map an event_type string to a PreferenceType when possible."""
        mapping: dict[str, PreferenceType] = {
            "response_format": PreferenceType.RESPONSE_STYLE,
            "response_style": PreferenceType.RESPONSE_STYLE,
            "tool_choice": PreferenceType.TOOL_PREFERENCE,
            "tool_used": PreferenceType.TOOL_PREFERENCE,
            "tone": PreferenceType.COMMUNICATION_TONE,
            "communication_tone": PreferenceType.COMMUNICATION_TONE,
            "work_hours": PreferenceType.WORKING_HOURS,
            "working_hours": PreferenceType.WORKING_HOURS,
            "priority": PreferenceType.PRIORITY_FOCUS,
            "priority_focus": PreferenceType.PRIORITY_FOCUS,
        }
        return mapping.get(event_type.lower())

    def _upsert(self, pref: Preference) -> None:
        """Update in-memory index and persist to FactGraph."""
        with self._lock:
            key = (pref.user_id, pref.preference_type)
            existing = self._index.get(key)
            # Only overwrite if new confidence is higher
            if existing is None or pref.confidence >= existing.confidence:
                self._index[key] = pref
                self._store_triple(pref)

    # Required by CoreService
    def validate_access(self, operation: str, context: dict[str, Any]) -> bool:
        return True

    def get_metadata(self) -> dict[str, Any]:
        return {
            "name": "PreferenceLearner",
            "domain": "D-Memory",
            "layer": "L3",
            "version": "1.0.0",
            "status": self.status,
        }

    def get_registry_info(self) -> dict[str, Any]:
        return {
            "bos_uri": "bos://memory/preferences",
            "endpoints": [
                "bos://memory/preferences/learn",
                "bos://memory/preferences/set",
                "bos://memory/preferences/get",
                "bos://memory/preferences/all",
            ],
        }
