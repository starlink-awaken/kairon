"""Tests for KOS FastAPI web app."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def _load_web_app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("KOS_HOME", str(tmp_path))
    sys.modules.pop("kos.web.app", None)
    module = importlib.import_module("kos.web.app")
    return importlib.reload(module)


def test_health_endpoint_reports_workspace_and_database(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["workspace"]["name"] == "kos-default"
    assert payload["workspace"]["zones"] == 1
    assert payload["database"]["reachable"] is True
    assert payload["database"]["path"] == str(tmp_path / "kos-index.sqlite")


def test_stats_endpoint_reports_uninitialized_database(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    response = client.get("/api/v1/stats")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["data_quality"] == "unavailable"
    assert "documents" in payload["error"]
