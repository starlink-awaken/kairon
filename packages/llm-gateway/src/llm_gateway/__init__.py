"""LLM Gateway — unified LLM provider abstraction layer.

Provides:
- :class:`LLMProvider` ABC with :class:`LLMRequest` / :class:`LLMResponse` dataclasses
- Concrete providers: Ollama, Anthropic, OpenAI, Gemini, DeepSeek, HITL
- :class:`MockLLMProvider` and :class:`NoneProvider` for testing / degradation
- :func:`detect_backends` / :func:`create_provider` for auto-detection
"""

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

__all__ = [
    # Core
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LLMError",
    "LLMRetryExhaustedError",
    # Concrete providers
    "AnthropicProvider",
    "DeepSeekProvider",
    "GeminiProvider",
    "HitlLLMProvider",
    "OllamaProvider",
    "OpenAIProvider",
    # Testing / degradation
    "MockLLMProvider",
    "NoneProvider",
    # Tool classes (backward compat)
    "ToolCall",
    "ToolResult",
    "ToolSchema",
    # Detection
    "create_provider",
    "detect_backends",
]
