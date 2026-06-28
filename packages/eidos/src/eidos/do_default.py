"""P57-W0 eidos do_default — 真业务 (调 eidos.adapters.sharedbrain).

P56-W3 评估后 P57-W0 实施: 3 sample 包先做真业务, 其他 14 包留 P58+.

POC 业务范围: list_available_organs / get_organ_path / read_organ_data / find_sharedbrain_root.
"""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P57-W0 eidos do_default: 真调 eidos.adapters.sharedbrain."""
    try:
        from eidos.adapters.sharedbrain import (
            find_sharedbrain_root,
            get_organ_path,
            list_available_organs,
            read_organ_data,
        )
    except Exception as exc:  # noqa: BLE001
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list")
    try:
        if action == "list":
            organs = list_available_organs()
            return {
                "_method": "do_default",
                "_action": "list",
                "organs_count": len(organs),
                "organs": organs[:10],
            }
        if action == "get_organ_path":
            organ = args.get("organ", args.get("name", ""))
            path = get_organ_path(organ)
            return {"_method": "do_default", "_action": "get_organ_path", "organ": organ, "path": path}
        if action == "read":
            organ = args.get("organ", args.get("name", ""))
            data = read_organ_data(organ)
            return {
                "_method": "do_default",
                "_action": "read",
                "organ": organ,
                "data_keys": list(data.keys()) if isinstance(data, dict) else None,
            }
        if action == "find_root":
            root = find_sharedbrain_root()
            return {"_method": "do_default", "_action": "find_root", "root": root}
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:  # noqa: BLE001
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
