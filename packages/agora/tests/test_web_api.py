"""Integration tests for Agora Web API (FastAPI TestClient)."""

import os
import sqlite3
import subprocess
from pathlib import Path

# 必须优先设置 AGORA_API_KEY，否则 _auth_middleware 会拒掉所有 POST 请求
# 使用强制赋值（非 setdefault）以覆盖环境中已有的真实 API key
os.environ["AGORA_API_KEY"] = "test-key-123"

# 兜底：如果 app 模块已在其他 conftest 中被导入，强制重写其 API_KEY
import agora.web.app as _app_module
from agora.web.app import app
from fastapi.testclient import TestClient

_app_module.API_KEY = "test-key-123"

client = TestClient(app, headers={"X-API-Key": "test-key-123"})


class TestDashboard:
    def test_dashboard_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "html" in resp.headers["content-type"].lower()

    def test_dashboard_contains_agora(self):
        resp = client.get("/")
        assert "Agora" in resp.text or "agora" in resp.text.lower()

    def test_dashboard_contains_research_detail_sections(self):
        resp = client.get("/")
        assert "研究详情" in resp.text
        assert "研究时间线" in resp.text
        assert "发布产物" in resp.text


class TestCorsConfig:
    """CORS middleware respects AGORA_CORS_ORIGINS env var."""

    def test_default_cors_headers(self):
        """Default CORS origins allow localhost:7430."""
        resp = client.get("/", headers={"Origin": "http://localhost:7430"})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:7430"

    def test_default_cors_rejects_unknown_origin(self):
        """Default CORS origins reject unknown origins."""
        resp = client.get("/", headers={"Origin": "https://evil.com"})
        assert resp.status_code == 200
        assert "access-control-allow-origin" not in resp.headers


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
        "INSERT INTO research (id, topic, summary, source_count, created_at) VALUES (?, ?, ?, ?, ?)",
        (2, "Parent Topic", "Parent summary", 1, 1700000000.0),
    )
    conn.execute(
        "INSERT INTO research (id, topic, summary, source_count, created_at) VALUES (?, ?, ?, ?, ?)",
        (3, "Child Topic", "Child summary", 2, 1720000000.0),
    )
    conn.execute(
        "INSERT INTO research_relations (parent_id, child_id, relation_type, created_at) VALUES (?, ?, ?, ?)",
        (2, 1, "merge", 1710000100.0),
    )
    conn.execute(
        "INSERT INTO research_relations (parent_id, child_id, relation_type, created_at) VALUES (?, ?, ?, ?)",
        (1, 3, "digest", 1710000200.0),
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


class TestApiResearch:
    def test_research_returns_empty_when_db_missing(self, monkeypatch, tmp_path):
        from agora.web import workspace_research

        monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)
        resp = client.get("/api/research")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"research": [], "total": 0}

    def test_research_search_returns_match_snippet(self, monkeypatch, tmp_path):
        from agora.web import workspace_research

        _seed_workspace_db(tmp_path)
        monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

        resp = client.get("/api/research", params={"q": "Main", "status": "active"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["research"][0]["id"] == 1
        assert data["research"][0]["snippet"] == "Main summary"

    def test_research_status_filter_returns_archived_records(self, monkeypatch, tmp_path):
        from agora.web import workspace_research

        _seed_workspace_db(tmp_path)
        conn = sqlite3.connect(str(tmp_path / ".workspace" / "data.db"))
        conn.execute(
            "INSERT INTO research (id, topic, summary, source_count, created_at, archived_at, archive_reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (9, "Archived Topic", "Archived summary", 1, 1690000000.0, 1690000100.0, "manual archive"),
        )
        conn.commit()
        conn.close()
        monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

        resp = client.get("/api/research", params={"status": "archived"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["research"][0]["id"] == 9

    def test_research_default_listing_excludes_archived_records(self, monkeypatch, tmp_path):
        from agora.web import workspace_research

        _seed_workspace_db(tmp_path)
        conn = sqlite3.connect(str(tmp_path / ".workspace" / "data.db"))
        conn.execute(
            "INSERT INTO research (id, topic, summary, source_count, created_at, archived_at, archive_reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (9, "Archived Topic", "Archived summary", 1, 1730000000.0, 1730000100.0, "manual archive"),
        )
        conn.commit()
        conn.close()
        monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

        resp = client.get("/api/research")

        assert resp.status_code == 200
        data = resp.json()
        assert all(item["id"] != 9 for item in data["research"])

    def test_research_rejects_invalid_status_value(self, monkeypatch, tmp_path):
        from agora.web import workspace_research

        _seed_workspace_db(tmp_path)
        monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

        resp = client.get("/api/research", params={"status": "broken"})

        assert resp.status_code == 400
        assert resp.json()["error"] == "无效状态：broken"

    def test_research_rejects_non_positive_limit(self, monkeypatch, tmp_path):
        from agora.web import workspace_research

        _seed_workspace_db(tmp_path)
        monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

        resp = client.get("/api/research", params={"limit": 0})

        assert resp.status_code == 400
        assert resp.json()["error"] == "limit 必须大于 0"

    def test_research_detail_returns_dossier_timeline_and_publications(self, monkeypatch, tmp_path):
        from agora.web import workspace_research

        _seed_workspace_db(tmp_path)
        monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

        resp = client.get("/api/research/1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["record"]["id"] == 1
        assert data["record"]["topic"] == "Main Topic"
        assert data["record"]["tags"] == ["alpha", "beta"]
        assert data["parents"][0]["id"] == 2
        assert data["children"][0]["id"] == 3
        assert data["publications"][0]["style"] == "brief"
        assert any(item["event_type"] == "created" for item in data["timeline"])
        assert any(item["event_type"] == "published" for item in data["timeline"])

    def test_research_detail_returns_404_when_missing(self, monkeypatch, tmp_path):
        from agora.web import workspace_research

        _seed_workspace_db(tmp_path)
        monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

        resp = client.get("/api/research/999")

        assert resp.status_code == 404
        assert resp.json()["error"] == "Research not found"

    def test_research_tag_returns_400_when_research_missing(self, monkeypatch, tmp_path):
        from agora.web import workspace_research

        _seed_workspace_db(tmp_path)
        monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

        resp = client.post("/api/research/999/tag", params={"tags": "missing"})

        assert resp.status_code == 400
        assert resp.json()["error"] == "标签更新失败：研究不存在"

    def test_research_ask_returns_400_when_research_missing(self, monkeypatch, tmp_path):
        from agora.web import workspace_research

        _seed_workspace_db(tmp_path)
        monkeypatch.setattr(workspace_research, "workspace_home", lambda: tmp_path)

        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=1,
                stdout="",
                stderr="研究不存在",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        resp = client.post("/api/research/999/ask", params={"question": "why"})

        assert resp.status_code == 400
        assert resp.json()["error"] == "研究不存在"


class TestApiServices:
    def test_list_services_returns_list(self):
        resp = client.get("/api/services")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_service_has_protocol_field(self):
        resp = client.get("/api/services")
        data = resp.json()
        if data:
            assert "protocol" in data[0]
            assert "circuit" in data[0]


class TestApiHealth:
    def test_health_returns_status(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "services" in data
        assert "healthy" in data

    def test_health_circuits_present(self):
        resp = client.get("/api/health")
        data = resp.json()
        assert "circuits" in data


class TestApiRegister:
    def test_register_service_basic(self):
        resp = client.post(
            "/api/register",
            data={
                "name": "test-svc",
                "mcp_endpoint": "http://192.0.2.10:8765",
                "tags": "test,api",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-svc"
        assert data["status"] == "registered"

    def test_register_with_protocol(self):
        resp = client.post(
            "/api/register",
            data={
                "name": "rest-api",
                "protocol": "rest",
                "protocol_config": '{"method":"POST","path":"/users"}',
                "mcp_endpoint": "http://192.0.2.11:3000",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["protocol"] == "rest"

    def test_register_invalid_protocol_config(self):
        resp = client.post(
            "/api/register",
            data={
                "name": "bad-config",
                "protocol_config": "not json",
            },
        )
        assert resp.status_code == 400

    def test_register_default_protocol(self):
        resp = client.post(
            "/api/register",
            data={
                "name": "default-proto-svc",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["protocol"] == "mcp"


class TestApiPipeline:
    def test_list_pipelines(self):
        resp = client.get("/api/pipelines")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipelines" in data  # returns {"pipelines": [...]}

    def test_pipeline_dag(self):
        resp = client.get("/api/pipeline/full-pipeline/dag")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (dict, list))


class TestApiDiscover:
    def test_discover_returns_result(self):
        resp = client.post("/api/discover")
        assert resp.status_code == 200
        data = resp.json()
        assert "discovered" in data
        assert "total" in data


class TestApiClear:
    def test_clear_returns_status(self):
        resp = client.post("/api/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cleared"


class TestApiMetrics:
    def test_metrics_history(self):
        resp = client.get("/api/metrics/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "latency" in data
        assert "services" in data


class TestApiEvent:
    def test_event_log_returns_list(self):
        resp = client.get("/api/event-log")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_event_publish_returns_id(self):
        resp = client.post(
            "/api/event-publish",
            data={
                "event_type": "test:unit",
                "payload": '{"msg":"hello"}',
                "source": "test",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "published"

    def test_event_publish_after_restart(self):
        """Events survive API restart due to module-level EventBus."""
        resp = client.post(
            "/api/event-publish",
            data={
                "event_type": "test:persist",
                "payload": "{}",
            },
        )
        assert resp.status_code == 200
        # Log should now include this new event
        resp2 = client.get("/api/event-log")
        assert resp2.status_code == 200


class TestRateLimit:
    def test_normal_request_passes(self, monkeypatch):
        monkeypatch.setenv("AGORA_RATE_LIMIT", "5")
        resp = client.get("/api/services")
        assert resp.status_code == 200

    def test_rate_limit_header(self, monkeypatch):
        monkeypatch.setenv("AGORA_RATE_LIMIT", "60")
        resp = client.get("/api/services")
        assert resp.status_code == 200


class TestPrometheusMetrics:
    def test_metrics_endpoint(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        # Prometheus format should include gauge lines
        assert "agora_services" in resp.text
