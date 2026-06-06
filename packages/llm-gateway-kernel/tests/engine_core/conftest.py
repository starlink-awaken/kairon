"""Pytest configuration and shared fixtures for engine-core tests.

Provides load_module() to import engine-core modules directly,
bypassing the broken __init__.py import chain (kairon_lib not available).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


def load_module(module_name: str, file_name: str) -> Any:
    """Load an engine-core module directly by file path.

    Args:
        module_name: Dotted module name, e.g. "engine_core._compat"
        file_name:   Python file name, e.g. "_compat.py"

    Returns:
        Loaded module object.
    """
    mod_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "llm_gateway_kernel"
        / "engine_core"
        / file_name
    )
    spec = importlib.util.spec_from_file_location(module_name, str(mod_path))
    if spec is None:
        raise ImportError(f"Could not find spec for {module_name} at {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(module_name, mod)
    if spec.loader is None:
        raise ImportError(f"No loader for {module_name}")
    spec.loader.exec_module(mod)
    return mod
