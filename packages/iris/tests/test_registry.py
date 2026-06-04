"""Tests for connector registry."""

import pytest
from iris.base import BaseConnector
from iris.registry import ConnectorRegistry


class MockConnector(BaseConnector):
    name = "mock"
    display_name = "Mock Platform"

    def is_available(self):
        return True

    def list_items(self, limit=20, cursor=None):
        return []

    def get_item(self, id):
        return None

    def search(self, query, limit=10):
        return []

    def status(self):
        return {"mock": True}


class UnavailableConnector(BaseConnector):
    name = "unavailable"
    display_name = "Unavailable"

    def is_available(self):
        return False

    def list_items(self, limit=20, cursor=None):
        return []

    def get_item(self, id):
        return None

    def search(self, query, limit=10):
        return []

    def status(self):
        return {"available": False}


class TestRegistry:
    def test_register_and_get(self):
        registry = ConnectorRegistry()
        conn = MockConnector()
        registry.register(conn)
        assert registry.get("mock") is conn

    def test_register_empty_name_raises(self):
        registry = ConnectorRegistry()
        conn = MockConnector()
        conn.name = ""
        with pytest.raises(ValueError):
            registry.register(conn)

    def test_list(self):
        registry = ConnectorRegistry()
        registry.register(MockConnector())
        registry.register(UnavailableConnector())
        assert len(registry.list_all()) == 2

    def test_list_names(self):
        registry = ConnectorRegistry()
        registry.register(MockConnector())
        assert registry.list_names() == ["mock"]

    def test_unregister(self):
        registry = ConnectorRegistry()
        conn = MockConnector()
        registry.register(conn)
        registry.unregister("mock")
        assert registry.get("mock") is None

    def test_contains(self):
        registry = ConnectorRegistry()
        registry.register(MockConnector())
        assert "mock" in registry
        assert "nope" not in registry

    def test_status_all(self):
        registry = ConnectorRegistry()
        registry.register(MockConnector())
        registry.register(UnavailableConnector())
        statuses = registry.status_all()
        assert len(statuses) == 2
        status_map = {s["name"]: s for s in statuses}
        assert status_map["mock"]["available"] is True
        assert status_map["unavailable"]["available"] is False

    def test_len(self):
        registry = ConnectorRegistry()
        assert len(registry) == 0
        registry.register(MockConnector())
        assert len(registry) == 1
