from __future__ import annotations

"""Threat Detection with Welford online Z-score anomaly detection.

Based on D_Immunity: immunity_guard.py + behavioral_fingerprint.py.
5-level threat: TL0_OK -> TL1_WATCH -> TL2_WARN -> TL3_FREEZE -> TL4_MELTDOWN -> TL5_QUARANTINE.
Auto-freeze at TL3, auto-quarantine at TL5.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from math import sqrt
from typing import Any
from collections.abc import Callable

_log = logging.getLogger(__name__)

WARMUP_SAMPLES: int = 10
WINDOW_SECONDS: int = 60
Z_SCORE_THRESHOLD: float = 3.0
ANOMALY_STRIKES_TO_FREEZE: int = 3
ANOMALY_STRIKES_TO_QUARANTINE: int = 10


class ThreatLevel(IntEnum):
    """5-level threat severity scale."""

    TL0_OK = 0
    TL1_WATCH = 1
    TL2_WARN = 2
    TL3_FREEZE = 3
    TL4_MELTDOWN = 4
    TL5_QUARANTINE = 5

    @property
    def label(self) -> str:
        return {0: "OK", 1: "WATCH", 2: "WARN", 3: "FREEZE", 4: "MELTDOWN", 5: "QUARANTINE"}.get(self.value, "UNKNOWN")

    @classmethod
    def from_z_score(cls, z_score: float, strikes: int) -> ThreatLevel:
        abs_z = abs(z_score)
        if abs_z < 1.5:
            return cls.TL0_OK
        if abs_z < 2.5:
            return cls.TL1_WATCH
        if abs_z < Z_SCORE_THRESHOLD:
            return cls.TL2_WARN
        if strikes < ANOMALY_STRIKES_TO_FREEZE:
            return cls.TL2_WARN
        if strikes < ANOMALY_STRIKES_TO_QUARANTINE:
            return cls.TL3_FREEZE
        if abs_z < 5.0:
            return cls.TL4_MELTDOWN
        return cls.TL5_QUARANTINE


@dataclass
class AgentFingerprint:
    """Per-agent behavioral fingerprint with Welford online statistics."""

    agent_id: str
    call_history: list[float] = field(default_factory=list)
    mean_rate: float = 0.0
    stddev_rate: float = 0.0
    sample_count: int = 0
    last_updated: float = field(default_factory=time.time)
    anomaly_strikes: int = 0
    is_frozen: bool = False
    is_quarantined: bool = False
    threat_level: ThreatLevel = ThreatLevel.TL0_OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "mean_rate": round(self.mean_rate, 4),
            "stddev_rate": round(self.stddev_rate, 4),
            "sample_count": self.sample_count,
            "anomaly_strikes": self.anomaly_strikes,
            "is_frozen": self.is_frozen,
            "is_quarantined": self.is_quarantined,
            "threat_level": self.threat_level.label,
        }


class ThreatDetector:
    """Threat detection engine — Welford online Z-score with auto-freeze/quarantine.

        detector = ThreatDetector()
        status = detector.update("agent-1")  # "LEARNING" | "OK" | "WARN" | "FROZEN" | "QUARANTINED"
    """

    def __init__(self) -> None:
        self._fingerprints: dict[str, AgentFingerprint] = {}
        self._freeze_cbs: list[Callable[[str, str, dict[str, Any]], Any]] = []
        self._quarantine_cbs: list[Callable[[str, str, dict[str, Any]], Any]] = []

    def update(self, agent_id: str) -> str:
        """Record a call and return behavioral status."""
        if not agent_id:
            return "OK"

        now = time.time()
        fp = self._fingerprints.setdefault(agent_id, AgentFingerprint(agent_id=agent_id))

        if fp.is_quarantined:
            return "QUARANTINED"
        if fp.is_frozen:
            return "FROZEN"

        fp.call_history.append(now)
        if len(fp.call_history) > 1000:
            fp.call_history = fp.call_history[-1000:]
        fp.last_updated = now

        cutoff = now - WINDOW_SECONDS
        window_calls = sum(1 for t in fp.call_history if t >= cutoff)
        current_rate = window_calls / (WINDOW_SECONDS / 60.0)

        if fp.sample_count < WARMUP_SAMPLES:
            self._welford_update(fp, current_rate)
            return "LEARNING"

        z = self._compute_z(fp, current_rate)
        self._welford_update(fp, current_rate)

        if abs(z) > Z_SCORE_THRESHOLD:
            fp.anomaly_strikes += 1
            _log.warning("Anomaly: agent=%s z=%.2f strikes=%d", agent_id, z, fp.anomaly_strikes)
        else:
            fp.anomaly_strikes = max(0, fp.anomaly_strikes - 1)

        tl = ThreatLevel.from_z_score(z, fp.anomaly_strikes)
        fp.threat_level = tl

        if tl >= ThreatLevel.TL3_FREEZE and not fp.is_frozen:
            fp.is_frozen = True
            _log.warning("Auto-freeze: agent=%s threat=%s", agent_id, tl.label)
            for cb in self._freeze_cbs:
                try:
                    cb(agent_id, tl.label, fp.to_dict())
                except Exception as exc:
                    _log.error("Freeze callback failed: %s", exc)

        if tl >= ThreatLevel.TL5_QUARANTINE and not fp.is_quarantined:
            fp.is_quarantined = True
            _log.error("Auto-quarantine: agent=%s threat=%s", agent_id, tl.label)
            for cb in self._quarantine_cbs:
                try:
                    cb(agent_id, tl.label, fp.to_dict())
                except Exception as exc:
                    _log.error("Quarantine callback failed: %s", exc)

        if fp.is_quarantined:
            return "QUARANTINED"
        if fp.is_frozen:
            return "FROZEN"
        if tl >= ThreatLevel.TL2_WARN:
            return "WARN"
        if tl >= ThreatLevel.TL1_WATCH:
            return "WATCH"
        return "OK"

    def get_fingerprint(self, agent_id: str) -> AgentFingerprint | None:
        return self._fingerprints.get(agent_id)

    def get_status(self) -> dict[str, dict[str, Any]]:
        return {aid: fp.to_dict() for aid, fp in self._fingerprints.items()}

    def unfreeze(self, agent_id: str) -> bool:
        fp = self._fingerprints.get(agent_id)
        if fp is None:
            return False
        fp.is_frozen = False
        fp.anomaly_strikes = 0
        fp.threat_level = ThreatLevel.TL0_OK
        _log.info("Agent %s unfrozen", agent_id)
        return True

    def release_from_quarantine(self, agent_id: str) -> bool:
        fp = self._fingerprints.get(agent_id)
        if fp is None:
            return False
        fp.is_quarantined = False
        fp.is_frozen = False
        fp.anomaly_strikes = 0
        fp.threat_level = ThreatLevel.TL0_OK
        _log.info("Agent %s released from quarantine", agent_id)
        return True

    def on_freeze(self, callback: Callable[[str, str, dict[str, Any]], Any]) -> None:
        self._freeze_cbs.append(callback)

    def on_quarantine(self, callback: Callable[[str, str, dict[str, Any]], Any]) -> None:
        self._quarantine_cbs.append(callback)

    @staticmethod
    def _welford_update(fp: AgentFingerprint, current_rate: float) -> None:
        """Welford's online algorithm — update mean and stddev in one pass."""
        n = fp.sample_count + 1
        delta = current_rate - fp.mean_rate
        fp.mean_rate += delta / n
        delta2 = current_rate - fp.mean_rate
        fp.stddev_rate = sqrt((fp.stddev_rate**2 * (n - 1) + delta * delta2) / n)
        fp.sample_count = n

    @staticmethod
    def _compute_z(fp: AgentFingerprint, current_rate: float) -> float:
        if fp.stddev_rate == 0.0:
            return 0.0
        return (current_rate - fp.mean_rate) / fp.stddev_rate


__all__ = [
    "AgentFingerprint", "ThreatDetector", "ThreatLevel",
    "WARMUP_SAMPLES", "WINDOW_SECONDS", "Z_SCORE_THRESHOLD",
]
