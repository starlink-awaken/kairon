"""Consolidate orchestrates dream runner; never reimplements cycle phases."""

from mos.consolidate import DEFAULT_CONSOLIDATE_PHASES, FakeDreamRunner, run_consolidate
from mos.service import MemoryOS


def test_default_phases_include_extract_and_consolidate():
    assert "extract_facts" in DEFAULT_CONSOLIDATE_PHASES
    assert "consolidate" in DEFAULT_CONSOLIDATE_PHASES


def test_consolidate_uses_fake_runner_and_audits_raw():
    fake = FakeDreamRunner()
    mos = MemoryOS(dream_runner=fake)
    mos.write({"type": "semantic", "content": "pending fact for consolidate", "confidence": 0.9})
    result = mos.consolidate(dry_run=True)
    assert result.ok is True
    assert result.dry_run is True
    assert fake.calls and fake.calls[0]["dry_run"] is True
    assert fake.calls[0]["phases"] == list(DEFAULT_CONSOLIDATE_PHASES)
    types = [e["event_type"] for e in mos.raw_backend.events]
    assert "memory.consolidate" in types
    st = mos.status()
    assert st["last_consolidate"] is not None
    assert st["backlog"]["active_docs"] >= 1


def test_consolidate_degraded_on_phase_failure():
    fake = FakeDreamRunner(fail_phases={"embed"})
    mos = MemoryOS(dream_runner=fake)
    result = mos.consolidate()
    assert result.degraded is True
    assert result.ok is False


def test_run_consolidate_standalone():
    fake = FakeDreamRunner()
    r = run_consolidate(dream=fake, phases=["consolidate"], dry_run=True)
    assert r.ok
    assert r.phases == ["consolidate"]
