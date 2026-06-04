"""LLM client abstraction layer.

Provides a common interface for LLM providers (Ollama, OpenAI, Anthropic)
and a factory for client creation.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


def _simple_hash_embed(text: str, dim: int = 64) -> list[float]:
    """Produce a deterministic float vector from text."""
    vec = [0.0] * dim
    for i, ch in enumerate(text):
        vec[i % dim] += (ord(ch) / 127.0) * ((-1) ** (i // dim))
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class BaseLLMClient(ABC):
    """Abstract base for LLM API clients."""

    @abstractmethod
    def chat(self, messages: list[dict[str, str]]) -> str:
        """Send a chat completion request and return the response text."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into float vectors."""


@dataclass
class OllamaClient(BaseLLMClient):
    """Stub Ollama client for local models."""

    model: str = "llama3"
    base_url: str = "http://localhost:11434"
    options: dict[str, Any] = field(default_factory=dict)

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Stub: returns a placeholder response."""
        return f"[Ollama:{self.model}] Stub response for {len(messages)} messages"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_simple_hash_embed(t) for t in texts]


@dataclass
class OpenAIClient(BaseLLMClient):
    """Stub OpenAI-compatible API client."""

    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    options: dict[str, Any] = field(default_factory=dict)

    def chat(self, messages: list[dict[str, str]]) -> str:
        return f"[OpenAI:{self.model}] Stub response for {len(messages)} messages"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_simple_hash_embed(t) for t in texts]


@dataclass
class AnthropicClient(BaseLLMClient):
    """Stub Anthropic API client."""

    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    base_url: str = "https://api.anthropic.com/v1"
    options: dict[str, Any] = field(default_factory=dict)

    def chat(self, messages: list[dict[str, str]]) -> str:
        return f"[Anthropic:{self.model}] Stub response for {len(messages)} messages"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_simple_hash_embed(t) for t in texts]


class LLMClientFactory:
    """Factory to create LLM clients by provider name."""

    _registry: dict[str, type[BaseLLMClient]] = {
        "ollama": OllamaClient,
        "openai": OpenAIClient,
        "anthropic": AnthropicClient,
    }

    @classmethod
    def register(cls, name: str, client_cls: type[BaseLLMClient]) -> None:
        cls._registry[name] = client_cls

    @classmethod
    def create(cls, provider: str, config: dict[str, Any] | None = None) -> BaseLLMClient:
        """Return a client instance for the given *provider* name."""
        client_cls = cls._registry.get(provider.lower())
        if client_cls is None:
            msg = f"Unknown provider: {provider}. Known: {list(cls._registry)}"
            raise ValueError(msg)
        cfg = config or {}
        return client_cls(**cfg)
