"""KOS test fixtures."""

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def set_kos_home():
    """Set KOS_HOME for tests."""
    kos_tools = Path(__file__).resolve().parent.parent
    os.environ.setdefault("KOS_HOME", str(kos_tools))
