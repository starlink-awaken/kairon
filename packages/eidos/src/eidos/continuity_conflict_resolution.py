from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Summary: Multi-end conflict resolution (LWW, CRDT merge, and manual arbitration)
Authority: organs/D-Continuity/AGENTS.md
---

"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Conflict Resolution ≡ Module
# 内涵 ≝ {Conflict, Resolution}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ConflictResolution)}
# 功能 ⊢ {Conflict_Resolution, Init_Conflict, Validate_Resolution}
# =============================================================================


import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from threading import Lock
from typing import Any, cast

_log = logging.getLogger(__name__)


class ResolutionStrategy(Enum):
    LAST_WRITE_WINS = "last_write_wins"
    CRDT_MERGE = "crdt_merge"
    MANUAL_ARBITRATION = "manual_arbitration"


class ConflictSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ConflictRecord:
    conflict_id: str
    entity_type: str
    entity_id: str
    strategy_used: str
    winner_id: str | None
    loser_id: str | None
    resolution: str
    created_at: str
    resolved_at: str | None
    severity: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConflictRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ConflictEntry:
    conflict_id: str
    entity_type: str
    entity_id: str
    versions: list[dict[str, Any]]
    timestamp: str
    resolution: str
    resolved: bool = False
    resolution_value: Any = None


# === Real CRDT Implementations ===


@dataclass
class VectorClock:
    """Vector clock for causal ordering across devices."""

    clock: dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str) -> None:
        self.clock[node_id] = self.clock.get(node_id, 0) + 1

    def merge(self, other: VectorClock) -> VectorClock:
        merged = VectorClock()
        all_nodes = set(self.clock.keys()) | set(other.clock.keys())
        for node in all_nodes:
            merged.clock[node] = max(self.clock.get(node, 0), other.clock.get(node, 0))
        return merged

    def happens_before(self, other: VectorClock) -> bool:
        """Returns True if self happened-before other (strict partial order)."""
        dominates = False
        for node in set(self.clock.keys()) | set(other.clock.keys()):
            s_val = self.clock.get(node, 0)
            o_val = other.clock.get(node, 0)
            if s_val > o_val:
                return False
            if s_val < o_val:
                dominates = True
        return dominates and (self.clock != other.clock)


@dataclass
class LWWRegister:
    """Last-Writer-Wins Register CRDT."""

    key: str
    value: Any = None
    timestamp: float = 0.0
    node_id: str = ""

    def merge(self, other: LWWRegister) -> LWWRegister:
        if not isinstance(other, LWWRegister):
            return self
        if other.timestamp > self.timestamp:
            return other
        if other.timestamp == self.timestamp and other.node_id > self.node_id:
            return other
        return self


@dataclass
class ORSet:
    """Observed-Remove Set CRDT for collaborative lists."""

    key: str
    items: dict[str, Any] = field(default_factory=dict)  # tag -> value

    def add(self, item: str) -> None:
        tag = f"{item}_{time.time_ns()}"
        self.items[tag] = item

    def remove(self, item: str) -> None:
        to_remove = [tag for tag, v in self.items.items() if v == item]
        for tag in to_remove:
            del self.items[tag]

    def merge(self, other: ORSet) -> ORSet:
        if not isinstance(other, ORSet):
            return self
        merged = ORSet(key=self.key, items=dict(self.items))
        for tag, value in other.items.items():
            if tag not in merged.items:
                merged.items[tag] = value
        return merged


class ConflictResolution:
    """
    Multi-end conflict resolution engine.

    Strategies:
    1. LAST_WRITE_WINS - timestamp-based, deterministic
    2. CRDT_MERGE - merge concurrent changes using vector clocks
    3. MANUAL_ARBITRATION - flag for human resolution

    All conflicts are recorded in an in-memory history ring buffer.
    """

    DEFAULT_MAX_HISTORY = 1000

    def __init__(
        self,
        strategy: ResolutionStrategy = ResolutionStrategy.LAST_WRITE_WINS,
        max_history: int = DEFAULT_MAX_HISTORY,
        history_path: str | None = None,
    ) -> None:
        self.metadata_path = "eidos/continuity_conflict_resolution.py"
        self.organ_name = "continuity_conflict_resolution"
        self.organ_id = f"eidos-{id(self):x}"
        self._status = "active"
        self._metabolic_budget = 1000.0
        self._strategy = strategy
        self._max_history = max_history
        self._history_path = history_path
        self._lock = Lock()
        self._history: list[ConflictRecord] = []
        self._pending: dict[str, ConflictEntry] = {}
        self._load_history()

    def set_strategy(self, strategy: ResolutionStrategy) -> None:
        with self._lock:
            old = self._strategy
            self._strategy = strategy
            _log.info("Conflict strategy changed: %s -> %s", old.value, strategy.value)

    def get_strategy(self) -> ResolutionStrategy:
        with self._lock:
            return self._strategy

    def resolve(
        self,
        entity_type: str,
        entity_id: str,
        versions: list[dict[str, Any]],
        force_strategy: ResolutionStrategy | None = None,
    ) -> dict[str, Any]:
        strategy = force_strategy or self._strategy
        now = datetime.now(UTC).isoformat()
        conflict_id = str(uuid.uuid4())

        if len(versions) <= 1:
            winner = versions[0] if versions else None
            return {
                "conflict_id": conflict_id,
                "strategy": strategy.value,
                "resolution": "winner",
                "winner": winner,
                "merged": None,
                "pending": False,
            }

        if strategy == ResolutionStrategy.LAST_WRITE_WINS:
            result = self._resolve_lww(versions)
        elif strategy == ResolutionStrategy.CRDT_MERGE:
            result = self._resolve_crdt(versions)
        else:
            result = self._resolve_manual()

        entry = ConflictEntry(
            conflict_id=conflict_id,
            entity_type=entity_type,
            entity_id=entity_id,
            versions=versions,
            timestamp=now,
            resolution=result["resolution"],
            resolved=result["pending"] is False,
            resolution_value=result.get("winner") or result.get("merged"),
        )
        with self._lock:
            self._pending[conflict_id] = entry

        self._record_conflict(
            conflict_id=conflict_id,
            entity_type=entity_type,
            entity_id=entity_id,
            winner_id=result.get("winner", {}).get("device_id") or result.get("winner", {}).get("source_node_id"),
            loser_id=self._find_loser(versions, result.get("winner")),
            strategy_used=strategy.value,
            resolution=result["resolution"],
            severity=self._assess_severity(versions),
            details={"version_count": len(versions)},
        )

        return {
            "conflict_id": conflict_id,
            "strategy": strategy.value,
            "resolution": result["resolution"],
            "winner": result.get("winner"),
            "merged": result.get("merged"),
            "pending": result["pending"],
        }

    def resolve_fact_triple(
        self,
        sub: str,
        pred: str,
        obj: str,
        remote_versions: list[dict[str, Any]],
        local_version: dict[str, Any] | None,
    ) -> dict[str, Any]:
        all_versions = remote_versions if local_version is None else remote_versions + [local_version]

        if len(all_versions) <= 1:
            return {
                "apply": bool(all_versions),
                "fact": all_versions[0] if all_versions else None,
                "strategy": "singleton",
            }

        def sort_key(v: dict[str, Any]) -> tuple:
            vc = v.get("vector_clock", {})
            return (
                sum(vc.values()),
                v.get("lamport_clock", 0),
                v.get("importance", 1.0),
                str(v.get("source_node_id", "")),
            )

        sorted_versions = sorted(all_versions, key=sort_key, reverse=True)
        winner = sorted_versions[0]

        self._record_conflict(
            conflict_id=str(uuid.uuid4()),
            entity_type="fact_triple",
            entity_id=f"{sub}|{pred}|{obj}",
            winner_id=winner.get("source_node_id"),
            loser_id=sorted_versions[1].get("source_node_id") if len(sorted_versions) > 1 else None,
            strategy_used="crdt_priority",
            resolution="winner",
            severity=self._assess_severity(all_versions),
            details={
                "sub": sub,
                "pred": pred,
                "obj": obj,
                "winner_vc": winner.get("vector_clock", {}),
                "lamport_winner": winner.get("lamport_clock", 0),
            },
        )

        return {
            "apply": True,
            "fact": winner,
            "strategy": "crdt_priority",
            "conflict_count": len(all_versions) - 1,
        }

    def resolve_session_state(
        self,
        session_id: str,
        device_versions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not device_versions:
            return {"apply": False, "reason": "no_versions"}

        def get_ts(v: dict[str, Any]) -> float:
            raw = v.get("last_active", "1970-01-01T00:00:00+00:00")
            try:
                return datetime.fromisoformat(raw).timestamp()
            except (ValueError, TypeError):
                return 0.0

        winner = max(device_versions, key=get_ts)
        conflict_id = str(uuid.uuid4())
        losers = [v for v in device_versions if v.get("device_id") != winner.get("device_id")]

        self._record_conflict(
            conflict_id=conflict_id,
            entity_type="session_state",
            entity_id=session_id,
            winner_id=winner.get("device_id"),
            loser_id=losers[0].get("device_id") if losers else None,
            strategy_used="last_write_wins",
            resolution="winner",
            severity="low",
            details={
                "device_count": len(device_versions),
                "winner_last_active": winner.get("last_active"),
            },
        )

        return {
            "apply": True,
            "winner": winner,
            "conflict_id": conflict_id,
            "strategy": "last_write_wins",
            "device_count": len(device_versions),
        }

    def _resolve_lww(self, versions: list[dict[str, Any]]) -> dict[str, Any]:
        def ts(v: dict[str, Any]) -> float:
            raw = v.get("updated_at") or v.get("timestamp") or 0
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
            except (ValueError, AttributeError, TypeError):
                try:
                    return float(raw)
                except (ValueError, TypeError):
                    return 0.0

        winner = max(versions, key=ts)
        return {"resolution": "winner", "winner": winner, "merged": None, "pending": False}

    def _resolve_crdt(self, versions: list[dict[str, Any]]) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        latest_ts: dict[str, float] = {}

        for version in versions:
            data = version.get("data", {})
            ts_raw = version.get("updated_at", version.get("timestamp", 0))
            try:
                ts_val = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError):
                ts_val = float(ts_raw or 0)

            for key, value in data.items():
                if key not in latest_ts or ts_val > latest_ts[key]:
                    merged[key] = value
                    latest_ts[key] = ts_val

            for key, value in version.get("metadata", {}).items():
                meta_key = f"_meta_{key}"
                if meta_key not in latest_ts or ts_val > latest_ts[meta_key]:
                    if meta_key not in merged:
                        merged[meta_key] = {}
                    merged[meta_key][key] = value
                    latest_ts[meta_key] = ts_val

        winner = versions[-1] if versions else {}
        return {"resolution": "merged", "winner": winner, "merged": merged, "pending": False}

    def _resolve_manual(self) -> dict[str, Any]:
        return {"resolution": "pending_arbitration", "winner": None, "merged": None, "pending": True}

    def list_pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "conflict_id": e.conflict_id,
                    "entity_type": e.entity_type,
                    "entity_id": e.entity_id,
                    "version_count": len(e.versions),
                    "created_at": e.timestamp,
                    "versions": e.versions,
                }
                for e in self._pending.values()
                if not e.resolved
            ]

    def resolve_manual(
        self,
        conflict_id: str,
        chosen_version: dict[str, Any],
    ) -> bool:
        with self._lock:
            if conflict_id not in self._pending:
                return False
            entry = self._pending[conflict_id]
            if entry.resolved:
                return False

            entry.resolved = True
            entry.resolution_value = chosen_version
            entry.resolution = "manual"

            self._record_conflict(
                conflict_id=conflict_id,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                winner_id=chosen_version.get("device_id") or chosen_version.get("source_node_id"),
                loser_id=None,
                strategy_used="manual_arbitration",
                resolution="manual",
                severity="medium",
                details={"chosen_by": "human"},
            )

            _log.info("Manual arbitration resolved: %s -> %s", conflict_id, entry.entity_id)
            return True

    def dismiss_pending(self, conflict_id: str) -> bool:
        with self._lock:
            if conflict_id not in self._pending:
                return False
            entry = self._pending[conflict_id]
            if entry.resolved:
                return False
            entry.resolved = True
            entry.resolution = "dismissed"
            return True

    def get_history(
        self,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[ConflictRecord]:
        with self._lock:
            records = self._history
            if entity_type:
                records = [r for r in records if r.entity_type == entity_type]
            return list(reversed(records))[:limit]

    def get_conflict_stats(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._history)
            pending = sum(1 for e in self._pending.values() if not e.resolved)
            by_strategy: dict[str, int] = {}
            by_entity: dict[str, int] = {}
            by_severity: dict[str, int] = {}
            for r in self._history:
                by_strategy[r.strategy_used] = by_strategy.get(r.strategy_used, 0) + 1
                by_entity[r.entity_type] = by_entity.get(r.entity_type, 0) + 1
                by_severity[r.severity] = by_severity.get(r.severity, 0) + 1

            return {
                "total_conflicts": total,
                "pending_arbitration": pending,
                "strategy_distribution": by_strategy,
                "entity_distribution": by_entity,
                "severity_distribution": by_severity,
                "current_strategy": self._strategy.value,
            }

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()
        _log.info("Conflict history cleared")

    def _record_conflict(
        self,
        conflict_id: str,
        entity_type: str,
        entity_id: str,
        winner_id: str | None,
        loser_id: str | None,
        strategy_used: str,
        resolution: str,
        severity: str,
        details: dict[str, Any],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        record = ConflictRecord(
            conflict_id=conflict_id,
            entity_type=entity_type,
            entity_id=entity_id,
            strategy_used=strategy_used,
            winner_id=winner_id,
            loser_id=loser_id,
            resolution=resolution,
            created_at=now,
            resolved_at=now,
            severity=severity,
            details=details,
        )
        with self._lock:
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]
        self._save_history()

    def _assess_severity(self, versions: list[dict[str, Any]]) -> str:
        if len(versions) >= 5:
            return "critical"
        if len(versions) >= 3:
            return "high"
        if len(versions) == 2:
            data0 = versions[0].get("data", {})
            data1 = versions[1].get("data", {})
            if data0 and data1 and set(data0.keys()) != set(data1.keys()):
                return "medium"
            return "low"
        return "low"

    def _find_loser(
        self,
        versions: list[dict[str, Any]],
        winner: dict[str, Any] | None,
    ) -> str | None:
        if winner is None or len(versions) < 2:
            return None
        winner_id = winner.get("device_id") or winner.get("source_node_id")
        for v in versions:
            vid = v.get("device_id") or v.get("source_node_id")
            if vid and vid != winner_id:
                return cast("str | None", vid)
        return None

    def _load_history(self) -> None:
        if not self._history_path:
            return
        try:
            from pathlib import Path

            path = Path(self._history_path)
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                self._history = [ConflictRecord.from_dict(r) for r in raw]
                _log.info("Conflict history loaded: %d records", len(self._history))
        except (json.JSONDecodeError, OSError, KeyError) as e:
            _log.warning("Failed to load conflict history: %s", e)

    def _save_history(self) -> None:
        if not self._history_path:
            return
        try:
            from pathlib import Path

            path = Path(self._history_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps([r.to_dict() for r in self._history], indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            _log.warning("Failed to save conflict history: %s", e)


__all__ = [
    "ConflictResolution",
    "ResolutionStrategy",
    "ConflictSeverity",
    "ConflictRecord",
    "ConflictEntry",
    "VectorClock",
    "LWWRegister",
    "ORSet",
]
