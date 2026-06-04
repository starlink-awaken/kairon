#!/usr/bin/env python3
"""Thin wrapper — delegates to canonical script."""

import runpy
import sys
from pathlib import Path

_REAL = str(Path(__file__).resolve())
sys.argv[0] = _REAL
runpy.run_path(_REAL, run_name="__main__")
