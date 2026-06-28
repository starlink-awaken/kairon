"""Tests for core-models provenance."""

from core_models.provenance import Provenance


def test_provenance_defaults():
    p = Provenance()
    assert isinstance(p.source_file, str)
