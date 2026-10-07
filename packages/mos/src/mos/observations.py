"""ADR-0464 blind spot 1 — inert-by-default observability seam.

Records, in an append-only JSONL observation file, the fact that the Memory OS
control plane executed a REAL (non-fixture) recall under the current env, so a
gate can later assert "under default configuration, has this capability actually
executed?" instead of trusting registry markers like `status: phase10`.

Design rules (repo AGENTS.md §7 lessons; ADR-0464 decision):
- Telemetry, NOT policy: recording an observation never changes recall behavior.
- Fail SOFT: any exception inside the seam is swallowed; recall never breaks.
- Resolved at CALL TIME, never import time: the write root mirrors
  bin/lib/repo_root.py env precedence (OMOSTATION_STATE_ROOT → ECOS_WORKSPACE /
  WORKSPACE_ROOT → marker walk for docs/project-registry.yaml). kairon is a
  submodule and cannot import the parent's bin/lib, so this mirrors the same
  contract; the parent gate reads the same file via repo_root.state_root().
- Only REAL executions append. `data_mode == "fixture"` writes NOTHING — absence
  of a record IS the honest signal ("no real execution observed yet"). Writing a
  `last_real_execution: null` on every fixture recall would create unbounded
  writes, so we deliberately do not.
- Rate/watermark policy: at most one record per MOS_SEAM_MIN_INTERVAL seconds
  (default 300), enforced by comparing the last record's ts. Idempotent and
  cheap — bounded even if recall is hammered.

Record shape (one JSON object per line):
  {"kind": "mos.real_execution", "ts": "<ISO-8601 UTC>", "data_mode": "live",
   "live_backends": ["kos"], "default_env": true, "source": "recall"}
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OBSERVATIONS_REL = Path("runtime") / "mos" / "observations.jsonl"
OBSERVATIONS_PATH_ENV = "MOS_OBSERVATIONS_PATH"
MIN_INTERVAL_ENV = "MOS_SEAM_MIN_INTERVAL"
DEFAULT_MIN_INTERVAL_SECONDS = 300.0
MARKER = Path("docs") / "project-registry.yaml"

KIND = "mos.real_execution"
SCHEMA = "mos/execution-observation/v1"


def _flag_seconds(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _marker_walk(start: Path) -> Path | None:
    """Walk up from start to the workspace marker (same as repo_root.MARKER)."""
    for parent in [start, *start.parents]:
        if (parent / MARKER).is_file():
            return parent
    return None


def observation_path() -> Path | None:
    """Resolve the observation file path AT CALL TIME (never a module constant).

    Precedence mirrors bin/lib/repo_root.py:
      1. MOS_OBSERVATIONS_PATH (explicit override — hermetic tests / operators)
      2. OMOSTATION_STATE_ROOT → <state-root>/runtime/mos/observations.jsonl
      3. ECOS_WORKSPACE / WORKSPACE_ROOT → <workspace>/runtime/mos/observations.jsonl
      4. marker walk from this file (docs/project-registry.yaml found)
    Returns None when no root is resolvable — the seam then writes nothing.
    """
    explicit = os.environ.get(OBSERVATIONS_PATH_ENV)
    if explicit:
        return Path(explicit).expanduser().absolute()

    state_root = os.environ.get("OMOSTATION_STATE_ROOT")
    if state_root:
        return Path(state_root).expanduser().absolute() / OBSERVATIONS_REL

    for var in ("ECOS_WORKSPACE", "WORKSPACE_ROOT"):
        ws = os.environ.get(var)
        if ws:
            return Path(ws).expanduser().absolute() / OBSERVATIONS_REL

    root = _marker_walk(Path(__file__).resolve())
    if root is not None:
        return root / OBSERVATIONS_REL
    return None


def _last_line(path: Path) -> str:
    """Return the last non-empty line, or empty string."""
    try:
        with path.open(encoding="utf-8") as fh:
            lines = [ln for ln in (line.strip() for line in fh) if ln]
        return lines[-1] if lines else ""
    except OSError:
        return ""


def _last_record_ts(path: Path) -> float:
    line = _last_line(path)
    if not line:
        return 0.0
    try:
        record = json.loads(line)
        ts = str(record.get("ts") or "")
        if not ts:
            return 0.0
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except (json.JSONDecodeError, ValueError):
        return 0.0


def record_real_execution(
    data_mode: str,
    live_backends: list[str],
    *,
    source: str = "recall",
    intent: str | None = None,
    default_env: bool | None = None,
) -> bool:
    """Append one observation if (and only if) a REAL execution is proven.

    Returns True when a record was written, False when skipped (fixture-only,
    rate-limited, or no resolvable root). Never raises.
    """
    try:
        if data_mode not in ("live", "mixed") or not live_backends:
            return False
        path = observation_path()
        if path is None:
            return False
        interval = _flag_seconds(MIN_INTERVAL_ENV, DEFAULT_MIN_INTERVAL_SECONDS)
        last_ts = _last_record_ts(path)
        if interval > 0 and last_ts and (time.time() - last_ts) < interval:
            return False
        if default_env is None:
            default_env = not any(
                (os.environ.get(k) or "").strip().lower() not in {"", "0", "false", "off", "no"}
                for k in ("MOS_LIVE_KOS", "MOS_LIVE_GBRAIN", "MOS_LIVE_GBRAIN_WRITE")
            )
        record: dict[str, Any] = {
            "schema": SCHEMA,
            "kind": KIND,
            "ts": _utc_now(),
            "data_mode": data_mode,
            "live_backends": sorted(live_backends),
            "default_env": bool(default_env),
            "source": source,
        }
        if intent:
            record["intent"] = intent
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return True
    except Exception:
        # Fail SOFT: a seam failure must never break recall.
        return False


def latest_observation(path: Path | None = None) -> dict[str, Any] | None:
    """Read the latest observation record; None when absent/unreadable.

    Used by tests and by the parent-repo gate to assert on the watermark.
    """
    target = path or observation_path()
    if target is None or not target.is_file():
        return None
    line = _last_line(target)
    if not line:
        return None
    try:
        record = json.loads(line)
        return record if isinstance(record, dict) else None
    except json.JSONDecodeError:
        return None
