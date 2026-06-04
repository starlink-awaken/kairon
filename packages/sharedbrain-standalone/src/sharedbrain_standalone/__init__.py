"""sharedbrain-standalone — HTTP/MCP server wrapping sharedbrain-core.

Exposes a FastAPI HTTP server on port 8000 and a FastMCP MCP server
on port 8001, sharing NeuralCenter, CircuitEngine, and NeuronPool instances.
"""

from __future__ import annotations

__version__ = "0.1.0"
