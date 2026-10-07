"""Hermetic isolation for the MOS test suite.

The ADR-0464 observability seam (mos.observations) appends real-execution
records under the resolved state/workspace root. Tests must never pollute the
host checkout or the operator's state root, so every test gets a private
observation file via MOS_OBSERVATIONS_PATH (same env-override precedent as
MOS_STORE_PATH).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _hermetic_observations(tmp_path, monkeypatch):
    monkeypatch.setenv("MOS_OBSERVATIONS_PATH", str(tmp_path / "observations.jsonl"))
    yield
