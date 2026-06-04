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
Summary: 'PreferenceStore — 用户偏好存储、推断与应用'
Tags:
- preference
- personalization
- memory
- context
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Preference Store ≡ Module
# 内涵 ≝ {Preference, Store}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, PreferenceStore)}
# 功能 ⊢ {Preference_Store, Init_Preference, Validate_Store}
# =============================================================================

import json
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

from storage_dal import SQLiteError, SQLiteRelationalProvider  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)

# Predicate URI for preference triples
PRED_HAS_PREFERENCE = ":userHasPreference"

# Inference rule weights
INFERENCE_WEIGHTS = {
    "frequency": 0.4,  # Repeated behavior → preference
    "recency": 0.3,  # Recent behavior weighs more
    "absence": 0.2,  # Avoidance suggests inverse preference
    "explicit": 0.5,  # Directly stated preference
}


@dataclass
class PreferenceEntry:
    """Single preference entry with confidence."""

    key: str
    value: Any
    confidence: float = 0.5  # [0.0, 1.0]
    source: str = "explicit"  # explicit | inferred | observed
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    access_count: int = 0
    decay_factor: float = 0.95  # Confidence decays over time
    tags: list[str] = field(default_factory=list)

    def update_confidence(self, delta: float) -> None:
        """Update confidence with bounded adjustment."""
        self.confidence = max(0.0, min(1.0, self.confidence + delta))
        self.last_updated = time.time()

    def boost(self, amount: float = 0.1) -> None:
        """Boost confidence."""
        self.update_confidence(amount)

    def dampen(self, amount: float = 0.05) -> None:
        """Dampen confidence (preference erosion)."""
        self.update_confidence(-amount)


class PreferenceStore:
    """用户偏好存储层 — 支持 key-value 存储、置信度管理、偏好推断与注入。

    存储架构:
    - 内存索引: dict[key, PreferenceEntry] (热路径)
    - FactGraph: TripleStore持久化 (sub="user", pred=":userHasPreference", obj=json_dump)
    - HoloMemory: LTM 备份 (memory_type="user_preference")

    偏好推断策略:
    - 频率推断: 重复行为 → 偏好
    - 时近推断: 最近行为权重更高
    - 缺失推断: 回避行为 → 反向偏好
    - 显式推断: 直接声明的偏好

    偏好应用:
    - 注入到 cognition context
    - 决策加权
    - 响应个性化
    """

    DEFAULT_CONFIDENCE_THRESHOLD = 0.3  # 低于此置信度不注入
    MAX_INFERENCE_ITEMS = 1000  # 推断缓存上限
    DECAY_HALF_LIFE_DAYS = 14  # 置信度半衰期

    def __init__(
        self,
        db_path: str | None = None,
        holo_memory: Any | None = None,
        fact_graph: Any | None = None,
        provider: SQLiteRelationalProvider | None = None,
        metadata_path: str = "organs/D-Memory/organs/preference_store.py",
    ) -> None:
        self._preferences: dict[str, PreferenceEntry] = {}
        self._holo_memory = holo_memory
        self._fact_graph = fact_graph
        self._db_path = db_path
        self._provider = provider
        self._lock_fields: dict[str, bool] = {}  # key -> locked (won't be inferred-over)
        self._observation_buffer: list[tuple[str, Any, float, float]] = []  # (behavior, value, timestamp, weight)
        self._observation_max = 200
        # Inference cache
        self._inference_cache: dict[str, float] = {}  # key -> inferred_confidence
        self._cache_built_at: float = 0.0
        self._db_initialized = False

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def set(
        self,
        key: str,
        value: Any,
        confidence: float = 0.8,
        source: str = "explicit",
        tags: list[str] | None = None,
    ) -> None:
        """Store a preference.

        Args:
            key: Preference key (e.g., "theme", "communication_style", "topic_interests")
            value: Preference value (any JSON-serializable type)
            confidence: Initial confidence [0.0, 1.0]
            source: Origin of preference (explicit | inferred | observed)
            tags: Optional category tags
        """
        now = time.time()
        entry = PreferenceEntry(
            key=key,
            value=value,
            confidence=confidence,
            source=source,
            created_at=now,
            last_updated=now,
            tags=tags or [],
        )
        self._preferences[key] = entry
        self._persist_preference(entry)
        self._log(f"Preference set: {key}={value} (conf={confidence:.2f}, source={source})")

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Retrieve a preference value."""
        entry = self._preferences.get(key)
        if entry is None:
            return default
        entry.access_count += 1
        return entry.value

    def get_entry(self, key: str) -> PreferenceEntry | None:
        """Get full preference entry with metadata."""
        entry = self._preferences.get(key)
        if entry:
            entry.access_count += 1
        return entry

    def get_all(self, min_confidence: float = 0.0) -> dict[str, Any]:
        """Get all preferences filtered by minimum confidence."""
        result = {}
        for key, entry in self._preferences.items():
            if entry.confidence >= min_confidence:
                result[key] = entry.value
        return result

    def get_all_entries(self, min_confidence: float = 0.0) -> dict[str, PreferenceEntry]:
        """Get all preference entries above confidence threshold."""
        return {key: entry for key, entry in self._preferences.items() if entry.confidence >= min_confidence}

    def delete(self, key: str) -> bool:
        """Remove a preference."""
        if key in self._preferences:
            del self._preferences[key]
            self._delete_from_persistence(key)
            return True
        return False

    def lock(self, key: str) -> None:
        """Lock a preference — won't be overwritten by inference."""
        self._lock_fields[key] = True

    def unlock(self, key: str) -> None:
        """Unlock a preference — inference may update it."""
        self._lock_fields.pop(key, None)

    def is_locked(self, key: str) -> bool:
        return self._lock_fields.get(key, False)

    # ------------------------------------------------------------------
    # Preference Inference
    # ------------------------------------------------------------------

    def observe(self, behavior: str, value: Any, weight: float = 1.0) -> None:
        """Record observed behavior for preference inference.

        Args:
            behavior: Behavior identifier (becomes preference key if inferrable)
            value: Observed value or direction
            weight: Observation weight [0.0, 1.0]
        """
        self._observation_buffer.append((behavior, value, time.time(), weight))
        if len(self._observation_buffer) > self._observation_max:
            self._observation_buffer = self._observation_buffer[-self._observation_max :]
        self._invalidate_cache()

    def infer_preferences(self, min_confidence: float = 0.4) -> dict[str, PreferenceEntry]:
        """Infer new preferences from observation buffer.

        Returns dict of inferred preferences above threshold.
        """
        if not self._observation_buffer:
            return {}

        # Group by behavior
        behavior_groups: dict[str, list[tuple[Any, float, float]]] = {}
        for behavior, value, timestamp, weight in self._observation_buffer:
            if behavior not in behavior_groups:
                behavior_groups[behavior] = []
            behavior_groups[behavior].append((value, timestamp, weight))

        inferred: dict[str, PreferenceEntry] = {}
        now = time.time()

        for behavior, observations in behavior_groups.items():
            # Skip if already locked with higher confidence
            if self.is_locked(behavior):
                continue
            existing = self._preferences.get(behavior)
            if existing and existing.confidence >= 0.7:
                continue

            # Frequency score
            freq_score = min(len(observations) / 10.0, 1.0) * INFERENCE_WEIGHTS["frequency"]

            # Recency score
            most_recent = max(ts for _, ts, _ in observations)
            recency_days = (now - most_recent) / 86400.0
            recency_score = math.exp(-0.1 * recency_days) * INFERENCE_WEIGHTS["recency"]

            # Consensus score (do values agree?)
            value_counts: dict[str, int] = {}
            for val, _, _ in observations:
                v_str = json.dumps(val, sort_keys=True)
                value_counts[v_str] = value_counts.get(v_str, 0) + 1
            most_common_value = max(value_counts, key=lambda k: value_counts[k])
            consensus_ratio = max(value_counts.values()) / len(observations)
            consensus_score = consensus_ratio * 0.3

            # Combined inference confidence
            inferred_conf = freq_score + recency_score + consensus_score
            inferred_conf = min(inferred_conf, 1.0)

            if inferred_conf < min_confidence:
                continue

            # Pick the most common value
            inferred_value = json.loads(most_common_value)
            entry = PreferenceEntry(
                key=behavior,
                value=inferred_value,
                confidence=inferred_conf,
                source="inferred",
                created_at=now,
                last_updated=now,
            )
            inferred[behavior] = entry

        # Apply inferred preferences (merge with existing)
        for key, entry in inferred.items():
            existing = self._preferences.get(key)
            if existing is None:
                self._preferences[key] = entry
                self._persist_preference(entry)
            elif entry.confidence > existing.confidence:
                existing.value = entry.value
                existing.confidence = entry.confidence
                existing.source = "inferred"
                existing.last_updated = now
                self._persist_preference(existing)

        self._invalidate_cache()
        self._log(f"Inferred {len(inferred)} preferences from {len(behavior_groups)} behaviors")
        return inferred

    def apply_to_context(self, context: dict[str, Any], min_confidence: float | None = None) -> dict[str, Any]:
        """Inject preferences into a cognition context dict.

        Args:
            context: The context dict to inject preferences into
            min_confidence: Minimum confidence threshold (default: DEFAULT_CONFIDENCE_THRESHOLD)

        Returns:
            Modified context dict with "_preferences" key injected
        """
        threshold = min_confidence if min_confidence is not None else self.DEFAULT_CONFIDENCE_THRESHOLD
        entries = self.get_all_entries(min_confidence=threshold)
        pref_dict = {}
        for key, entry in entries.items():
            pref_dict[key] = {
                "value": entry.value,
                "confidence": entry.confidence,
                "source": entry.source,
            }
        context["_preferences"] = pref_dict
        return context

    # ------------------------------------------------------------------
    # Decision Injection — weight candidate options by preference match
    # ------------------------------------------------------------------

    def score_options(self, options: list[dict[str, Any]], preference_key: str) -> list[tuple[float, dict[str, Any]]]:
        """Score options by how well they match a preference.

        Args:
            options: List of option dicts (each should have an 'id' or 'name' field)
            preference_key: Which preference to use for scoring

        Returns:
            List of (score, option) tuples sorted by score descending
        """
        entry = self._preferences.get(preference_key)
        if entry is None or entry.confidence < self.DEFAULT_CONFIDENCE_THRESHOLD:
            return [(1.0, opt) for opt in options]

        pref_value = entry.value
        scored = []
        for opt in options:
            score = self._compute_match_score(opt, pref_value)
            scored.append((score * entry.confidence, opt))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    def _compute_match_score(self, option: dict[str, Any], pref_value: Any) -> float:
        """Compute how well an option matches a preference value."""
        # Direct value match
        for field_name in ["preferred_value", "value", "name", "id"]:
            if field_name in option:
                field_val = option[field_name]
                if field_val == pref_value:
                    return 1.0
                # Partial match for strings
                if isinstance(field_val, str) and isinstance(pref_value, str):
                    if pref_value.lower() in field_val.lower():
                        return 0.7
                    if field_val.lower() in pref_value.lower():
                        return 0.7
        return 0.3

    # ------------------------------------------------------------------
    # Decay & Maintenance
    # ------------------------------------------------------------------

    def decay_confidences(self) -> int:
        """Apply time-based confidence decay.

        Uses exponential decay: conf = conf * decay_factor^(days/half_life)
        Returns count of decayed entries.
        """
        now = time.time()
        decayed = 0
        for _key, entry in self._preferences.items():
            if entry.source == "explicit":
                continue  # Don't decay explicit preferences
            days_elapsed = (now - entry.last_updated) / 86400.0
            decay = math.pow(self.DECAY_HALF_LIFE_DAYS, -days_elapsed / self.DECAY_HALF_LIFE_DAYS)
            new_conf = entry.confidence * decay
            if abs(new_conf - entry.confidence) > 0.001:
                entry.confidence = max(0.0, new_conf)
                decayed += 1
                self._persist_preference(entry)
        if decayed > 0:
            self._invalidate_cache()
        return decayed

    def get_stats(self) -> dict[str, Any]:
        """Return preference store statistics."""
        total = len(self._preferences)
        if total == 0:
            return {
                "total": 0,
                "by_source": {},
                "avg_confidence": 0.0,
                "locked": 0,
                "observations": len(self._observation_buffer),
            }
        by_source: dict[str, int] = {}
        conf_sum = 0.0
        for entry in self._preferences.values():
            by_source[entry.source] = by_source.get(entry.source, 0) + 1
            conf_sum += entry.confidence
        return {
            "total": total,
            "by_source": by_source,
            "avg_confidence": round(conf_sum / total, 3),
            "locked": sum(1 for k in self._lock_fields if self._lock_fields[k]),
            "observations": len(self._observation_buffer),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _get_provider(self) -> SQLiteRelationalProvider | None:
        """Get or create the SQLiteRelationalProvider instance."""
        if self._provider is not None:
            return self._provider
        if self._db_path is None:
            return None
        self._provider = SQLiteRelationalProvider(self._db_path)
        return self._provider

    def _init_db(self) -> None:
        """Initialize the SQLite preference table."""
        if self._db_initialized or self._db_path is None:
            return
        try:
            provider = self._get_provider()
            if provider is None:
                return
            provider.execute(
                """
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    source TEXT NOT NULL DEFAULT 'explicit',
                    created_at REAL NOT NULL,
                    last_updated REAL NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    decay_factor REAL NOT NULL DEFAULT 0.95,
                    tags TEXT NOT NULL DEFAULT '[]',
                    locked INTEGER NOT NULL DEFAULT 0
                )
            """
            )
            provider.execute("CREATE INDEX IF NOT EXISTS idx_pref_confidence ON preferences(confidence)")
            self._db_initialized = True
        except (ImportError, OSError, SQLiteError) as e:
            _log.warning("[PreferenceStore] DB init failed (non-fatal): %s", e)

    def _persist_preference(self, entry: PreferenceEntry) -> None:
        """Persist a preference entry to SQLite and FactGraph."""
        self._init_db()

        # SQLite persistence
        provider = self._get_provider()
        if provider is not None:
            try:
                provider.execute_write(
                    """
                    INSERT OR REPLACE INTO preferences
                    (key, value, confidence, source, created_at, last_updated, access_count, decay_factor, tags, locked)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.key,
                        json.dumps(entry.value),
                        entry.confidence,
                        entry.source,
                        entry.created_at,
                        entry.last_updated,
                        entry.access_count,
                        entry.decay_factor,
                        json.dumps(entry.tags),
                        1 if self.is_locked(entry.key) else 0,
                    ),
                )
            except (ImportError, OSError, SQLiteError) as e:
                _log.debug("[PreferenceStore] SQLite persist failed: %s", e)

        # FactGraph persistence (Triple-based)
        if self._fact_graph is not None:
            try:
                obj_data = {
                    "key": entry.key,
                    "value": entry.value,
                    "confidence": entry.confidence,
                    "source": entry.source,
                }
                self._fact_graph.add_fact("user", PRED_HAS_PREFERENCE, json.dumps(obj_data))
            except (AttributeError, TypeError) as e:
                _log.debug("[PreferenceStore] FactGraph persist failed: %s", e)

        # Also store in HoloMemory for LTM backup
        if self._holo_memory is not None:
            try:
                self._holo_memory.wm_store(
                    key=f"pref:{entry.key}",
                    value=json.dumps(
                        {
                            "key": entry.key,
                            "value": entry.value,
                            "confidence": entry.confidence,
                            "source": entry.source,
                        }
                    ),
                    importance=entry.confidence,
                    sacred=False,
                    auto_consolidate=True,
                    memory_type="user_preference",
                )
            except (AttributeError, TypeError) as e:
                _log.debug("[PreferenceStore] HoloMemory persist failed: %s", e)

    def _delete_from_persistence(self, key: str) -> None:
        """Remove preference from all persistence layers."""
        provider = self._get_provider()
        if provider is not None:
            try:
                provider.execute_write("DELETE FROM preferences WHERE key = ?", (key,))
            except (ImportError, OSError, SQLiteError):
                pass

    def load_from_db(self) -> int:
        """Load preferences from SQLite on startup."""
        self._init_db()
        loaded = 0
        provider = self._get_provider()
        if provider is not None:
            try:
                rows = provider.fetch_all("SELECT * FROM preferences")
                for row in rows:
                    entry = PreferenceEntry(
                        key=row["key"],
                        value=json.loads(row["value"]),
                        confidence=row["confidence"],
                        source=row["source"],
                        created_at=row["created_at"],
                        last_updated=row["last_updated"],
                        access_count=row["access_count"],
                        decay_factor=row["decay_factor"],
                        tags=json.loads(row["tags"]),
                    )
                    self._preferences[row["key"]] = entry
                    if row["locked"]:
                        self._lock_fields[row["key"]] = True
                    loaded += 1
                self._log(f"Loaded {loaded} preferences from database")
            except (ImportError, OSError, SQLiteError, json.JSONDecodeError) as e:
                _log.warning("[PreferenceStore] Load from DB failed: %s", e)
        return loaded

    def _invalidate_cache(self) -> None:
        self._inference_cache.clear()
        self._cache_built_at = 0.0

    def _log(self, message: str) -> None:
        _log.info("[PreferenceStore] %s", message)

    def validate_internal_state(self) -> bool:
        """Validate internal consistency."""
        for key, entry in self._preferences.items():
            if not (0.0 <= entry.confidence <= 1.0):
                _log.warning("[PreferenceStore] Invalid confidence for %s: %s", key, entry.confidence)
                return False
            if entry.key != key:
                _log.warning("[PreferenceStore] Key mismatch: %s vs %s", entry.key, key)
                return False
        return True


# ── Convenience singleton ──────────────────────────────────────────────
_preference_store_singleton: PreferenceStore | None = None


def get_preference_store(
    db_path: str | None = None,
    holo_memory: Any | None = None,
    fact_graph: Any | None = None,
    provider: SQLiteRelationalProvider | None = None,
) -> PreferenceStore:
    """Get the global PreferenceStore singleton."""
    global _preference_store_singleton
    if _preference_store_singleton is None:
        _preference_store_singleton = PreferenceStore(
            db_path=db_path, holo_memory=holo_memory, fact_graph=fact_graph, provider=provider
        )
        _preference_store_singleton.load_from_db()
    return _preference_store_singleton
