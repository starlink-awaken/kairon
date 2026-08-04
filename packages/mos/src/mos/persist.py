"""File-backed raw/theta store for CLI cross-process continuity."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mos.backends import InMemoryRawBackend, InMemorySearchBackend, InMemoryThetaBackend
from mos.service import MemoryOS


def default_store_path() -> Path:
    override = os.environ.get("MOS_STORE_PATH")
    if override:
        return Path(override)
    # Prefer workspace-local runtime data when present
    ws = os.environ.get("ECOS_WORKSPACE") or os.environ.get("WORKSPACE_ROOT")
    if ws:
        return Path(ws) / "runtime" / "mos" / "store.json"
    return Path.home() / ".mos" / "store.json"


class FileStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"raw_events": [], "theta_docs": [], "kos_docs": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {"raw_events": [], "theta_docs": [], "kos_docs": []}

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def build_memory_os(self) -> MemoryOS:
        raw = InMemoryRawBackend(events=list(self._data.get("raw_events") or []))
        theta = InMemoryThetaBackend(docs=list(self._data.get("theta_docs") or []))
        kos_docs = list(self._data.get("kos_docs") or [])
        if not kos_docs:
            kos_docs = [
                {
                    "id": "kos-adr-0372",
                    "title": "ADR-0372 Memory OS",
                    "snippet": "Memory OS control plane unified write recall",
                    "path": ".omo/_knowledge/decisions/0372-memory-os-control-plane.md",
                }
            ]
        mos = MemoryOS(raw=raw, theta=theta)
        mos.register_search_backend("kos", InMemorySearchBackend(name="kos", docs=kos_docs))
        mos.register_search_backend("cards", InMemorySearchBackend(name="cards", docs=[]))
        mos.register_search_backend("codebase_memory", InMemorySearchBackend(name="codebase_memory", docs=[]))
        mos.register_search_backend("governance_omo", InMemorySearchBackend(name="governance_omo", docs=[]))
        # attach for flush
        mos._file_store = self  # type: ignore[attr-defined]
        return mos

    def flush_from(self, mos: MemoryOS) -> None:
        self._data["raw_events"] = list(getattr(mos.raw_backend, "events", []) or [])
        self._data["theta_docs"] = list(getattr(mos.theta_backend, "docs", []) or [])
        self.save()
