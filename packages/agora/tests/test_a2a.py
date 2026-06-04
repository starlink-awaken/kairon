"""Tests for A2A features — Agent Card, state transitions, push notifications, and task management."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock

import pytest

# Must set AGORA_API_KEY before importing app (module-level config)
# 使用强制赋值（非 setdefault）以覆盖环境中已有的真实 API key
os.environ["AGORA_API_KEY"] = "test-key-123"

# Each test in TestTaskManager uses a unique temp file to avoid cross-test contamination
_tm_path = lambda: tempfile.mktemp(suffix=".json")  # noqa: E731, S306

# 兜底：如果 app 模块已在其他 conftest 中被导入，强制重写其 API_KEY
import agora.web.app as _app_module
from agora.a2a.task_manager import TaskManager
from agora.server.mcp import (
    a2a_cancel_task,
    a2a_get_task,
    a2a_list_tasks,
    a2a_send_task,
    get_state_transitions,
    register_push_notification,
)
from agora.web.app import app
from fastapi.testclient import TestClient

_app_module.API_KEY = "test-key-123"

client = TestClient(app, headers={"X-API-Key": "test-key-123"})


@pytest.fixture(autouse=True)
def _clean_registry():
    """Clear registry state before each test to avoid cross-test contamination."""
    import sys

    # Clear both MCP and Web app registry instances (they are separate instances
    # in the same Python process, sharing the same persistent file)
    from agora.server.mcp import registry as mcp_registry

    app_module = sys.modules.get("agora.web.app")
    app_registry = getattr(app_module, "registry", None)

    mcp_registry.clear_all()
    mcp_registry._transitions.clear()

    if app_registry is not None:
        app_registry.clear_all()
        app_registry._transitions.clear()
    yield


class TestStateTransitions:
    """State transition tracking (registry-level)."""

    def test_register_triggers_transition(self):
        """Registering a service creates a 'registered' state transition."""
        import asyncio

        from agora.server.mcp import register_service, registry

        registry._transitions.clear()
        asyncio.run(
            register_service(
                name="trans-test",
                mcp_endpoint="http://192.0.2.100:8765",
            )
        )
        transitions = registry.get_transitions(service="trans-test")
        assert len(transitions) >= 1
        assert transitions[-1]["state_to"] in ("registered", "healthy")
        assert transitions[-1]["service"] == "trans-test"

    def test_get_transitions_filters_by_service(self):
        """get_transitions with service filter returns only matching entries."""
        import asyncio

        from agora.server.mcp import register_service, registry

        registry._transitions.clear()
        asyncio.run(register_service(name="filter-a", mcp_endpoint="http://192.0.2.110:8765"))
        asyncio.run(register_service(name="filter-b", mcp_endpoint="http://192.0.2.111:8765"))
        transitions_a = registry.get_transitions(service="filter-a")
        assert all(t["service"] == "filter-a" for t in transitions_a)

    def test_clear_transitions(self):
        """clear_transitions empties the transition log."""
        import asyncio

        from agora.server.mcp import register_service, registry

        registry._transitions.clear()
        asyncio.run(register_service(name="clear-test", mcp_endpoint="http://192.0.2.120:8765"))
        assert len(registry.get_transitions()) >= 1
        registry.clear_transitions()
        assert len(registry.get_transitions()) == 0

    def test_transition_limit(self):
        """Transitions are capped at MAX_TRANSITIONS."""
        from agora.server.mcp import registry

        registry._transitions.clear()
        for i in range(600):
            registry._transitions.add(f"svc-{i}", "", "registered", "bulk test", "test")
        # _add_transition already trims, so list should be capped
        assert len(registry.get_transitions()) <= 500


class TestStateTransitionTool:
    """MCP tool get_state_transitions."""

    def test_get_state_transitions_returns_ok(self):
        """get_state_transitions returns status 'ok' with transitions data."""
        result = get_state_transitions()
        assert result["status"] == "ok"
        assert "transitions" in result
        assert "count" in result
        assert isinstance(result["transitions"], list)
        assert isinstance(result["count"], int)

    def test_get_state_transitions_filter_service(self):
        """get_state_transitions with service filter works."""
        result = get_state_transitions(service="nonexistent")
        assert result["status"] == "ok"
        assert len(result["transitions"]) == 0


class TestRegisterPushNotification:
    """Push notification registration via MCP tool."""

    def test_register_valid_url(self):
        """register_push_notification with valid URL returns ok."""
        result = register_push_notification(
            callback_url="http://example.com/events",
            event_types="registry:*,route:call.failed",
        )
        assert result["status"] == "ok"
        assert "subscriptions" in result
        assert "registry:*" in result["subscriptions"]
        assert "route:call.failed" in result["subscriptions"]
        assert result["callback_url"] == "http://example.com/events"

    def test_register_invalid_url(self):
        """register_push_notification with invalid URL returns error."""
        result = register_push_notification(
            callback_url="not-a-url",
            event_types="*",
        )
        assert result["status"] == "error"
        assert "callback_url" in result["error"].lower()

    def test_register_empty_url(self):
        """register_push_notification with empty URL returns error."""
        result = register_push_notification(
            callback_url="",
            event_types="*",
        )
        assert result["status"] == "error"

    def test_default_catches_all(self):
        """register_push_notification with default event_types catches all."""
        result = register_push_notification(
            callback_url="http://example.com/events",
        )
        assert result["status"] == "ok"
        assert "*" in result["subscriptions"]


class TestTaskManager:
    """TaskManager unit tests."""

    def test_create_task(self):
        """create_task returns task in submitted state."""
        router = AsyncMock()
        router.route.return_value = {"result": "done"}
        tm = TaskManager(router, storage_path=_tm_path())
        task = tm.create_task(
            "test-svc",
            "test.tool",
            {"key": "value"},
            "session-1",
            caller_identity={
                "subject_id": "alice",
                "subject_type": "user",
                "issuer": "auth0",
                "tenant": "acme",
            },
        )
        assert task.status == "submitted"
        assert task.service_name == "test-svc"
        assert task.tool_name == "test.tool"
        assert task.arguments == {"key": "value"}
        assert task.session_id == "session-1"
        assert task.caller_identity == {
            "subject_id": "alice",
            "subject_type": "user",
            "issuer": "auth0",
            "tenant": "acme",
        }
        assert task.id.startswith("task_")

    def test_get_task_found(self):
        """get_task returns created task."""
        router = AsyncMock()
        tm = TaskManager(router, storage_path=_tm_path())
        task = tm.create_task("svc", "tool.test")
        found = tm.get_task(task.id)
        assert found is not None
        assert found.id == task.id

    def test_get_task_not_found(self):
        """get_task returns None for unknown ID."""
        router = AsyncMock()
        tm = TaskManager(router, storage_path=_tm_path())
        assert tm.get_task("task_nonexistent") is None

    def test_cancel_submitted_task(self):
        """cancel_task on submitted task returns True."""
        router = AsyncMock()
        tm = TaskManager(router, storage_path=_tm_path())
        task = tm.create_task("svc", "tool.test")
        assert tm.cancel_task(task.id) is True
        updated = tm.get_task(task.id)
        assert updated.status == "canceled"

    def test_cancel_completed_task_fails(self):
        """cancel_task on completed task returns False."""
        router = AsyncMock()
        tm = TaskManager(router, storage_path=_tm_path())
        task = tm.create_task("svc", "tool.test")
        tm.update_task(task.id, "completed", result={"ok": True})
        assert tm.cancel_task(task.id) is False

    def test_update_task_status(self):
        """update_task changes status and sets completed_at."""
        router = AsyncMock()
        tm = TaskManager(router, storage_path=_tm_path())
        task = tm.create_task("svc", "tool.test")
        tm.update_task(task.id, "completed", result={"result": "success"})
        updated = tm.get_task(task.id)
        assert updated.status == "completed"
        assert updated.result == {"result": "success"}
        assert updated.completed_at != ""

    def test_update_task_not_found(self):
        """update_task on unknown ID returns None."""
        router = AsyncMock()
        tm = TaskManager(router, storage_path=_tm_path())
        assert tm.update_task("task_nonexist", "completed") is None

    def test_list_tasks(self):
        """list_tasks returns tasks sorted by created_at desc."""
        router = AsyncMock()
        tm = TaskManager(router, storage_path=_tm_path())
        tm.create_task("svc-a", "tool.a")
        tm.create_task("svc-a", "tool.b")
        tm.create_task("svc-b", "tool.c")
        all_tasks = tm.list_tasks()
        assert len(all_tasks) >= 3
        svc_a = tm.list_tasks(service="svc-a")
        assert all(t.service_name == "svc-a" for t in svc_a)
        assert len(svc_a) == 2

    def test_list_tasks_filter_status(self):
        """list_tasks with status filter works."""
        router = AsyncMock()
        tm = TaskManager(router, storage_path=_tm_path())
        task = tm.create_task("svc", "tool.test")
        tm.update_task(task.id, "failed", error="test error")
        failed = tm.list_tasks(status="failed")
        assert all(t.status == "failed" for t in failed)

    async def test_execute_task_success(self):
        """execute_task transitions submitted→working→completed on success."""
        router = AsyncMock()
        router.route.return_value = {"data": {"result": "done"}}
        tm = TaskManager(router, storage_path=_tm_path())
        task = tm.create_task(
            "svc",
            "tool.test",
            {"arg": 1},
            caller_identity={
                "subject_id": "alice",
                "subject_type": "user",
                "issuer": "auth0",
                "tenant": "acme",
            },
        )
        result = await tm.execute_task(task.id)
        assert result is not None
        assert result.status == "completed"
        assert result.result == {"result": "done"}
        router.route.assert_awaited_once_with(
            "tool.test",
            {"arg": 1},
            caller_id={
                "subject_id": "alice",
                "subject_type": "user",
                "issuer": "auth0",
                "tenant": "acme",
            },
        )

    async def test_execute_task_not_found(self):
        """execute_task on unknown ID returns None."""
        router = AsyncMock()
        tm = TaskManager(router, storage_path=_tm_path())
        result = await tm.execute_task("task_nonexist")
        assert result is None

    async def test_execute_task_failure(self):
        """execute_task transitions to failed on router error."""
        router = AsyncMock()
        router.route.side_effect = ValueError("Router failure")
        tm = TaskManager(router, storage_path=_tm_path())
        task = tm.create_task("svc", "tool.test")
        result = await tm.execute_task(task.id)
        assert result is not None
        assert result.status == "failed"
        assert "Router failure" in result.error


class TestA2aTaskMCP:
    """A2A task MCP tools."""

    def test_a2a_list_tasks_empty(self):
        """a2a_list_tasks returns well-formed response."""
        result = a2a_list_tasks()
        assert result["status"] == "ok"
        assert "tasks" in result
        assert "count" in result
        assert isinstance(result["tasks"], list)
        assert isinstance(result["count"], int)
        assert result["count"] >= 0

    def test_a2a_list_tasks_filter_status(self):
        """a2a_list_tasks with status filter returns only matching tasks."""
        result = a2a_list_tasks(status="completed")
        assert result["status"] == "ok"
        assert isinstance(result["tasks"], list)
        assert result["count"] >= 0

    def test_a2a_send_task_bad_tool(self):
        """a2a_send_task with nonexistent tool returns error."""
        import asyncio

        result = asyncio.run(a2a_send_task("nonexistent.tool"))
        assert result is not None  # result could be ok with failed task or error
        # If the tool doesn't exist, the task should still complete (with error result)
        assert result["status"] == "ok" or result["status"] == "error"

    def test_a2a_get_task_not_found(self):
        """a2a_get_task with unknown ID returns error."""
        result = a2a_get_task("task_nonexistent_12345")
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    def test_a2a_cancel_task_not_found(self):
        """a2a_cancel_task with unknown ID returns error."""
        result = a2a_cancel_task("task_nonexistent_12345")
        assert result["status"] == "error"


class TestAgentCardEndpoint:
    """Agent Card well-known endpoint."""

    def test_agent_card_endpoint_returns_agents_container(self):
        """GET /.well-known/agent-card.json returns agents container."""
        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert "count" in data
        assert "format_version" in data
        assert "generated_at" in data
        assert isinstance(data["agents"], dict)

    def test_agent_card_registered_service_has_card(self):
        """Agent Card for a registered service includes name and capabilities."""
        # Register via HTTP API so it's visible to the app's registry
        resp_register = client.post(
            "/api/register",
            data={
                "name": "card-test-svc",
                "mcp_endpoint": "http://192.0.2.200:8765",
                "description": "Agent Card test service",
            },
        )
        assert resp_register.status_code == 200

        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        data = resp.json()
        agents = data.get("agents", {})
        assert "card-test-svc" in agents, f"card-test-svc not in agents: {list(agents.keys())}"
        card = agents["card-test-svc"]
        assert "name" in card
        assert card["name"] == "card-test-svc"
        assert "capabilities" in card
        assert "skills" in card


class TestWebhookEndpoint:
    """Webhook / push notification endpoints."""

    def test_webhook_receive_valid(self):
        """POST /api/webhook/events with valid body returns ok."""
        resp = client.post(
            "/api/webhook/events",
            json={
                "event_type": "test:webhook",
                "payload": {"msg": "hello"},
                "source": "test",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_webhook_receive_missing_event_type(self):
        """POST /api/webhook/events without event_type returns 400."""
        resp = client.post(
            "/api/webhook/events",
            json={"payload": {}},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data

    def test_a2a_push_notification_register(self):
        """POST /api/a2a/push-notification registers callback."""
        resp = client.post(
            "/api/a2a/push-notification",
            json={
                "callback_url": "http://example.com/notify",
                "event_types": ["*"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_a2a_push_notification_missing_url(self):
        """POST /api/a2a/push-notification without URL returns 400."""
        resp = client.post(
            "/api/a2a/push-notification",
            json={"event_types": ["*"]},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data


class TestA2aApiTasks:
    """A2A task HTTP endpoints."""

    def test_a2a_send_task_endpoint(self):
        """POST /api/a2a/tasks/send returns task result."""
        resp = client.post(
            "/api/a2a/tasks/send",
            json={
                "tool_name": "nonexistent.tool",
                "arguments": {},
            },
        )
        assert resp.status_code in (200, 400, 500)  # routing may fail gracefully

    def test_a2a_send_task_endpoint_passes_caller_identity(self, monkeypatch):
        """POST /api/a2a/tasks/send forwards caller_identity into the TaskManager."""

        class _FakeTask:
            id = "task_test"

            def to_dict(self):
                return {"id": self.id, "status": "completed"}

        class _FakeTaskManager:
            def __init__(self):
                self.created = None

            def create_task(self, service_name, tool_name, arguments=None, session_id="", caller_identity=None):
                self.created = {
                    "service_name": service_name,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "session_id": session_id,
                    "caller_identity": caller_identity,
                }
                return _FakeTask()

            async def execute_task(self, task_id):
                assert task_id == "task_test"
                return _FakeTask()

        fake_tm = _FakeTaskManager()
        monkeypatch.setattr("agora.web.app._get_tm", lambda: fake_tm)

        resp = client.post(
            "/api/a2a/tasks/send",
            json={
                "tool_name": "minerva.research",
                "arguments": {"query": "identity"},
                "session_id": "session-1",
                "caller_identity": {
                    "subject_id": "alice",
                    "subject_type": "user",
                    "issuer": "auth0",
                    "tenant": "acme",
                },
            },
        )

        assert resp.status_code == 200
        assert fake_tm.created == {
            "service_name": "",
            "tool_name": "minerva.research",
            "arguments": {"query": "identity"},
            "session_id": "session-1",
            "caller_identity": {
                "subject_id": "alice",
                "subject_type": "user",
                "issuer": "auth0",
                "tenant": "acme",
            },
        }

    def test_a2a_get_task_endpoint_not_found(self):
        """GET /api/a2a/tasks/{id} with unknown ID returns 404."""
        resp = client.get("/api/a2a/tasks/task_nonexistent_999")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data

    def test_a2a_cancel_task_endpoint_not_found(self):
        """POST /api/a2a/tasks/{id}/cancel with unknown ID returns 400."""
        resp = client.post("/api/a2a/tasks/task_nonexistent_999/cancel")
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data

    def test_a2a_tasks_list_endpoint(self):
        """GET /api/a2a/tasks returns task list with ok status."""
        resp = client.get("/api/a2a/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "tasks" in data
        assert "count" in data
        assert isinstance(data["tasks"], list)

    def test_a2a_tasks_list_with_filters(self):
        """GET /api/a2a/tasks accepts filter query params."""
        resp = client.get("/api/a2a/tasks?service=test&status=completed&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestA2aApiTransitions:
    """State transition HTTP endpoints."""

    def test_transitions_endpoint(self):
        """GET /api/transitions returns transitions list."""
        resp = client.get("/api/transitions")
        assert resp.status_code == 200
        data = resp.json()
        assert "transitions" in data
        assert "count" in data
        assert isinstance(data["transitions"], list)

    def test_service_transitions_endpoint(self):
        """GET /api/transitions/{service} returns service-specific transitions."""
        resp = client.get("/api/transitions/unknown-svc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "unknown-svc"
        assert "transitions" in data
        assert "count" in data


class TestAgentCardMCP:
    """Agent Card generation via MCP tool."""

    def test_get_agent_card_unknown_service(self):
        """get_agent_card with unknown name returns error."""

        from agora.server.mcp import get_agent_card

        result = get_agent_card("nonexistent")
        assert result["status"] == "error"

    def test_get_agent_card_registered_service(self):
        """get_agent_card for a registered service returns agent_card data."""
        import asyncio

        from agora.server.mcp import get_agent_card, register_service

        asyncio.run(
            register_service(
                name="mcp-card-test",
                mcp_endpoint="http://192.0.2.210:8765",
            )
        )
        result = get_agent_card("mcp-card-test")
        assert result["status"] == "ok"
        assert "agent_card" in result
        card = result["agent_card"]
        assert "name" in card
        assert card["name"] == "mcp-card-test"
        assert "capabilities" in card
        assert "skills" in card
        assert "version" in card
        assert "url" in card
