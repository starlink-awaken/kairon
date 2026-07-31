"""Persistent, redacted human-adjudication queue for KEMS evaluation data."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SPLITS = {"train", "validation", "test", "shadow"}
_PRIVATE_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}


def _reject_private(value: object) -> None:
    if isinstance(value, dict):
        if _PRIVATE_KEYS.intersection(str(key).lower() for key in value):
            raise ValueError("raw content fields are forbidden")
        for child in value.values():
            _reject_private(child)
    elif isinstance(value, list):
        for child in value:
            _reject_private(child)


def _required_text(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _validate_queue_item(record: object) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("adjudication queue item must be an object")
    _reject_private(record)
    sample_id = _required_text(record, "sample_id")
    source_sha256 = _required_text(record, "source_sha256")
    if not _SHA256.fullmatch(source_sha256):
        raise ValueError("source_sha256 must be a lowercase SHA-256")
    source_ref = _required_text(record, "source_ref")
    if not source_ref.startswith("vault://redacted/"):
        raise ValueError("source_ref must use vault://redacted/")
    split = _required_text(record, "split")
    if split not in _SPLITS:
        raise ValueError("split is unsupported")
    status = record.get("annotation_status", "pending")
    if status != "pending":
        raise ValueError("new queue items must be pending")
    return {
        "sample_id": sample_id,
        "source_sha256": source_sha256,
        "source_ref": source_ref,
        "scenario_id": _required_text(record, "scenario_id"),
        "split": split,
    }


class AdjudicationStore:
    """Persist only redacted metadata and the human label decision."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS adjudication_queue (
                    sample_id TEXT PRIMARY KEY,
                    source_sha256 TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    split TEXT NOT NULL,
                    annotation_status TEXT NOT NULL,
                    labels_json TEXT NOT NULL,
                    annotation_version TEXT NOT NULL,
                    annotator TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def ingest_queue(self, items: list[object]) -> int:
        if not items:
            raise ValueError("adjudication queue must not be empty")
        normalized = [_validate_queue_item(item) for item in items]
        now = datetime.now(UTC).isoformat()
        self.initialize()
        inserted = 0
        with self._connect() as connection:
            for item in normalized:
                existing = connection.execute(
                    "SELECT source_sha256, source_ref, scenario_id, split FROM adjudication_queue WHERE sample_id=?",
                    (item["sample_id"],),
                ).fetchone()
                if existing:
                    if any(
                        existing[field] != item[field]
                        for field in ("source_sha256", "source_ref", "scenario_id", "split")
                    ):
                        raise ValueError(f"sample_id already exists with different metadata: {item['sample_id']}")
                    continue
                connection.execute(
                    """INSERT INTO adjudication_queue VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item["sample_id"],
                        item["source_sha256"],
                        item["source_ref"],
                        item["scenario_id"],
                        item["split"],
                        "pending",
                        "{}",
                        "",
                        "",
                        "",
                        now,
                    ),
                )
                inserted += 1
        return inserted

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["labels"] = json.loads(str(result.pop("labels_json")))
        return result

    def list_items(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if status is not None and status not in {"pending", "reviewed", "adjudicated"}:
            raise ValueError("annotation status is unsupported")
        self.initialize()
        with self._connect() as connection:
            if status:
                rows = connection.execute(
                    "SELECT * FROM adjudication_queue WHERE annotation_status=? ORDER BY updated_at, sample_id LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM adjudication_queue ORDER BY updated_at, sample_id LIMIT ?", (limit,)
                ).fetchall()
        return [self._row(row) for row in rows]

    def get_item(self, sample_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM adjudication_queue WHERE sample_id=?", (sample_id,)).fetchone()
        return self._row(row) if row else None

    def claim(self, sample_id: str, *, annotator: str) -> dict[str, Any]:
        annotator = annotator.strip()
        if not annotator:
            raise ValueError("annotator is required")
        self.initialize()
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM adjudication_queue WHERE sample_id=?", (sample_id,)).fetchone()
            if row is None:
                raise KeyError(sample_id)
            if row["annotation_status"] == "adjudicated":
                raise ValueError("adjudicated samples cannot be claimed")
            if row["annotation_status"] == "reviewed":
                if row["annotator"] == annotator:
                    return self._row(row)
                raise ValueError("sample is already claimed by another annotator")
            connection.execute(
                "UPDATE adjudication_queue SET annotation_status='reviewed', annotator=?, claimed_at=?, updated_at=? WHERE sample_id=?",
                (annotator, now, now, sample_id),
            )
        result = self.get_item(sample_id)
        assert result is not None
        return result

    def adjudicate(
        self,
        sample_id: str,
        *,
        labels: dict[str, Any],
        annotation_version: str,
        annotator: str,
    ) -> dict[str, Any]:
        if not labels:
            raise ValueError("labels must be a non-empty object")
        _reject_private(labels)
        annotation_version = annotation_version.strip()
        annotator = annotator.strip()
        if not annotation_version or not annotator:
            raise ValueError("annotation_version and annotator are required")
        self.initialize()
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM adjudication_queue WHERE sample_id=?", (sample_id,)).fetchone():
                raise KeyError(sample_id)
            connection.execute(
                """UPDATE adjudication_queue
                   SET annotation_status='adjudicated', labels_json=?, annotation_version=?, annotator=?, updated_at=?
                   WHERE sample_id=?""",
                (json.dumps(labels, ensure_ascii=False, sort_keys=True), annotation_version, annotator, now, sample_id),
            )
        result = self.get_item(sample_id)
        assert result is not None
        return result

    def adjudicated_items(self, *, limit: int = 10000) -> list[dict[str, Any]]:
        return self.list_items(status="adjudicated", limit=limit)
