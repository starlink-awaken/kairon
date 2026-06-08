"""Eidos test fixtures."""
import pytest


@pytest.fixture
def sample_entity():
    return {"id": "test-entity-1", "type": "concept", "name": "Test Entity"}
