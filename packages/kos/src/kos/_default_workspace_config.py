# kos/_default_workspace_config.py
"""Default workspace config for standalone KOS usage.
Override by placing a workspace_config.py in your KOS_HOME directory.
"""

import json
import os
from pathlib import Path
from typing import Any, cast


def get_workspace_manifest() -> dict[str, Any]:
    """Return minimal default manifest. Auto-creates if missing."""
    kos_home = os.environ.get("KOS_HOME")
    if kos_home:
        manifest_path = Path(kos_home) / "manifest.json"
        if manifest_path.exists():  # type: ignore[Any, Any]
            return cast("dict[str, Any]", json.loads(manifest_path.read_text()))
        # Auto-create default manifest with workspace zone
        default = {
            "name": "kos-default",
            "zones": {
                "workspace": {
                    "label": "KOS Workspace",
                    "authoritative": True,
                    "indexable": True,
                    "path": kos_home,
                    "scope": "internal",
                    "filePatterns": ["*.py", "*.md", "*.txt", "*.toml", "*.yaml", "*.json"],
                    "indexingStrategies": {"default": "full_text"},
                }
            },
            "entitySources": [],
            "predicatePatterns": {
                "zh": {
                    "reports_to": ["汇报给", "向.*汇报", "上级", "分管"],
                    "manages": ["管理", "主管", "负责"],
                    "member_of": ["属于", "隶属于", "所在", "成员"],
                    "works_on": ["参与", "承担"],
                    "owns": ["拥有", "创建", "作者"],
                    "coordinates": ["协调", "统筹", "对接"],
                }
            },
            "artifacts": {"retrievalDatabase": "kos-index.sqlite"},
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(default, ensure_ascii=False, indent=2))
        return default
    return {
        "name": "kos-default",
        "zones": {},
        "indexingStrategies": {},
        "entitySources": [],
        "predicatePatterns": {},
    }


def get_artifact_path(name: str) -> str:
    """Return default artifact paths relative to KOS_HOME."""
    kos_home = os.environ.get("KOS_HOME", str(Path.home() / ".kos"))
    paths = {
        "retrievalDatabase": str(Path(kos_home) / "kos-index.sqlite"),
    }
    return paths.get(name, "")


def get_zone_path(zone: str) -> str:
    """Default zone path - each zone is a directory under KOS_HOME/domains/."""
    kos_home = os.environ.get("KOS_HOME", str(Path.home() / ".kos"))
    return str(Path(kos_home) / "domains" / zone)


def get_documents_root() -> str:
    """Default documents root."""
    return os.environ.get("KOS_HOME", str(Path.home() / ".kos"))


def get_vault_ops_dir() -> Path:
    """Return the default KOS workspace root for package-level config fallback."""
    return Path(os.environ.get("KOS_HOME", str(Path.home() / ".kos")))
