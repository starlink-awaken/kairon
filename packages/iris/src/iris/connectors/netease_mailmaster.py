"""Netease Mailmaster connector — 网易邮箱大师 (ECCP P3 收编).

收编自 runtime/scripts/netease-mailmaster-ingest.py.
原脚本: 真实解压 OrigBody zlib Blob, 3 账号 (卫健委/163) 真实邮件公文.
本 connector: health (sqlite/zlib 数据目录) + descriptor; list 留后续 (zlib 解压逻辑迁移).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from iris.base import BaseConnector

MAILMASTER_BASE = (
    Path.home()
    / "Library/Containers/com.netease.macmail/Data/Library/Application Support/data"
)


class NeteaseMailmasterConnector(BaseConnector):
    """网易邮箱大师 (ECCP P3 收编)."""

    name = "netease_mailmaster"
    display_name = "网易邮箱大师"
    connection_kind = "knowledge_source"
    protocol = "netease.mailmaster/v1"
    capabilities = ("discover", "search", "read", "snapshot")
    data_classification = "private"

    def is_available(self) -> bool:
        return MAILMASTER_BASE.exists()

    def status(self) -> dict[str, Any]:
        db_count = len(list(MAILMASTER_BASE.glob("**/*.sqlite"))) if self.is_available() else 0
        return {
            "base": str(MAILMASTER_BASE),
            "available": self.is_available(),
            "sqlite_count": db_count,
        }
