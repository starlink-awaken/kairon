"""mcp_gateway — central MCP backend registration for all kairon packages.

Starts and registers all internal MCP backend services through agora's
ProxyManager, making them available via the unified MCP entry points
(ports 7430/7431). Other packages must NOT expose independent MCP ports.

Usage:
    python -m agora.mcp_gateway          # CLI mode (starts all, waits for signal)
    from agora.auth.mcp_gateway import start_all, stop_all
"""

from __future__ import annotations

import asyncio
import os
import signal
import tomllib
from pathlib import Path

import structlog

from agora.mcp_proxy.manager import ProxyManager

logger = structlog.get_logger(__name__)

# ── Known MCP backends ────────────────────────────────────────────
# Each entry defines how ProxyManager should launch the service.
# These commands must be available on $PATH (installed via pip/uv).
# The MCP script entry points (e.g. ``eidos-mcp``) in each package's
# ``pyproject.toml`` remain intact — they are consumed here as stdio
# commands by ProxyManager.

KNOWN_BACKENDS: list[dict] = [
    {
        "name": "agent-runtime",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "agent-runtime", "python", "-m", "agent_runtime.mcp_server"],
    },
    {
        "name": "eidos",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "eidos", "python", "-m", "eidos.mcp_server"],
    },
    {
        "name": "iris",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "iris", "python", "-m", "iris.mcp_server"],
    },
    {
        "name": "kronos",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "kronos", "python", "-m", "kronos.mcp_server"],
    },
    {
        "name": "metaos",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "metaos", "python", "-m", "metaos.mcp_server"],
    },
    {
        "name": "minerva",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "minerva", "python", "-m", "minerva.mcp_server.server"],
    },
    {
        "name": "sophia",
        "mcp_endpoint": "",
        "command": "uv",
        "args": ["run", "--package", "sophia", "python", "-m", "sophia.server.mcp_server"],
    },
    {
        "name": "cron-service",
        "mcp_endpoint": "",
        "command": "cron-service",
        "args": ["--mcp"],
    },
]

def discover_mcp_backends() -> list[dict]:
    """Dynamically discover MCP backends from kairon packages."""
    candidates = [
        Path(__file__).resolve().parents[3] / "packages",
        Path.cwd() / "packages",
        Path.cwd() / "projects" / "kairon" / "packages",
    ]
    packages_dir = next((path for path in candidates if path.exists()), None)
    if packages_dir is None:
        return []

    backends = []
    for pkg_dir in packages_dir.iterdir():
        if not pkg_dir.is_dir() or not (pkg_dir / "pyproject.toml").exists():
            continue
        try:
            with open(pkg_dir / "pyproject.toml", "rb") as f:
                config = tomllib.load(f)
            pkg_name = config.get("project", {}).get("name")
            if not pkg_name: continue

            mcp_module = None
            for root, _, files in os.walk(pkg_dir):
                if "test" in root: continue
                if "mcp_server.py" in files:
                    mcp_module = "mcp_server"
                elif "server.py" in files and ("mcp" in root or "standalone" in root):
                    mcp_module = "server"
                else:
                    continue

                rel_path = Path(root).relative_to(pkg_dir)
                parts = list(rel_path.parts)
                if parts and parts[0] == "src":
                    parts = parts[1:]
                mod_name = ".".join(parts + [mcp_module])
                
                backends.append({
                    "name": pkg_name,
                    "mcp_endpoint": "",
                    "command": "uv",
                    "args": ["run", "--package", pkg_name, "python", "-m", mod_name]
                })
                break
        except Exception as e:
            logger.warning("mcp_gateway_discovery_error", package=pkg_dir.name, error=str(e))
    return backends

# Module-level singleton — reused across start/stop calls.
_gateway_manager: ProxyManager | None = None


async def start_all() -> dict[str, str]:
    """Start all known backends and register them with the proxy.

    Returns a dict mapping service name → result string ("ok: N tools registered"
    or "error: ..."). Each connection is attempted in parallel.
    """
    global _gateway_manager
    if _gateway_manager is None:
        _gateway_manager = ProxyManager()

    backends = list(KNOWN_BACKENDS)
    known_names = {backend["name"] for backend in backends}
    discovered = [backend for backend in discover_mcp_backends() if backend["name"] not in known_names]
    if discovered:
        backends.extend(discovered)
        logger.info("mcp_gateway_discovered_backends", count=len(discovered), services=[b["name"] for b in discovered])

    results = await _gateway_manager.start(backends)
    ok_count = sum(1 for v in results.values() if v.startswith("ok"))
    logger.info("mcp_gateway_started", ok=ok_count, failed=len(results) - ok_count, services=list(results.keys()))
    return results


async def stop_all() -> None:
    """Stop all known backends and clean up the proxy manager.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _gateway_manager
    if _gateway_manager is not None:
        await _gateway_manager.shutdown()
        _gateway_manager = None
        logger.info("mcp_gateway_stopped")


def main() -> None:
    """CLI entry point — start all known MCP backends and wait for signal."""

    async def _run() -> None:
        logger.info("mcp_gateway_starting")
        await start_all()

        # Block until SIGINT or SIGTERM is received.
        stop_event = asyncio.Event()

        def _signal_handler() -> None:
            logger.info("mcp_gateway_shutdown_signal_received")
            stop_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                # Windows or non-POSIX — fall back to polling
                logger.warning("mcp_gateway_signal_not_supported", sig=sig)

        await stop_event.wait()
        await stop_all()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
