"""Standalone HTTP/MCP server — wraps sharedbrain-core as a deployable service.

Wraps sharedbrain-core as a deployable service with a FastAPI HTTP server
on port 8000 and a FastMCP MCP server on port 8001.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

from core_models.circuit_engine import CircuitEngine
from core_models.neural_center import NeuralCenter
from core_models.neuron_pool import NeuronPool
from core_models.protocols.circuit import CircuitDefinition, CircuitStep
from core_models.protocols.identity import IdentityResult
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastmcp import FastMCP

# ── Shared state ──────────────────────────────────────────────────────────

neural_center = NeuralCenter()
circuit_engine = CircuitEngine()
neuron_pool = NeuronPool()
_request_count: int = 0
_start_time: float = time.time()

# ── FastAPI HTTP server (port 8000) ──────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await neural_center.start_health_checker(interval=30.0)
    yield
    await neural_center.stop_health_checker()
    await neuron_pool.close()


app = FastAPI(title="sharedbrain-standalone", version="0.1.0", lifespan=lifespan)


def _incr() -> int:
    global _request_count
    _request_count += 1
    return _request_count


@app.post("/neural/register")
async def handle_register(request: Request):
    _incr()
    body = await request.json()
    name = body.get("name", "")
    endpoint = body.get("endpoint", "")
    caps = body.get("capabilities")
    meta = body.get("metadata")
    result = await neural_center.register(name, endpoint, capabilities=caps, metadata=meta)
    return {
        "name": name,
        "passed": result.passed,
        "neuron_id": result.neuron_id,
        "required_failed": result.required_failed,
    }


@app.get("/neural/services")
async def handle_list_services():
    _incr()
    services = await neural_center.list_services()
    return {
        "total": len(services),
        "services": [
            {
                "name": s.name,
                "endpoint": s.endpoint,
                "capabilities": s.capabilities,
                "neuron_id": s.neuron_id,
                "registered_at": s.registered_at,
            }
            for s in services
        ],
    }


@app.post("/circuit/execute")
async def handle_circuit_execute(request: Request):
    _incr()
    body = await request.json()
    yaml_text = body.get("circuit_yaml", "")
    context = body.get("context", {})

    if yaml_text:
        circuit = circuit_engine.parse_circuit(yaml_text)
    elif body.get("name"):
        steps_data = body.get("steps", [])
        steps = [CircuitStep(**s) for s in steps_data]
        sla = body.get("sla", {})
        circuit = CircuitDefinition(
            name=body["name"],
            version=body.get("version", "1.0"),
            description=body.get("description", ""),
            trigger=body.get("trigger", ""),
            sla_p99_ms=sla.get("p99_ms", 100),
            sla_timeout_ms=sla.get("timeout_ms", 1000),
            steps=steps,
        )
    else:
        return {"error": "Provide circuit_yaml or name+steps"}, 400

    run = await circuit_engine.execute_circuit(circuit, context)
    return {"run_id": run.run_id, "status": run.status, "error": run.error}


@app.get("/health")
async def handle_health():
    _incr()
    summary = await neural_center.get_health_summary()
    unhealthy = summary.get("unhealthy", 0)
    return {
        "status": "healthy" if unhealthy == 0 else "degraded",
        "version": "0.1.0",
        "uptime_seconds": round(time.time() - _start_time, 2),
        "services": summary,
    }


@app.post("/v1/identity/verify")
async def handle_identity_verify(request: Request):
    _incr()
    body = await request.json()
    principal = body.get("principal", "")
    result = IdentityResult(
        identity_id=f"id-{principal}",
        principal=principal,
        authenticated=True,
        roles=["user"],
        permissions=["read", "write"],
    )
    return {
        "identity_id": result.identity_id,
        "principal": result.principal,
        "authenticated": result.authenticated,
        "roles": result.roles,
        "permissions": result.permissions,
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def handle_metrics():
    uptime = time.time() - _start_time
    services = await neural_center.list_services()
    return PlainTextResponse(
        "# HELP sharedbrain_http_requests_total Total HTTP requests\n"
        "# TYPE sharedbrain_http_requests_total counter\n"
        f"sharedbrain_http_requests_total {_request_count}\n"
        "# HELP sharedbrain_uptime_seconds Server uptime\n"
        "# TYPE sharedbrain_uptime_seconds gauge\n"
        f"sharedbrain_uptime_seconds {uptime:.0f}\n"
        "# HELP sharedbrain_registered_services Total registered services\n"
        "# TYPE sharedbrain_registered_services gauge\n"
        f"sharedbrain_registered_services {len(services)}\n"
    )


# ── FastMCP MCP server (port 8001) ───────────────────────────────────────

mcp = FastMCP("sharedbrain-standalone")


@mcp.tool()
async def neural_register(
    name: str,
    endpoint: str,
    capabilities: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """Register a service with the neural center."""
    result = await neural_center.register(name, endpoint, capabilities=capabilities, metadata=metadata)
    return {
        "name": name,
        "passed": result.passed,
        "neuron_id": result.neuron_id,
        "required_failed": result.required_failed,
    }


@mcp.tool()
async def neural_list_services() -> dict:
    """List all registered services in the neural center."""
    services = await neural_center.list_services()
    return {
        "total": len(services),
        "services": [
            {
                "name": s.name,
                "endpoint": s.endpoint,
                "capabilities": s.capabilities,
                "neuron_id": s.neuron_id,
            }
            for s in services
        ],
    }


@mcp.tool()
async def circuit_execute(circuit_yaml: str, context: dict | None = None) -> dict:
    """Execute a circuit from YAML definition and return the run result."""
    circuit = circuit_engine.parse_circuit(circuit_yaml)
    run = await circuit_engine.execute_circuit(circuit, context or {})
    return {"run_id": run.run_id, "status": run.status, "error": run.error}


@mcp.tool()
async def health_check() -> dict:
    """Probe health of this service and all registered services."""
    summary = await neural_center.get_health_summary()
    return {
        "status": "healthy" if summary.get("unhealthy", 0) == 0 else "degraded",
        "uptime_seconds": round(time.time() - _start_time, 2),
        "services": summary,
    }


@mcp.tool()
async def identity_verify(principal: str, credentials: dict | None = None) -> dict:
    """Verify a principal's identity. Standalone mode auto-authenticates."""
    result = IdentityResult(
        identity_id=f"id-{principal}",
        principal=principal,
        authenticated=True,
        roles=["user"],
        permissions=["read", "write"],
    )
    return {
        "identity_id": result.identity_id,
        "principal": result.principal,
        "authenticated": result.authenticated,
        "roles": result.roles,
        "permissions": result.permissions,
    }


# ── Concurrent runner ────────────────────────────────────────────────────


async def run_http_server():
    """Run the FastAPI HTTP server via uvicorn."""
    import uvicorn

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")  # noqa: S104
    server = uvicorn.Server(config)
    await server.serve()


async def run_mcp_server():
    """Run the FastMCP MCP server over HTTP/SSE on port 8001."""
    await mcp.run_http_async(host="0.0.0.0", port=8001)  # noqa: S104


async def main():
    """Run both HTTP and MCP servers concurrently."""
    await asyncio.gather(run_http_server(), run_mcp_server())


if __name__ == "__main__":
    asyncio.run(main())
