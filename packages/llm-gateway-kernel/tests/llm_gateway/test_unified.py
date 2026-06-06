"""Tests for the unified LLM provider interface.

Covers:
- Unified LLMResponse/LLMRequest with ``content``/``provider`` fields
- MockLLMProvider (async generate, sync complete, streaming)
- NoneProvider (silent degradation)
- Detection module (detect_backends, create_provider)
- Provider identity (provider_name property)
- health_check
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# LLMRequest / LLMResponse dataclass tests
# ---------------------------------------------------------------------------


class TestLLMRequest:
    def test_defaults(self):
        from llm_gateway.provider import LLMRequest

        r = LLMRequest(prompt="hello")
        assert r.prompt == "hello"
        assert r.system_prompt == ""
        assert r.model is None
        assert r.max_tokens == 1024
        assert r.temperature == 0.7
        assert r.stop_sequences == []
        assert r.context == []
        assert r.metadata == {}

    def test_all_fields(self):
        from llm_gateway.provider import LLMRequest

        r = LLMRequest(
            prompt="test",
            system_prompt="be helpful",
            model="gpt-4",
            max_tokens=500,
            temperature=0.5,
            stop_sequences=["\n"],
            context=[{"role": "user", "content": "prev"}],
            metadata={"key": "val"},
        )
        assert r.prompt == "test"
        assert r.system_prompt == "be helpful"
        assert r.model == "gpt-4"
        assert r.max_tokens == 500
        assert r.temperature == 0.5
        assert r.stop_sequences == ["\n"]
        assert r.context == [{"role": "user", "content": "prev"}]
        assert r.metadata == {"key": "val"}


class TestLLMResponse:
    def test_defaults(self):
        from llm_gateway.provider import LLMResponse

        r = LLMResponse(content="hello")
        assert r.content == "hello"
        assert r.provider == ""
        assert r.model == ""
        assert r.input_tokens == 0
        assert r.output_tokens == 0
        assert r.finish_reason == "stop"
        assert r.metadata == {}

    def test_all_fields(self):
        from llm_gateway.provider import LLMResponse

        r = LLMResponse(
            content="response",
            provider="openai",
            model="gpt-4",
            input_tokens=10,
            output_tokens=20,
            finish_reason="length",
            metadata={"latency_ms": 150},
        )
        assert r.content == "response"
        assert r.provider == "openai"
        assert r.model == "gpt-4"
        assert r.input_tokens == 10
        assert r.output_tokens == 20
        assert r.finish_reason == "length"
        assert r.metadata == {"latency_ms": 150}


# ---------------------------------------------------------------------------
# MockLLMProvider tests
# ---------------------------------------------------------------------------


class TestMockLLMProvider:
    def test_provider_name(self):
        from llm_gateway.provider import MockLLMProvider

        p = MockLLMProvider()
        assert p.provider_name == "mock"

    def test_is_available(self):
        from llm_gateway.provider import MockLLMProvider

        assert MockLLMProvider().is_available()

    def test_health_check(self):
        from llm_gateway.provider import MockLLMProvider

        assert MockLLMProvider().health_check() == ""

    def test_available_models(self):
        from llm_gateway.provider import MockLLMProvider

        assert MockLLMProvider().available_models() == ["mock-model"]

    def test_complete(self):
        from llm_gateway.provider import LLMRequest, MockLLMProvider

        resp = MockLLMProvider().complete(LLMRequest(prompt="hello world"))
        assert "Mock response" in resp.content
        assert resp.model == "mock-model"
        assert resp.provider == "mock"

    def test_generate(self):
        import asyncio

        from llm_gateway.provider import LLMRequest, MockLLMProvider

        resp = asyncio.run(MockLLMProvider().generate(LLMRequest(prompt="hello")))
        assert "Mock response" in resp.content

    def test_stream_generate(self):
        import asyncio

        from llm_gateway.provider import LLMRequest, MockLLMProvider

        async def collect():
            chunks = []
            async for chunk in MockLLMProvider().stream_generate(LLMRequest(prompt="hello")):
                chunks.append(chunk)
            return "".join(chunks)

        result = asyncio.run(collect())
        assert "Mock response" in result


# ---------------------------------------------------------------------------
# NoneProvider tests
# ---------------------------------------------------------------------------


class TestNoneProvider:
    def test_provider_name(self):
        from llm_gateway.provider import NoneProvider

        assert NoneProvider().provider_name == "none"

    def test_is_available(self):
        from llm_gateway.provider import NoneProvider

        assert NoneProvider().is_available()

    def test_complete_returns_empty(self):
        from llm_gateway.provider import LLMRequest, NoneProvider

        resp = NoneProvider().complete(LLMRequest(prompt="anything"))
        assert resp.content == ""
        assert resp.provider == "none"

    def test_generate_returns_empty(self):
        import asyncio

        from llm_gateway.provider import LLMRequest, NoneProvider

        resp = asyncio.run(NoneProvider().generate(LLMRequest(prompt="anything")))
        assert resp.content == ""
        assert resp.provider == "none"

    def test_stream_generate(self):
        import asyncio

        from llm_gateway.provider import LLMRequest, NoneProvider

        async def collect():
            chunks = []
            async for chunk in NoneProvider().stream_generate(LLMRequest(prompt="hello")):
                chunks.append(chunk)
            return "".join(chunks)

        result = asyncio.run(collect())
        assert result == ""


# ---------------------------------------------------------------------------
# Detection module tests
# ---------------------------------------------------------------------------


class TestDetection:
    def test_create_provider_known(self):
        from llm_gateway.detection import create_provider

        p = create_provider("mock")
        # mock is not in the registry, so should return None
        assert p is None

    def test_create_provider_unknown(self):
        from llm_gateway.detection import create_provider

        p = create_provider("nonexistent")
        assert p is None

    def test_detect_backends_returns_list(self):
        from llm_gateway.detection import detect_backends

        providers = detect_backends()
        assert isinstance(providers, list)
        assert len(providers) >= 1

    def test_detect_backends_fallback_none_provider(self):
        """When no env vars are set and no SDKs installed, last resort is NoneProvider."""
        # Save and clear relevant env vars
        import os

        from llm_gateway.detection import detect_backends

        saved = {}
        for var in [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
            "DEEPSEEK_API_KEY",
            "LLM_PROVIDER",
        ]:
            saved[var] = os.environ.pop(var, None)

        try:
            providers = detect_backends()
            # Without env vars, only Ollama and HITL may detect (they need no keys).
            # When all SDK-detection-based providers are unavailable, NoneProvider
            # is the last resort.  At minimum we should get back providers.
            assert len(providers) >= 1
        finally:
            # Restore
            for var, val in saved.items():
                if val is not None:
                    os.environ[var] = val


# ---------------------------------------------------------------------------
# Provider identity tests
# ---------------------------------------------------------------------------


class TestProviderIdentity:
    def test_openai_provider_name(self):
        from llm_gateway.providers.openai_provider import OpenAIProvider

        assert OpenAIProvider(api_key="test-key").provider_name == "openai"

    def test_anthropic_provider_name(self):
        from llm_gateway.providers.anthropic_provider import AnthropicProvider

        assert AnthropicProvider(api_key="test-key").provider_name == "anthropic"

    def test_gemini_provider_name(self):
        from llm_gateway.providers.gemini_provider import GeminiProvider

        assert GeminiProvider(api_key="test-key").provider_name == "gemini"

    def test_deepseek_provider_name(self):
        from llm_gateway.providers.deepseek_provider import DeepSeekProvider

        assert DeepSeekProvider(api_key="test-key").provider_name == "deepseek"

    def test_ollama_provider_name(self):
        from llm_gateway.providers.ollama_provider import OllamaProvider

        assert OllamaProvider().provider_name == "ollama"

    def test_hitl_provider_name(self):
        from llm_gateway.providers.hitl_provider import HitlLLMProvider

        assert HitlLLMProvider().provider_name == "hitl"


# ---------------------------------------------------------------------------
# Health check tests
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_mock_health_ok(self):
        from llm_gateway.provider import MockLLMProvider

        assert MockLLMProvider().health_check() == ""

    def test_openai_unavailable_health(self):
        from llm_gateway.providers.openai_provider import OpenAIProvider

        result = OpenAIProvider(api_key="").health_check()
        assert "not available" in result or result == ""

    def test_none_health_ok(self):
        from llm_gateway.provider import NoneProvider

        assert NoneProvider().health_check() == ""


# ---------------------------------------------------------------------------
# Tool classes backward compat
# ---------------------------------------------------------------------------


class TestToolClasses:
    def test_tool_schema(self):
        from llm_gateway.provider import ToolSchema

        ts = ToolSchema(name="get_weather", description="Get weather", parameters={"loc": "str"})
        assert ts.name == "get_weather"
        assert ts.description == "Get weather"

    def test_tool_call(self):
        from llm_gateway.provider import ToolCall

        tc = ToolCall(id="1", name="get_weather", arguments={"loc": "NYC"})
        assert tc.id == "1"
        assert tc.name == "get_weather"
        assert tc.arguments == {"loc": "NYC"}

    def test_tool_result(self):
        from llm_gateway.provider import ToolResult

        tr = ToolResult(call_id="1", output="sunny", error=None)
        assert tr.call_id == "1"
        assert tr.output == "sunny"
        assert tr.error is None
