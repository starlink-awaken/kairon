"""`data_mode` provenance must reflect real runtime state, not class names.

BET-Y2Q4-T3-04 Item 3: production backends default OFF, so status/recall must say
loudly when they are served by fixture/stub data. `backend_data_mode` was fixed to
require the enable flag AND `available()` AND no `last_error`, so a flag-on backend
whose endpoint/CLI is down reads as fixture (M3). These tests fail against the
pre-M3 code and pass after.
"""

from mos.adapters.live_backends import LiveKosSearchBackend
from mos.neo4j_writer import Neo4jSearchBackend
from mos.service import MemoryOS, backend_data_mode

_FIXTURE_BACKENDS = ("gbrain", "gbrain_facts", "mem0", "temporal", "neo4j")


class _Writer:
    def __init__(self, avail: bool) -> None:
        self._avail = avail

    def available(self) -> bool:
        return self._avail


def test_default_memory_os_reports_fixture(monkeypatch):
    monkeypatch.delenv("MOS_LIVE_KOS", raising=False)
    monkeypatch.delenv("MOS_LIVE_GBRAIN", raising=False)
    monkeypatch.delenv("NEO4J_URI", raising=False)

    mos = MemoryOS()
    st = mos.status()
    assert st["data_mode"] == "fixture", st
    assert st["live_backends"] == []
    assert st["data_mode_note"], "a non-live mode must carry a notice"

    rec = mos.recall("hello world")
    assert rec.data_mode == "fixture"
    assert rec.to_dict()["notice"]


def test_genuinely_live_backend_reports_live(monkeypatch):
    monkeypatch.setenv("MOS_LIVE_KOS", "1")
    live = LiveKosSearchBackend(http_get=lambda path, params: [{"id": "1", "title": "t", "snippet": "s"}])
    assert backend_data_mode(live) == "live"
    assert live.available() is True
    assert live.last_error is None

    mos = MemoryOS(search_backends={"kos": live})
    rec = mos.recall("anything", intent="file_note")
    assert rec.data_mode == "live"
    assert rec.live_backends == ["kos"]
    assert rec.fixture_backends == []
    assert rec.to_dict()["notice"] is None


def test_flag_off_live_backend_is_fixture(monkeypatch):
    monkeypatch.delenv("MOS_LIVE_KOS", raising=False)
    off = LiveKosSearchBackend(http_get=lambda path, params: [{"id": "1"}])
    assert backend_data_mode(off) == "fixture"


def test_flag_on_but_erroring_backend_is_fixture(monkeypatch):
    monkeypatch.setenv("MOS_LIVE_KOS", "1")

    def _boom(path, params):
        raise RuntimeError("kos unreachable")

    bad = LiveKosSearchBackend(http_get=_boom)
    assert bad.available() is False
    assert bad.last_error  # error is recorded, not swallowed into a false "live"
    assert backend_data_mode(bad) == "fixture"


def test_neo4j_data_mode_tracks_uri_and_availability(monkeypatch):
    # No URI → fixture regardless of availability.
    monkeypatch.delenv("NEO4J_URI", raising=False)
    assert backend_data_mode(Neo4jSearchBackend(writer=_Writer(True))) == "fixture"

    # URI set + writer reachable → live.
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    assert backend_data_mode(Neo4jSearchBackend(writer=_Writer(True))) == "live"

    # URI set but writer unreachable → fixture (pre-M3 code wrongly said "live").
    assert backend_data_mode(Neo4jSearchBackend(writer=_Writer(False))) == "fixture"

    # A missing writer must not raise; it is not live.
    assert backend_data_mode(Neo4jSearchBackend(writer=None)) == "fixture"
