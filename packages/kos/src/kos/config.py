"""Package-level config shim for `kos.config` imports.
Delegates to root config.py via explicit path loading to avoid import collision.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from kos import _default_workspace_config

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_mod = None


def _load_root_config():
    global _mod
    if _mod is not None:
        return _mod
    kos_home_config = Path(os.environ.get("KOS_HOME", "")) / "config.py"
    if kos_home_config.exists():
        config_path = kos_home_config
    else:
        config_path = Path(_ROOT) / "config.py"
    if not config_path.exists():
        return _default_workspace_config
    spec = importlib.util.spec_from_file_location("kos_root_config", str(config_path))
    _mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_mod)
    if not hasattr(_mod, "get_vault_ops_dir"):
        _mod.get_vault_ops_dir = lambda: Path(os.environ.get("KOS_HOME", str(Path.home() / ".kos")))
    return _mod


def get_vault_ops_dir() -> Path:
    return _load_root_config().get_vault_ops_dir()


def get_artifact_path(*args, **kwargs):
    return _load_root_config().get_artifact_path(*args, **kwargs)


def get_workspace_manifest(*args, **kwargs):
    return _load_root_config().get_workspace_manifest(*args, **kwargs)


def get_documents_root(*args, **kwargs):
    return _load_root_config().get_documents_root(*args, **kwargs)
