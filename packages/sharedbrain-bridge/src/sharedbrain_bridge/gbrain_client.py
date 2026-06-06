"""GBrain MCP Client."""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger(__name__)
DEFAULT_GBRAIN_DIR = str(Path(__file__).resolve().parents[3] / "gbrain")
RESP_TIMEOUT = 30.0
