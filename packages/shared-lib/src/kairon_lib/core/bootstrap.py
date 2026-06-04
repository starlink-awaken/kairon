from __future__ import annotations

"""
Bootstrap utilities for project root resolution.

Provides ``ensure_project_root_on_sys_path`` so that sibling modules can
reliably locate the monorepo root regardless of PYTHONPATH.
"""

import sys
from pathlib import Path


def ensure_project_root_on_sys_path() -> Path:
    """Add the project root to ``sys.path`` (if absent) and return it.

    Walks upward from ``__file__`` looking for a ``pyproject.toml`` that
    declares ``[tool.uv.workspace]`` (or for a ``.git`` directory).  The
    first match is treated as the monorepo root and added to ``sys.path``.
    """
    candidate = Path(__file__).resolve().parent
    for parent in [candidate] + list(candidate.parents):
        if (parent / ".git").exists():
            root = parent
            break
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            if "[tool.uv.workspace]" in content:
                root = parent
                break
    else:
        root = candidate  # fallback — caller may still work

    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    return root
