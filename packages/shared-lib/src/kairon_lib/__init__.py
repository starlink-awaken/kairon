"""Kairon shared library - common utilities and base models."""

__version__ = "0.2.0"
__all__: list[str] = []

# Backward-compat re-exports
from kairon_lib.events import BOSEvent, get_global_event_bus, make_event  # noqa: F401



