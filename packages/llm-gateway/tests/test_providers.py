"""Tests for llm-gateway provider ABC."""
from __future__ import annotations

from llm_gateway.provider import LLMRequest, LLMResponse, MockLLMProvider, NoneProvider


def test_mock_provider():
    p = MockLLMProvider()
    assert p.provider_name == "mock"
    assert p.is_available()


def test_none_provider():
    p = NoneProvider()
    assert p.provider_name == "none"
    assert p.is_available()


def test_llm_request_defaults():
    r = LLMRequest(prompt="Hello")
    assert r.prompt == "Hello"
    assert r.max_tokens == 1024
    assert r.temperature == 0.7


def test_llm_request_custom():
    r = LLMRequest(prompt="Test", model="gpt-4", max_tokens=2048, temperature=0.0)
    assert r.model == "gpt-4"
    assert r.max_tokens == 2048
    assert r.temperature == 0.0


def test_mock_generate():
    import asyncio
    p = MockLLMProvider()
    req = LLMRequest(prompt="What is kairon?")
    resp = asyncio.run(p.generate(req))
    assert isinstance(resp, LLMResponse)
    assert "kairon" in resp.content.lower()
