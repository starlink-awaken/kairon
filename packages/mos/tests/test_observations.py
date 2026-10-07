"""ADR-0464 blind spot 1 — observability seam contract.

The seam must observe REAL (non-fixture) executions and stay silent on
fixture-only runs. These tests are the mutation proof: force a live backend and
assert the signal appears; run only fixtures and assert nothing is claimed.
"""

from __future__ import annotations

import json
from pathlib import Path

from mos.adapters.live_backends import LiveKosSearchBackend
from mos.envelope import validate_envelope
from mos.neo4j_writer import Neo4jSearchBackend
from mos.observations import observation_path, record_real_execution
from mos.persist import FileStore
from mos.service import MemoryOS


class _Writer:
    def __init__(self, available: bool) -> None:
        self._available = available

    def available(self) -> bool:
        return self._available


def _live_kos() -> LiveKosSearchBackend:
    return LiveKosSearchBackend(http_get=lambda path, params: [{"id": "1", "title": "t", "snippet": "s"}])


def test_fixture_only_recall_writes_nothing(monkeypatch, tmp_path):
    """Mutation proof: fixture-only execution must NOT claim success."""
    obs = tmp_path / "observations.jsonl"
    monkeypatch.setenv("MOS_OBSERVATIONS_PATH", str(obs))
    monkeypatch.delenv("MOS_LIVE_KOS", raising=False)
    monkeypatch.delenv("MOS_LIVE_GBRAIN", raising=False)
    monkeypatch.delenv("NEO4J_URI", raising=False)

    mos = MemoryOS()
    rec = mos.recall("hello world")
    assert rec.data_mode == "fixture"
    assert not obs.exists(), "a fixture-only recall must not write an observation"


def test_real_execution_is_observed(monkeypatch, tmp_path):
    """When a real backend serves the recall, the seam records it."""
    obs = tmp_path / "observations.jsonl"
    monkeypatch.setenv("MOS_OBSERVATIONS_PATH", str(obs))
    monkeypatch.setenv("MOS_LIVE_KOS", "1")

    live = LiveKosSearchBackend(http_get=lambda path, params: [{"id": "1", "title": "t", "snippet": "s"}])
    mos = MemoryOS(search_backends={"kos": live})
    rec = mos.recall("anything", intent="file_note")
    assert rec.data_mode == "live"
    assert rec.live_backends == ["kos"]

    assert obs.is_file()
    record = json.loads(obs.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert record["kind"] == "mos.real_execution"
    assert record["data_mode"] == "live"
    assert record["live_backends"] == ["kos"]
    assert record["default_env"] is False  # MOS_LIVE_KOS was explicitly set
    assert record["ts"].endswith("Z")


def test_default_env_real_execution_is_flagged(monkeypatch, tmp_path):
    """A live execution WITHOUT live overrides (e.g. reachable Neo4j) counts as default env."""
    obs = tmp_path / "observations.jsonl"
    monkeypatch.setenv("MOS_OBSERVATIONS_PATH", str(obs))
    for key in ("MOS_LIVE_KOS", "MOS_LIVE_GBRAIN", "MOS_LIVE_GBRAIN_WRITE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")

    live_neo = Neo4jSearchBackend(writer=_Writer(True))
    mos = MemoryOS(search_backends={"neo4j": live_neo})
    rec = mos.recall("who relates to whom", intent="entity_relation")
    assert rec.data_mode == "mixed"
    assert rec.live_backends == ["neo4j"]

    record = json.loads(obs.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert record["default_env"] is True
    assert record["live_backends"] == ["neo4j"]


def test_rate_limit_bounds_writes(monkeypatch, tmp_path):
    """Two real executions within the interval produce exactly one record."""
    obs = tmp_path / "observations.jsonl"
    monkeypatch.setenv("MOS_OBSERVATIONS_PATH", str(obs))
    monkeypatch.setenv("MOS_SEAM_MIN_INTERVAL", "3600")

    assert record_real_execution("live", ["kos"], source="recall") is True
    assert record_real_execution("live", ["kos"], source="recall") is False
    lines = [ln for ln in obs.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1


def test_fixture_record_is_refused_even_when_called_directly(monkeypatch, tmp_path):
    obs = tmp_path / "observations.jsonl"
    monkeypatch.setenv("MOS_OBSERVATIONS_PATH", str(obs))
    assert record_real_execution("fixture", []) is False
    assert record_real_execution("live", []) is False  # no live backend => not a real execution
    assert not obs.exists()


def test_no_resolvable_root_is_fail_soft(monkeypatch):
    """No observation path resolvable => skip, no raise."""
    for key in ("MOS_OBSERVATIONS_PATH", "OMOSTATION_STATE_ROOT", "ECOS_WORKSPACE", "WORKSPACE_ROOT"):
        monkeypatch.delenv(key, raising=False)
    # Marker walk resolves the real checkout here, so force absence explicitly:
    monkeypatch.setattr("mos.observations._marker_walk", lambda start: None)
    assert observation_path() is None
    assert record_real_execution("live", ["kos"]) is False


def test_write_error_is_swallowed(monkeypatch, tmp_path):
    """A seam failure must never break recall."""
    # A path whose parent cannot be created (a file used as a directory).
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("MOS_OBSERVATIONS_PATH", str(blocker / "nested" / "observations.jsonl"))

    from mos.adapters.live_backends import LiveKosSearchBackend as Live

    monkeypatch.setenv("MOS_LIVE_KOS", "1")
    live = Live(http_get=lambda path, params: [{"id": "1"}])
    mos = MemoryOS(search_backends={"kos": live})
    rec = mos.recall("anything", intent="file_note")  # must not raise
    assert rec.data_mode == "live"
    assert not record_real_execution("live", ["kos"])  # swallowed -> False


def test_end_to_end_via_filestore(monkeypatch, tmp_path):
    """The CLI path (FileStore.build_memory_os) participates in the seam."""
    obs = tmp_path / "observations.jsonl"
    monkeypatch.setenv("MOS_OBSERVATIONS_PATH", str(obs))
    monkeypatch.setenv("MOS_STORE_PATH", str(tmp_path / "store.json"))
    monkeypatch.delenv("MOS_LIVE_KOS", raising=False)
    monkeypatch.delenv("MOS_LIVE_GBRAIN", raising=False)
    monkeypatch.delenv("NEO4J_URI", raising=False)

    store = FileStore()
    mos = store.build_memory_os()
    mos.write(validate_envelope({"type": "semantic", "content": "x", "confidence": 0.9}))
    mos.recall("x")  # fixture under default env
    assert not Path(obs).exists()
