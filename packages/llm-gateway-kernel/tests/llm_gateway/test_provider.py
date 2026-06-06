"""Tests for llm-gateway provider abstractions."""

from __future__ import annotations

from llm_gateway.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMRetryExhaustedError,
    MockLLMProvider,
    NoneProvider,
    _with_llm_retry,
)


def test_llm_request_defaults():
    req = LLMRequest(prompt="Hello")
    assert req.prompt == "Hello"
    assert req.temperature == 0.7
    assert req.max_tokens == 1024
    assert req.system_prompt == ""
    assert req.model is None
    assert req.stop_sequences == []
    assert req.context == []
    assert req.metadata == {}


def test_llm_response_defaults():
    resp = LLMResponse(content="Hi")
    assert resp.content == "Hi"
    assert resp.finish_reason == "stop"
    assert resp.provider == ""
    assert resp.model == ""
    assert resp.input_tokens == 0
    assert resp.output_tokens == 0
    assert resp.metadata == {}


def test_mock_provider_complete():
    mock = MockLLMProvider()
    resp = mock.complete(LLMRequest(prompt="test"))
    assert "Mock response" in resp.content
    assert resp.model == "mock-model"
    assert resp.provider == "mock"


def test_mock_provider_is_available():
    mock = MockLLMProvider()
    assert mock.is_available()


def test_mock_provider_generate():
    import asyncio

    mock = MockLLMProvider()
    resp = asyncio.run(mock.generate(LLMRequest(prompt="test")))
    assert "Mock response" in resp.content
    assert resp.model == "mock-model"
    assert resp.provider == "mock"


def test_mock_provider_stream_generate():
    import asyncio

    mock = MockLLMProvider()

    async def _run():
        chunks = []
        async for chunk in mock.stream_generate(LLMRequest(prompt="test")):
            chunks.append(chunk)
        return "".join(chunks)

    result = asyncio.run(_run())
    assert "Mock response" in result


def test_none_provider():
    none_provider = NoneProvider()
    assert none_provider.is_available()
    assert none_provider.provider_name == "none"

    resp = none_provider.complete(LLMRequest(prompt="test"))
    assert resp.content == ""
    assert resp.provider == "none"


def test_ollama_provider_exists():
    from llm_gateway.providers.ollama_provider import OllamaProvider

    p = OllamaProvider()
    assert p.default_model == "llama3"
    assert p.provider_name == "ollama"
    assert p.base_url == "http://localhost:11434"


def test_retry_success():
    """_with_llm_retry returns the value on first success."""
    result = _with_llm_retry(lambda: 42)
    assert result == 42


def test_retry_eventually_succeeds():
    """_with_llm_retry retries on transient errors and succeeds."""
    attempt = [0]

    def flaky():
        attempt[0] += 1
        if attempt[0] < 3:
            raise OSError("transient")
        return "ok"

    result = _with_llm_retry(flaky, max_retries=3, base_delay=0.01)
    assert result == "ok"
    assert attempt[0] == 3


def test_retry_exhausted():
    """_with_llm_retry raises after exhausting retries."""

    def always_fails():
        raise ValueError("always fails")

    import pytest

    with pytest.raises(LLMRetryExhaustedError):
        _with_llm_retry(always_fails, max_retries=2, base_delay=0.01)


def test_abstract_class_cannot_be_instantiated():
    import pytest

    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_mock_provider_health_check():
    mock = MockLLMProvider()
    assert mock.health_check() == ""


def test_mock_provider_available_models():
    mock = MockLLMProvider()
    assert mock.available_models() == ["mock-model"]
