"""Standalone HTTP/MCP server — wraps sharedbrain-core as a deployable service.

Part of sharedbrain-bridge. Exposes a FastAPI HTTP server on port 8000
and a FastMCP MCP server on port 8001, sharing NeuralCenter, CircuitEngine,
and NeuronPool instances.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = (
    "__version__",
)
