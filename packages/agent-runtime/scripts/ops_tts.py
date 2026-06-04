#!/usr/bin/env python3
"""Thin wrapper — delegates to canonical script."""

import os
import runpy
import sys
from pathlib import Path

_FORGE_ROOT = os.environ.get("FORGE_ROOT", str(Path.home() / "Workspace" / "Forge"))
_REAL = os.environ.get("OPS_TTS_REAL", str(Path(_FORGE_ROOT) / "scripts" / "ops_tts.py"))
sys.argv[0] = _REAL
runpy.run_path(_REAL, run_name="__main__")
