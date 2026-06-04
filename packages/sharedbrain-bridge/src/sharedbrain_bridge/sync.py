"""Batch Sync Bridge — kairon eidos ↔ SharedBrain D-Memory."""

import hashlib
import json
import logging
from pathlib import Path
from urllib.request import Request, urlopen

from typing import Any

_log = logging.getLogger(__name__)
DEFAULT_SB = "http://localhost:7421"
SHAREDBRAIN_ORGANS = Path(__file__).resolve().parents[3] / "SharedBrain" / "organs"  # auto-detect from package location


class SyncBridge:
    def __init__(self, sharedbrain=DEFAULT_SB):
        self.sb = sharedbrain

    def get_active_organs(self) -> list[dict[str, Any]]:
        organs: list[dict[str, Any]] = []
        if not SHAREDBRAIN_ORGANS.exists():
            return organs
        for d in sorted(SHAREDBRAIN_ORGANS.iterdir()):
            if d.is_dir() and d.name.startswith("D_"):
                sf = d / ".organ_status"
                organs.append({"name": d.name, "status": sf.read_text().strip() if sf.exists() else "active"})
        return organs

    def batch_sync_to_memory(self, organs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if organs is None:
            organs = self.get_active_organs()
        fp = hashlib.sha256(json.dumps(organs, sort_keys=True).encode()).hexdigest()
        try:
            payload = json.dumps({"organs": organs, "fingerprint": fp}).encode()
            req = Request(f"{self.sb}/api/v1/memory/sync", data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urlopen(req, timeout=10)
            return {"synced": resp.status == 200, "count": len(organs), "fp": fp}
        except Exception as e:
            return {"synced": False, "error": str(e), "count": len(organs), "fp": fp}
