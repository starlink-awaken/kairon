"""Basic tests for llm-gateway package."""

from __future__ import annotations

from llm_gateway_kernel.llm_gateway import (
    AnthropicProvider,
    LLMError,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MockLLMProvider,
    NoneProvider,
    OllamaProvider,
    OpenAIProvider,
    ToolCall,
    ToolResult,
    create_provider,
    detect_backends,
)
from llm_gateway_kernel.llm_gateway.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from llm_gateway_kernel.llm_gateway.policies import list_policies, register_policy, score_models
from llm_gateway_kernel.llm_gateway.registry import ModelRegistry
from llm_gateway_kernel.llm_gateway.retry import RetryConfig


class TestLlmGatewayBasic:
    """Core functionality and edge case tests."""

    def test_imports(self):
        """All expected exports are importable."""
        assert LLMProvider is not None
        assert LLMRequest is not None
        assert LLMResponse is not None
        assert MockLLMProvider is not None
        assert NoneProvider is not None
        assert AnthropicProvider is not None
        assert OllamaProvider is not None
        assert OpenAIProvider is not None
        assert create_provider is not None
        assert detect_backends is not None
        assert LLMError is not None
        assert ToolCall is not None
        assert ToolResult is not None

    def test_llm_request_minimal(self):
        """LLMRequest with just prompt works."""
        r = LLMRequest(prompt="hello")
        assert r.prompt == "hello"
        assert r.system_prompt == ""

    def test_llm_request_full(self):
        """LLMRequest with all fields."""
        r = LLMRequest(
            prompt="hello",
            system_prompt="be brief",
            temperature=0.5,
            max_tokens=100,
        )
        assert r.temperature == 0.5
        assert r.max_tokens == 100

    def test_mock_provider(self):
        """MockLLMProvider returns canned responses."""
        p = MockLLMProvider()
        result = p.complete(LLMRequest(prompt="test"))
        assert result.provider == "mock"

    def test_none_provider(self):
        """NoneProvider always returns error."""
        p = NoneProvider()
        result = p.complete(LLMRequest(prompt="x"))
        assert result.content == ""

    def test_circuit_breaker_defaults(self):
        """CircuitBreaker with default config."""
        cb = CircuitBreaker(name="test")
        assert cb.state == "closed"
        assert cb.name == "test"

    def test_circuit_breaker_config(self):
        """CircuitBreakerConfig stores parameters."""
        cfg = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0)
        assert cfg.failure_threshold == 5
        assert cfg.recovery_timeout == 60.0

    def test_retry_config(self):
        """RetryConfig stores parameters."""
        cfg = RetryConfig(max_retries=3, base_delay=1.0)
        assert cfg.max_retries == 3
        assert cfg.base_delay == 1.0

    def test_detect_backends_returns_list(self):
        """detect_backends returns at least empty list without crashing."""
        result = detect_backends()
        assert isinstance(result, list)

    def test_model_registry_init(self):
        """ModelRegistry initializes empty."""
        reg = ModelRegistry()
        assert reg.list_models() is not None

    def test_policies_importable(self):
        """Policy module functions import correctly."""
        assert list_policies is not None
        assert score_models is not None
        assert register_policy is not None
