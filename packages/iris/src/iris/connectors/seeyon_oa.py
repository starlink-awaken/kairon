"""Seeyon OA connector — 致远 OA CDP 抓取 (ECCP P3 收编).

收编自 runtime/scripts/seeyon-oa-cdp-ingest.py + seeyon-auto-login-fetch.py.
原脚本: 复用 Chrome 9222 已登录 Session, 静默提炼待办公文.
本 connector: health (CDP 9222 可用) + descriptor; list 留后续 (CDP 抓取逻辑迁移).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from iris.base import BaseConnector

SEEYON_CDP_PORT = 9222


class SeeyonOAConnector(BaseConnector):
    """致远 OA (ECCP P3 收编, CDP 9222 共享 Session)."""

    name = "seeyon_oa"
    display_name = "致远 OA"
    connection_kind = "knowledge_source"
    protocol = "seeyon.oa.cdp/v1"
    capabilities = ("discover", "read", "snapshot")
    data_classification = "internal"

    def is_available(self) -> bool:
        """检查 Chrome 9222 CDP Remote Debugging 开启."""
        try:
            req = urllib.request.urlopen(
                f"http://127.0.0.1:{SEEYON_CDP_PORT}/json/version", timeout=2
            )
            return bool(json.loads(req.read().decode("utf-8")))
        except Exception:
            return False

    def status(self) -> dict[str, Any]:
        return {
            "cdp_port": SEEYON_CDP_PORT,
            "available": self.is_available(),
            "note": "需 Chrome --remote-debugging-port=9222 + 已登录致远 OA",
        }
