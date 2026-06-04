# Contributing to Agora

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Git

### Clone and Install

```bash
git clone <repo-url>
cd packages/agora
uv sync --dev
```

### Activate Virtual Environment

```bash
source .venv/bin/activate
```

## Project Structure

```
src/agora/
├── cli/                  # CLI command implementations
│   ├── __init__.py       # Entry point & dispatch
│   ├── parser.py         # Argparse definitions
│   └── commands_*.py     # Command handlers
├── server/
│   └── mcp.py            # FastMCP server & all tool endpoints
├── mcp_proxy/
│   ├── manager.py        # ProxyManager — downstream connection lifecycle
│   ├── registry.py       # ProxyRegistry — tool-to-service mapping
│   └── idle_timeout.py   # Idle timeout management
├── mcp_registry/
│   ├── repository.py     # ToolCatalog — SQLite-backed tool metadata store
│   ├── lifecycle.py      # LifecycleManager — dynamic load/unload
│   ├── router.py         # SmartRouter — query routing
│   ├── orchestrator.py   # Orchestrator — high-level workflow coordination
│   ├── embeddings.py     # EmbeddingStore — semantic search
│   ├── evaluator.py      # QualityScorer — tool quality evaluation
│   └── sources.py        # External search sources (GitHub, registry)
├── event_bus.py          # EventBus — publish/subscribe
├── registry.py           # ServiceRegistry — core service registry
├── authorizer.py         # Authorizer — access control
├── identity_ca.py        # IdentityCA — certificate management
└── mcp_bootstrap.py      # KNOWN_SERVICES auto-discovery
tests/
├── conftest.py           # Shared fixtures (network check, FakeToolCatalog)
├── test_*.py             # Unit/integration tests
└── e2e/                  # End-to-end tests
```

## Running Tests

```bash
# Run all tests (excluding e2e)
python -m pytest tests/ --ignore=tests/e2e -v

# Run specific test file
python -m pytest tests/test_cli.py -v

# Run with network-dependent tests
python -m pytest tests/ -m network -v

# Run tests matching a keyword
python -m pytest tests/ -k "lifecycle" -v

# Run with coverage
python -m pytest tests/ --ignore=tests/e2e --cov=src/agora
```

### Test Fixtures

Shared fixtures are defined in `tests/conftest.py`:

- `network_available` — Session-scoped, checks github.com:443 reachability
- `_skip_if_no_network` — Autouse, skips `@pytest.mark.network` tests offline
- `clean_env` — Autouse, cleans AGORA_/OPENAI_/ANTHROPIC_ env vars
- `fake_tool_catalog` — Fresh `FakeToolCatalog` instance per test
- `FakeToolCatalog` class — In-memory ToolCatalog for unit tests

### Markers

- `network` — Tests requiring internet access (github.com)

## Code Style

- **Formatting**: [Ruff](https://github.com/astral-sh/ruff) with default config
- **Type hints**: All public functions must have type annotations
- **Docstrings**: Google-style docstrings for public APIs
- **Imports**: Use `from __future__ import annotations` in all files

```bash
# Format code
ruff check --fix src/agora/

# Type check
pyright src/agora/
```

## Architecture Guidelines

### Three-Layer Model

```
[CLI Layer]   → parser.py + commands_*.py
[Server Layer] → server/mcp.py (FastMCP tools)
[Core Layer]  → mcp_proxy/, mcp_registry/, event_bus.py
```

- CLI commands should be thin wrappers that delegate to core layer functions.
- Server tools (`@mcp.tool()`) validate input and call core layer.
- Core layer has no dependency on CLI or server modules.

### Return Format

All server tool functions return `dict` using helpers:
- `_ok(data=None, message="")` — Success response
- `_error(message, code="")` — Error response

Both produce dicts with `FORMAT_VERSION = "agora-v1"`.

### Adding a New CLI Command

1. Define the argparse subparser in `parser.py`
2. Create or update `commands_*.py` with the handler function
3. Add the `elif` dispatch branch in `cli/__init__.py`
4. Add tests in `tests/test_cli.py`

### Adding a New MCP Tool

1. Define the tool function in `server/mcp.py` with `@mcp.tool()`
2. Use `_ok()` / `_error()` for return values
3. Register any proxy-level handlers if needed
4. Add tests in `tests/test_mcp_server.py`

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for any new functionality
3. Ensure all tests pass: `python -m pytest tests/ --ignore=tests/e2e`
4. Run type checking: `pyright src/agora/`
5. Run linting: `ruff check src/agora/`
6. Submit a PR with a clear description of changes

## Known Issues

- `agent_runtime` module is required for degrade tests but may not be installed
- e2e tests require the `agora` CLI binary in PATH
