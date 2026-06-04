"""LLM Gateway — unified LLM provider abstraction layer.

Provides:
- :class:`LLMProvider` ABC with :class:`LLMRequest` / :class:`LLMResponse` dataclasses
- Concrete providers: Ollama, Anthropic, OpenAI, Gemini, DeepSeek, HITL
- :class:`MockLLMProvider` and :class:`NoneProvider` for testing / degradation
- :func:`detect_backends` / :func:`create_provider` for auto-detection
"""

import builtins

from llm_gateway.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from llm_gateway.detection import create_provider, detect_backends
from llm_gateway.provider import (
    LLMError,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMRetryExhaustedError,
    MockLLMProvider,
    NoneProvider,
    ToolCall,
    ToolResult,
    ToolSchema,
)
from llm_gateway.providers.anthropic_provider import AnthropicProvider
from llm_gateway.providers.deepseek_provider import DeepSeekProvider
from llm_gateway.providers.gemini_provider import GeminiProvider
from llm_gateway.providers.hitl_provider import HitlLLMProvider
from llm_gateway.providers.ollama_provider import OllamaProvider
from llm_gateway.providers.openai_provider import OpenAIProvider
from llm_gateway.retry import RetryConfig

builtins.CircuitBreaker = CircuitBreaker
builtins.CircuitBreakerConfig = CircuitBreakerConfig
builtins.RetryConfig = RetryConfig

__all__ = (
    "AnthropicProvider",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "DeepSeekProvider",
    "GeminiProvider",
    "HitlLLMProvider",
    "LLMError",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LLMRetryExhaustedError",
    "MockLLMProvider",
    "NoneProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "RetryConfig",
    "ToolCall",
    "ToolResult",
    "ToolSchema",
    "create_provider",
    "detect_backends",
)
