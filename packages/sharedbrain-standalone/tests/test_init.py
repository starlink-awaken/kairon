"""Tests for sharedbrain-standalone package initialization."""

from sharedbrain_standalone import __version__


class TestInit:
    """Test the package __init__.py exports."""

    def test_version(self):
        """__version__ should be defined and non-empty."""
        assert __version__ == "0.1.0"
        assert isinstance(__version__, str)
        assert len(__version__) > 0
