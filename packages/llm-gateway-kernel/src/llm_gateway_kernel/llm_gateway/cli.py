#!/usr/bin/env python3
"""llm-gateway CLI — unified LLM access from the command line.

Usage:
    llm-gateway list                     List available models
    llm-gateway generate <prompt>        Generate from prompt
    llm-gateway generate -m deepseek "Explain..."
    llm-gateway mcp                      Start MCP server
    llm-gateway serve --port 9090        Start HTTP server
"""
from __future__ import annotations

import argparse
import json
import sys

from .detection import create_provider, detect_backends
from .provider import LLMRequest


def cmd_list() -> int:
    providers = detect_backends()
    if not providers:
        print("No LLM backends available.")
        return 1
    print(f"Found {len(providers)} provider(s):")
    for p in providers:
        models = p.available_models()
        status = "🟢" if p.is_available() else "🔴"
        print(f"  {status} {p.provider_name}: {', '.join(models[:3])}")
    return 0


def cmd_generate(prompt: str, model: str | None, provider_name: str | None) -> int:
    if provider_name:
        providers = [create_provider(provider_name)]
    else:
        providers = detect_backends()
    if not providers:
        print("No LLM backends available.", file=sys.stderr)
        return 1
    provider = providers[0]
    if not provider.is_available():
        print(f"Provider {provider.provider_name} not available.", file=sys.stderr)
        return 1
    req = LLMRequest(prompt=prompt, model=model or provider.default_model)
    try:
        resp = provider.complete(req)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(resp.content)
    if resp.input_tokens:
        print(f"\n[{resp.model}] {resp.input_tokens} in / {resp.output_tokens} out", file=sys.stderr)
    return 0


def cmd_mcp() -> int:
    from .mcp_server import main as mcp_main
    mcp_main()
    return 0


def cmd_serve(port: int) -> int:
    """Start a simple HTTP server for LLM generation."""
    from .http_server import serve
    serve(port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-gateway", description="Unified LLM Gateway CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List available models")

    gen = sub.add_parser("generate", help="Generate LLM response")
    gen.add_argument("prompt")
    gen.add_argument("--model", "-m", help="Model name")
    gen.add_argument("--provider", "-p", help="Provider name (ollama, openai, ...)")

    sub.add_parser("mcp", help="Start MCP server (stdio)")

    srv = sub.add_parser("serve", help="Start HTTP server")
    srv.add_argument("--port", "-p", type=int, default=9090)

    args = parser.parse_args(argv)
    if args.cmd == "list":
        return cmd_list()
    elif args.cmd == "generate":
        return cmd_generate(args.prompt, args.model, args.provider)
    elif args.cmd == "mcp":
        return cmd_mcp()
    elif args.cmd == "serve":
        return cmd_serve(args.port)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
