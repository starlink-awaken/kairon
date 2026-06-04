"""
Plugin SDK for kairon plugin system.

Provides the BosPlugin base class and PluginContext for plugin development.
"""

__version__ = "1.0.0"

from kairon_lib.plugin_sdk.context import PluginContext
from kairon_lib.plugin_sdk.plugin import BosPlugin

__all__ = ["BosPlugin", "PluginContext", "__version__"]
