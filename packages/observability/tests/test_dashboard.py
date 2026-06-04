"""Tests for the dashboard module — DashboardData, DashboardConfig, ServiceCard, TopologyEdge."""

import json

import pytest

from observability.dashboard import (
    DashboardConfig,
    DashboardData,
    ServiceCard,
    TopologyEdge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dashboard():
    return DashboardData()


@pytest.fixture
def populated_dashboard():
    db = DashboardData()
    db.update_service("api-gateway", status="healthy", uptime_pct=99.95, p99_ms=120.0, error_rate=0.001)
    db.update_service("user-service", status="degraded", uptime_pct=98.0, p99_ms=600.0, error_rate=0.02)
    db.update_service("db-primary", status="unhealthy", uptime_pct=85.0, p99_ms=3000.0, error_rate=0.08)
    db.add_edge("web", "api-gateway", call_count=5000, avg_ms=25.0, p99_ms=80.0)
    db.add_edge("api-gateway", "user-service", call_count=2000, avg_ms=100.0, p99_ms=300.0)
    db.add_edge("api-gateway", "db-primary", call_count=1000, avg_ms=5.0, p99_ms=15.0)
    return db


# ---------------------------------------------------------------------------
# Dataclass basics
# ---------------------------------------------------------------------------


class TestServiceCard:
    def test_defaults(self):
        c = ServiceCard(name="test")
        assert c.name == "test"
        assert c.status == "unknown"
        assert c.uptime_pct == 0.0
        assert c.p99_latency_ms == 0.0
        assert c.error_rate == 0.0
        assert c.last_checked > 0

    def test_custom(self):
        c = ServiceCard(name="svc", status="healthy", uptime_pct=99.9, p99_latency_ms=150.0, error_rate=0.01)
        assert c.status == "healthy"
        assert c.p99_latency_ms == 150.0


class TestTopologyEdge:
    def test_defaults(self):
        e = TopologyEdge(source="a", target="b")
        assert e.source == "a"
        assert e.target == "b"
        assert e.call_count == 0

    def test_custom(self):
        e = TopologyEdge(source="web", target="api", call_count=100, avg_latency_ms=50.0, p99_latency_ms=200.0, error_rate=0.005)
        assert e.call_count == 100
        assert e.p99_latency_ms == 200.0


class TestDashboardConfig:
    def test_defaults(self):
        c = DashboardConfig()
        assert c.title == "Health Dashboard"
        assert c.refresh_interval_sec == 30
        assert c.degrade_p99_threshold_ms == 500.0
        assert c.degrade_error_threshold == 0.01
        assert c.unhealthy_p99_threshold_ms == 2000.0
        assert c.unhealthy_error_threshold == 0.05

    def test_custom(self):
        c = DashboardConfig(
            title="Custom",
            degrade_p99_threshold_ms=300.0,
            unhealthy_p99_threshold_ms=1000.0,
        )
        assert c.title == "Custom"
        assert c.degrade_p99_threshold_ms == 300.0


# ---------------------------------------------------------------------------
# Update service
# ---------------------------------------------------------------------------


class TestUpdateService:
    def test_create_service(self, dashboard):
        dashboard.update_service("api", status="healthy", uptime_pct=99.0, p99_ms=100.0)
        assert "api" in dashboard._services
        assert dashboard._services["api"].status == "healthy"

    def test_update_existing_service(self, dashboard):
        dashboard.update_service("api", status="healthy", uptime_pct=99.0, p99_ms=100.0)
        dashboard.update_service("api", status="degraded", uptime_pct=95.0, p99_ms=600.0)
        assert dashboard._services["api"].status == "degraded"
        assert dashboard._services["api"].p99_latency_ms == 600.0

    def test_auto_derive_status_healthy(self, dashboard):
        dashboard.update_service("api", p99_ms=100.0, error_rate=0.001)
        assert dashboard._services["api"].status == "healthy"

    def test_auto_derive_status_degraded_by_p99(self, dashboard):
        dashboard.update_service("api", p99_ms=600.0, error_rate=0.0)
        assert dashboard._services["api"].status == "degraded"

    def test_auto_derive_status_degraded_by_error_rate(self, dashboard):
        dashboard.update_service("api", p99_ms=100.0, error_rate=0.02)
        assert dashboard._services["api"].status == "degraded"

    def test_auto_derive_status_unhealthy_by_p99(self, dashboard):
        dashboard.update_service("api", p99_ms=3000.0, error_rate=0.0)
        assert dashboard._services["api"].status == "unhealthy"

    def test_auto_derive_status_unhealthy_by_error_rate(self, dashboard):
        dashboard.update_service("api", p99_ms=100.0, error_rate=0.10)
        assert dashboard._services["api"].status == "unhealthy"


# ---------------------------------------------------------------------------
# Add edge
# ---------------------------------------------------------------------------


class TestAddEdge:
    def test_add_edge(self, dashboard):
        dashboard.add_edge("web", "api", call_count=100)
        assert len(dashboard._edges) == 1
        assert dashboard._edges[0].source == "web"
        assert dashboard._edges[0].target == "api"

    def test_update_existing_edge(self, dashboard):
        dashboard.add_edge("web", "api", call_count=100)
        dashboard.add_edge("web", "api", call_count=200)
        assert len(dashboard._edges) == 1
        assert dashboard._edges[0].call_count == 200

    def test_multiple_edges(self, dashboard):
        dashboard.add_edge("a", "b")
        dashboard.add_edge("b", "c")
        assert len(dashboard._edges) == 2


# ---------------------------------------------------------------------------
# Get overview
# ---------------------------------------------------------------------------


class TestGetOverview:
    def test_empty_overview(self, dashboard):
        overview = dashboard.get_overview()
        assert overview["dashboard"]["title"] == "Health Dashboard"
        assert overview["services"] == []
        assert overview["summary"]["total"] == 0
        assert overview["summary"]["health_pct"] == 100.0
        assert overview["topology"] == []

    def test_overview_counts(self, populated_dashboard):
        overview = populated_dashboard.get_overview()
        assert overview["summary"]["total"] == 3
        assert overview["summary"]["healthy"] == 1
        assert overview["summary"]["degraded"] == 1
        assert overview["summary"]["unhealthy"] == 1

    def test_overview_services(self, populated_dashboard):
        overview = populated_dashboard.get_overview()
        names = {s["name"] for s in overview["services"]}
        assert names == {"api-gateway", "user-service", "db-primary"}

    def test_overview_topology(self, populated_dashboard):
        overview = populated_dashboard.get_overview()
        assert len(overview["topology"]) == 3
        edges = {(e["source"], e["target"]) for e in overview["topology"]}
        assert ("web", "api-gateway") in edges
        assert ("api-gateway", "user-service") in edges
        assert ("api-gateway", "db-primary") in edges

    def test_overview_metadata(self, populated_dashboard):
        overview = populated_dashboard.get_overview()
        assert "generated_at" in overview["dashboard"]
        assert "refresh_interval_sec" in overview["dashboard"]
        assert overview["updated_at"] > 0


# ---------------------------------------------------------------------------
# Get service detail
# ---------------------------------------------------------------------------


class TestGetServiceDetail:
    def test_unknown_service(self, dashboard):
        assert dashboard.get_service_detail("nobody") is None

    def test_service_detail_basic(self, populated_dashboard):
        detail = populated_dashboard.get_service_detail("api-gateway")
        assert detail is not None
        assert detail["service"]["name"] == "api-gateway"
        assert detail["service"]["status"] == "healthy"
        assert detail["metrics"]["p99_ms"] == 120.0

    def test_service_detail_connections(self, populated_dashboard):
        detail = populated_dashboard.get_service_detail("api-gateway")
        # api-gateway has 1 upstream (web) and 2 downstreams (user-service, db-primary)
        assert detail["dependency_count"]["upstream"] == 1  # web → api-gateway
        assert detail["dependency_count"]["downstream"] == 2  # api-gateway → user-service, api-gateway → db-primary

    def test_service_detail_no_connections(self, dashboard):
        dashboard.update_service("isolated", status="healthy")
        detail = dashboard.get_service_detail("isolated")
        assert detail["dependency_count"]["upstream"] == 0
        assert detail["dependency_count"]["downstream"] == 0


# ---------------------------------------------------------------------------
# Remove service / edge
# ---------------------------------------------------------------------------


class TestRemove:
    def test_remove_service(self, populated_dashboard):
        assert populated_dashboard.remove_service("user-service") is True
        assert "user-service" not in populated_dashboard._services

    def test_remove_service_nonexistent(self, dashboard):
        assert dashboard.remove_service("nobody") is False

    def test_remove_service_also_removes_edges(self, dashboard):
        dashboard.add_edge("a", "b")
        dashboard.add_edge("b", "c")
        dashboard.update_service("b", status="healthy")
        dashboard.remove_service("b")
        assert len(dashboard._edges) == 0

    def test_remove_edge(self, dashboard):
        dashboard.add_edge("a", "b")
        assert dashboard.remove_edge("a", "b") is True
        assert len(dashboard._edges) == 0

    def test_remove_edge_nonexistent(self, dashboard):
        assert dashboard.remove_edge("x", "y") is False


# ---------------------------------------------------------------------------
# Topology data
# ---------------------------------------------------------------------------


class TestTopologyData:
    def test_topology_data_nodes(self, populated_dashboard):
        topo = populated_dashboard.get_topology_data()
        node_ids = {n["id"] for n in topo["nodes"]}
        assert "api-gateway" in node_ids
        assert "user-service" in node_ids
        assert "db-primary" in node_ids
        assert "web" in node_ids  # from edge, not a service

    def test_topology_data_links(self, populated_dashboard):
        topo = populated_dashboard.get_topology_data()
        assert len(topo["links"]) == 3
        sources = {link["source"] for link in topo["links"]}
        assert "web" in sources

    def test_topology_node_groups(self, populated_dashboard):
        topo = populated_dashboard.get_topology_data()
        nodes = {n["id"]: n for n in topo["nodes"]}
        assert nodes["api-gateway"]["group"] == "API Layer"
        assert nodes["db-primary"]["group"] == "Database"
        # "web" (from edge) has no prefix match → should be "Other"
        assert nodes["web"]["group"] == "Other"


# ---------------------------------------------------------------------------
# Health summary
# ---------------------------------------------------------------------------


class TestHealthSummary:
    def test_no_data(self, dashboard):
        summary = dashboard.get_health_summary()
        assert summary["overall"] == "no_data"

    def test_healthy_summary(self, dashboard):
        dashboard.update_service("svc", status="healthy")
        summary = dashboard.get_health_summary()
        assert summary["overall"] == "healthy"
        assert summary["healthy"] == 1
        assert summary["issues"] == []

    def test_degraded_summary(self, dashboard):
        dashboard.update_service("svc", status="degraded", p99_ms=600.0, error_rate=0.02)
        summary = dashboard.get_health_summary()
        assert summary["overall"] == "degraded"
        assert len(summary["issues"]) == 1

    def test_unhealthy_summary(self, dashboard):
        dashboard.update_service("svc", status="unhealthy", p99_ms=3000.0, error_rate=0.10)
        summary = dashboard.get_health_summary()
        assert summary["overall"] == "unhealthy"

    def test_mixed_summary(self, dashboard):
        dashboard.update_service("healthy-svc", status="healthy")
        dashboard.update_service("bad-svc", status="unhealthy", p99_ms=5000.0, error_rate=0.20)
        dashboard.update_service("ok-svc", status="degraded", p99_ms=600.0, error_rate=0.015)
        summary = dashboard.get_health_summary()
        assert summary["overall"] == "unhealthy"
        assert summary["healthy"] == 1
        assert summary["degraded"] == 1
        assert summary["unhealthy"] == 1
        assert len(summary["issues"]) == 2


# ---------------------------------------------------------------------------
# To JSON
# ---------------------------------------------------------------------------


class TestToJSON:
    def test_to_json_compact(self, populated_dashboard):
        raw = populated_dashboard.to_json(pretty=False)
        data = json.loads(raw)
        assert data["summary"]["total"] == 3

    def test_to_json_pretty(self, populated_dashboard):
        raw = populated_dashboard.to_json(pretty=True)
        data = json.loads(raw)
        assert data["summary"]["total"] == 3

    def test_to_json_empty(self, dashboard):
        raw = dashboard.to_json()
        data = json.loads(raw)
        assert data["summary"]["total"] == 0


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_all(self, populated_dashboard):
        populated_dashboard.reset()
        assert len(populated_dashboard._services) == 0
        assert len(populated_dashboard._edges) == 0

    def test_reset_then_add(self, dashboard):
        dashboard.update_service("svc", status="healthy")
        dashboard.reset()
        assert len(dashboard._services) == 0
        dashboard.update_service("svc2", status="degraded")
        assert len(dashboard._services) == 1


# ---------------------------------------------------------------------------
# Custom config
# ---------------------------------------------------------------------------


class TestCustomConfig:
    def test_custom_thresholds(self):
        cfg = DashboardConfig(
            degrade_p99_threshold_ms=200.0,
            unhealthy_p99_threshold_ms=1000.0,
            degrade_error_threshold=0.005,
            unhealthy_error_threshold=0.02,
        )
        db = DashboardData(config=cfg)
        db.update_service("svc", p99_ms=300.0, error_rate=0.0)
        assert db._services["svc"].status == "degraded"

        db.update_service("svc2", p99_ms=1500.0, error_rate=0.0)
        assert db._services["svc2"].status == "unhealthy"

        # error_rate=0.01 > degrade threshold (0.005) but < unhealthy threshold (0.02) → degraded
        db.update_service("svc3", p99_ms=100.0, error_rate=0.01)
        assert db._services["svc3"].status == "degraded"

        # error_rate=0.03 > unhealthy threshold (0.02) → unhealthy
        db.update_service("svc4", p99_ms=100.0, error_rate=0.03)
        assert db._services["svc4"].status == "unhealthy"


# ---------------------------------------------------------------------------
# Group derivation
# ---------------------------------------------------------------------------


class TestDeriveGroup:
    def test_known_prefixes(self):
        assert DashboardData._derive_group("api-gateway") == "API Layer"
        assert DashboardData._derive_group("db-main") == "Database"
        assert DashboardData._derive_group("cache-redis") == "Cache"
        assert DashboardData._derive_group("mq-kafka") == "Message Queue"
        assert DashboardData._derive_group("worker-backfill") == "Workers"
        assert DashboardData._derive_group("web-frontend") == "Frontend"
        assert DashboardData._derive_group("auth-service") == "Authentication"
        assert DashboardData._derive_group("gateway-egress") == "Gateway"

    def test_unknown_prefix(self):
        assert DashboardData._derive_group("random-service") == "Other"

    def test_empty_name(self):
        assert DashboardData._derive_group("") == "Other"
