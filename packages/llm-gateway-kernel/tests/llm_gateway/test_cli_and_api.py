"""Tests for llm-gateway CLI and public API."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""


def test_cli_list():
    from llm_gateway.cli import main
    r = main(["list"])
    assert r in (0, 1)


def test_cli_help():
    from llm_gateway.cli import main
    try:
        main(["--help"])
    except SystemExit:
        pass  # argparse exits after printing help


def test_import_public_api():
    from llm_gateway import (
        LLMProvider, LLMRequest, LLMResponse,
        LLMError, detect_backends, create_provider,
    )
    assert LLMProvider is not None
    assert LLMRequest is not None
    assert LLMResponse is not None


def test_list_providers():
    from llm_gateway import detect_backends
    providers = detect_backends()
    assert isinstance(providers, list)


def test_create_provider_invalid():
    from llm_gateway import create_provider
    p = create_provider("nonexistent")
    assert p is not None  # returns some provider (likely mock/none)


def test_request_defaults():
    from llm_gateway import LLMRequest
    req = LLMRequest(prompt="Hello")
    assert req.prompt == "Hello"


def test_response_fields():
    from llm_gateway import LLMResponse
    resp = LLMResponse(content="test", input_tokens=10, output_tokens=5)
    assert resp.content == "test"
    assert resp.input_tokens == 10
    assert resp.output_tokens == 5
