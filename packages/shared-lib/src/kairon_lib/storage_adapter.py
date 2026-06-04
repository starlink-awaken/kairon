"""File storage adapter — file-based memory persistence (toolkit memory/adapters/FileStorageAdapter.ts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FileStorageAdapter:
    """Persist memory to JSON files."""

    def __init__(self, base_path: str = "./.memory") -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: Any) -> None:
        (self._base / f"{key}.json").write_text(json.dumps(data))

    def load(self, key: str) -> Any | None:
        fp = self._base / f"{key}.json"
        if not fp.exists(): return None
        return json.loads(fp.read_text())

    def delete(self, key: str) -> bool:
        fp = self._base / f"{key}.json"
        if not fp.exists(): return False
        fp.unlink(); return True

    def list_keys(self) -> list[str]:
        return [f.stem for f in self._base.glob("*.json")]
