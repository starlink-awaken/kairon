"""Tests for sharedbrain-bridge.standalone server module."""

import pytest
from sot_bridge.sharedbrain_bridge.standalone.server import (
    app,
    circuit_engine,
    handle_circuit_execute,
    handle_health,
    handle_identity_verify,
    handle_list_services,
    handle_metrics,
    handle_register,
    main,
    mcp,
    neural_center,
    neuron_pool,
)


class TestServerImports:
    """Verify all key symbols import correctly."""

    def test_fastapi_app(self):
        """app should be a FastAPI instance with correct title."""
        assert app.title == "sharedbrain-standalone"
        assert app.version == "0.1.0"

    def test_mcp_instance(self):
        """mcp should be a FastMCP instance with correct name."""
        assert mcp.name == "sharedbrain-standalone"

    def test_neural_center_type(self):
        """neural_center should be a NeuralCenter instance."""
        from core_models.neural_center import NeuralCenter

        assert isinstance(neural_center, NeuralCenter)

    def test_circuit_engine_type(self):
        """circuit_engine should be a CircuitEngine instance."""
        from core_models.circuit_engine import CircuitEngine

        assert isinstance(circuit_engine, CircuitEngine)

    def test_neuron_pool_type(self):
        """neuron_pool should be a NeuronPool instance."""
        from core_models.neuron_pool import NeuronPool

        assert isinstance(neuron_pool, NeuronPool)

    def test_main_async_function(self):
        """main() should be a callable coroutine function."""
        import asyncio

        assert asyncio.iscoroutinefunction(main)

    def test_handler_functions_are_async(self):
        """All HTTP handler should be async functions."""
        import asyncio

        assert asyncio.iscoroutinefunction(handle_health)
        assert asyncio.iscoroutinefunction(handle_register)
        assert asyncio.iscoroutinefunction(handle_list_services)
        assert asyncio.iscoroutinefunction(handle_circuit_execute)
        assert asyncio.iscoroutinefunction(handle_identity_verify)
        assert asyncio.iscoroutinefunction(handle_metrics)


class TestAppRoutes:
    """Verify FastAPI app routes are registered."""

    def test_health_route(self):
        """POST /health route should exist."""
        routes = [r.path for r in app.routes]
        assert "/health" in routes

    def test_register_route(self):
        """POST /neural/register route should exist."""
        routes = [r.path for r in app.routes]
        assert "/neural/register" in routes

    def test_list_services_route(self):
        """GET /neural/services route should exist."""
        routes = [r.path for r in app.routes]
        assert "/neural/services" in routes

    def test_circuit_execute_route(self):
        """POST /circuit/execute route should exist."""
        routes = [r.path for r in app.routes]
        assert "/circuit/execute" in routes

    def test_identity_verify_route(self):
        """POST /v1/identity/verify route should exist."""
        routes = [r.path for r in app.routes]
        assert "/v1/identity/verify" in routes

    def test_metrics_route(self):
        """GET /metrics route should exist."""
        routes = [r.path for r in app.routes]
        assert "/metrics" in routes


class TestMCPTools:
    """Verify MCP tools are registered."""

    @pytest.mark.anyio
    async def test_mcp_has_tools(self):
        """mcp instance should have registered tools."""
        # FastMCP stores tools in internal registry
        tools = await mcp.list_tools()
        assert len(tools) > 0

    @pytest.mark.anyio
    async def test_neural_register_tool_exists(self):
        """neural_register tool should be registered."""
        tools = await mcp.list_tools()
        assert "neural_register" in {t.name for t in tools}

    @pytest.mark.anyio
    async def test_neural_list_services_tool_exists(self):
        """neural_list_services tool should be registered."""
        tools = await mcp.list_tools()
        assert "neural_list_services" in {t.name for t in tools}

    @pytest.mark.anyio
    async def test_circuit_execute_tool_exists(self):
        """circuit_execute tool should be registered."""
        tools = await mcp.list_tools()
        assert "circuit_execute" in {t.name for t in tools}

    @pytest.mark.anyio
    async def test_health_check_tool_exists(self):
        """health_check tool should be registered."""
        tools = await mcp.list_tools()
        assert "health_check" in {t.name for t in tools}

    @pytest.mark.anyio
    async def test_identity_verify_tool_exists(self):
        """identity_verify tool should be registered."""
        tools = await mcp.list_tools()
        assert "identity_verify" in {t.name for t in tools}
