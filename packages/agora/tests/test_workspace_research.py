"""Tests for Agora workspace research read helpers."""

import sqlite3
from pathlib import Path

from agora.web import workspace_research


def _seed_workspace_db(home: Path) -> None:
    workspace_dir = home / ".workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(workspace_dir / "data.db"))
    conn.executescript(
        """
        CREATE TABLE research (
            id INTEGER PRIMARY KEY,
            topic TEXT NOT NULL,
            summary TEXT,
            source_count INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            follow_ups TEXT DEFAULT '[]',
            quarantined_at REAL,
            quarantine_reason TEXT,
            tags TEXT DEFAULT '[]',
            archived_at REAL,
            archive_reason TEXT
        );
        CREATE TABLE research_relations (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE published_reports (
            id INTEGER PRIMARY KEY,
            research_id INTEGER NOT NULL,
            style TEXT NOT NULL,
            output_path TEXT NOT NULL,
            published_at REAL NOT NULL
        );
        CREATE TABLE research_events (
            id INTEGER PRIMARY KEY,
            research_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO research (id, topic, summary, source_count, created_at, tags) VALUES (?, ?, ?, ?, ?, ?)",
        (1, "Main Topic", "Main summary", 3, 1710000000.0, '["alpha", "beta"]'),
    )
    conn.execute(
        "INSERT INTO research (id, topic, summary, source_count, created_at, archived_at, archive_reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2, "Archived Topic", "Archived summary", 1, 1700000000.0, 1700000100.0, "manual archive"),
    )
    conn.execute(
        "INSERT INTO research (id, topic, summary, source_count, created_at, quarantined_at, quarantine_reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (3, "Quarantined Topic", "Quarantined summary", 2, 1720000000.0, 1720000100.0, "bad source"),
    )
    conn.execute(
        "INSERT INTO research (id, topic, summary, source_count, created_at) VALUES (?, ?, ?, ?, ?)",
        (4, "Parent Topic", "Parent summary", 1, 1690000000.0),
    )
    conn.execute(
        "INSERT INTO research (id, topic, summary, source_count, created_at) VALUES (?, ?, ?, ?, ?)",
        (5, "Child Topic", "Child summary", 2, 1730000000.0),
    )
    conn.execute(
        "INSERT INTO research_relations (parent_id, child_id, relation_type, created_at) VALUES (?, ?, ?, ?)",
        (4, 1, "merge", 1710000100.0),
    )
    conn.execute(
        "INSERT INTO research_relations (parent_id, child_id, relation_type, created_at) VALUES (?, ?, ?, ?)",
        (1, 5, "digest", 1710000200.0),
    )
    conn.execute(
        "INSERT INTO published_reports (research_id, style, output_path, published_at) VALUES (?, ?, ?, ?)",
        (1, "brief", "/tmp/main-topic.md", 1710000300.0),
    )
    conn.execute(
        "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
        (1, "published", "发布为 brief: /tmp/main-topic.md", 1710000300.0),
    )
    conn.commit()
    conn.close()


def test_list_recent_research_returns_empty_when_db_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

    result = workspace_research.list_recent_research(limit=10)

    assert result == {"research": [], "total": 0}


def test_list_recent_research_filters_archived_and_quarantined(monkeypatch, tmp_path):
    _seed_workspace_db(tmp_path)
    monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

    result = workspace_research.list_recent_research(limit=10)

    assert result["total"] == 3
    ids = [item["id"] for item in result["research"]]
    assert 1 in ids
    assert 4 in ids
    assert 5 in ids
    assert 2 not in ids
    assert 3 not in ids


def test_get_research_detail_returns_dossier_timeline_and_publications(monkeypatch, tmp_path):
    _seed_workspace_db(tmp_path)
    monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

    result = workspace_research.get_research_detail(1)

    assert result is not None
    assert result["record"]["id"] == 1
    assert result["record"]["tags"] == ["alpha", "beta"]
    assert result["parents"][0]["id"] == 4
    assert result["children"][0]["id"] == 5
    assert result["publications"][0]["style"] == "brief"
    assert [item["event_type"] for item in result["timeline"]] == ["created", "derived_from", "published"]


def test_get_research_detail_returns_none_when_missing(monkeypatch, tmp_path):
    _seed_workspace_db(tmp_path)
    monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

    result = workspace_research.get_research_detail(999)

    assert result is None


def test_search_research_filters_by_keyword_status_and_tag(monkeypatch, tmp_path):
    _seed_workspace_db(tmp_path)
    monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

    result = workspace_research.search_research(q="Main", status="active", tag="alpha", limit=10)

    assert result["total"] == 1
    assert result["research"][0]["id"] == 1
    assert result["research"][0]["topic"] == "Main Topic"
    assert result["research"][0]["snippet"] == "Main summary"


def test_tag_research_returns_false_when_research_missing(monkeypatch, tmp_path):
    _seed_workspace_db(tmp_path)
    monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

    result = workspace_research.tag_research(999, ["missing"])

    assert result is False


def test_rename_research_returns_false_when_research_missing(monkeypatch, tmp_path):
    _seed_workspace_db(tmp_path)
    monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

    result = workspace_research.rename_research(999, "missing-title")

    assert result is False
