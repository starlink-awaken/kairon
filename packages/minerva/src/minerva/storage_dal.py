"""Data access layer abstractions — extracted from SharedBrain D_Memory.

Provides IStorageProvider, IRelationalProvider, IBlobProvider ABCs
and a SQLiteRelationalProvider implementation with WAL mode.
"""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class IStorageProvider(ABC):
    @abstractmethod
    def connect(self, db_path: str) -> None: ...
    @abstractmethod
    def close(self) -> None: ...


class IRelationalProvider(ABC):
    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> Any: ...
    @abstractmethod
    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]: ...
    @abstractmethod
    def commit(self) -> None: ...


class IBlobProvider(ABC):
    @abstractmethod
    def store(self, key: str, data: bytes) -> None: ...
    @abstractmethod
    def retrieve(self, key: str) -> bytes | None: ...


class SQLiteRelationalProvider(IRelationalProvider):
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = str(db_path) if db_path else ":memory:"
        self._conn: sqlite3.Connection | None = None
        self._connect()

    def _connect(self) -> None:
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._connect()
        assert self._conn is not None
        return self._conn

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
