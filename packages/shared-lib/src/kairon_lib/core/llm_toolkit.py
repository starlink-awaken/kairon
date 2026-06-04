"""LLM client with multiple provider support.

Migrated from agentmesh toolkit/src/llm/ (LLMClient, types, GoogleProvider,
OpenAIProvider, AnthropicProvider, OllamaProvider).
Replaces the existing stub with real async HTTP implementations.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

ProviderType = str  # "openai" | "anthropic" | "google" | "ollama"


@dataclass
class ChatMessage:
    role: str = "user"  # "system" | "user" | "assistant" | "tool"
    content: str = ""
    name: str = ""


@dataclass
class ChatOptions:
    messages: list[ChatMessage] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 1.0
    stop: list[str] = field(default_factory=list)


@dataclass
class ChatCompletion:
    model: str = ""
    content: str = ""
    finish_reason: str = "stop"
    id: str = ""
    created: int = 0
    usage: dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})


@dataclass
class StreamChunk:
    content: str = ""
    delta: str = ""
    done: bool = False


@dataclass
class EmbedRequest:
    input: str | list[str] = ""
    model: str = ""


@dataclass
class EmbedResponse:
    model: str = ""
    embeddings: list[list[float]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class LLMConfig:
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 1.0
    timeout: int = 60
    extra_headers: dict[str, str] = field(default_factory=dict)


# ----- Abstract Base -----

class BaseLLMClient(ABC):
    """Abstract base for all LLM providers."""

    provider_type: ProviderType = ""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()

    @abstractmethod
    async def chat(self, options: ChatOptions) -> ChatCompletion:
        ...

    async def stream(self, options: ChatOptions) -> AsyncGenerator[StreamChunk]:
        result = await self.chat(options)
        yield StreamChunk(content=result.content, delta=result.content, done=True)

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        return EmbedResponse(model=self.config.model, embeddings=[])

    async def is_available(self) -> bool:
        try:
            return await self._ping()
        except Exception:
            return False

    async def _ping(self) -> bool:
        return True


# ----- HTTP Helpers -----

async def _http_post(url: str, json_body: dict[str, Any], headers: dict[str, str], timeout: int = 60) -> dict[str, Any]:
    import httpx
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=json_body, headers=headers)
        resp.raise_for_status()
        return resp.json()


# ----- OpenAI Provider -----

class OpenAIProvider(BaseLLMClient):
    provider_type = "openai"

    def __init__(self, config: LLMConfig | None = None) -> None:
        super().__init__(config or LLMConfig(model="gpt-4o", base_url="https://api.openai.com/v1"))

    async def chat(self, options: ChatOptions) -> ChatCompletion:
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in options.messages],
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
            "top_p": options.top_p,
        }
        if options.stop:
            body["stop"] = options.stop
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key}"}
        headers.update(self.config.extra_headers)
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        data = await _http_post(url, body, headers, self.config.timeout)
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return ChatCompletion(
            model=data["model"], content=choice["message"]["content"],
            finish_reason=choice.get("finish_reason", "stop"),
            id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:12]}"),
            created=data.get("created", 0),
            usage={"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0), "total_tokens": usage.get("total_tokens", 0)},
        )

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        texts = request.input if isinstance(request.input, list) else [request.input]
        body = {"model": self.config.model, "input": texts}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key}"}
        url = f"{self.config.base_url.rstrip('/')}/embeddings"
        data = await _http_post(url, body, headers, self.config.timeout)
        embeddings = [d["embedding"] for d in data["data"]]
        usage = data.get("usage", {})
        return EmbedResponse(model=data["model"], embeddings=embeddings, usage={"prompt_tokens": usage.get("prompt_tokens", 0), "total_tokens": usage.get("total_tokens", 0)})


# ----- Anthropic Provider -----

class AnthropicProvider(BaseLLMClient):
    provider_type = "anthropic"

    def __init__(self, config: LLMConfig | None = None) -> None:
        super().__init__(config or LLMConfig(model="claude-sonnet-4-20250514", base_url="https://api.anthropic.com/v1"))

    async def chat(self, options: ChatOptions) -> ChatCompletion:
        system = [m.content for m in options.messages if m.role == "system"]
        messages = [{"role": m.role, "content": m.content} for m in options.messages if m.role != "system"]
        body: dict[str, Any] = {"model": self.config.model, "messages": messages, "max_tokens": options.max_tokens, "temperature": options.temperature}
        if system:
            body["system"] = system[0]
        headers = {"Content-Type": "application/json", "x-api-key": self.config.api_key, "anthropic-version": "2023-06-01"}
        headers.update(self.config.extra_headers)
        url = f"{self.config.base_url.rstrip('/')}/messages"
        data = await _http_post(url, body, headers, self.config.timeout)
        content = "".join(b.get("text", "") for b in data.get("content", []))
        usage = data.get("usage", {})
        return ChatCompletion(
            model=data["model"], content=content, finish_reason=data.get("stop_reason", "stop"),
            id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
            usage={"prompt_tokens": usage.get("input_tokens", 0), "completion_tokens": usage.get("output_tokens", 0), "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)},
        )


# ----- Google Provider -----

class GoogleProvider(BaseLLMClient):
    provider_type = "google"

    def __init__(self, config: LLMConfig | None = None) -> None:
        super().__init__(config or LLMConfig(model="gemini-2.0-flash", base_url="https://generativelanguage.googleapis.com/v1beta"))

    async def chat(self, options: ChatOptions) -> ChatCompletion:
        contents = [{"role": "user" if m.role == "user" else "model", "parts": [{"text": m.content}]} for m in options.messages if m.role != "system"]
        body: dict[str, Any] = {"contents": contents, "generationConfig": {"temperature": options.temperature, "maxOutputTokens": options.max_tokens, "topP": options.top_p}}
        headers = {"Content-Type": "application/json"}
        headers.update(self.config.extra_headers)
        url = f"{self.config.base_url.rstrip('/')}/models/{self.config.model}:generateContent?key={self.config.api_key}"
        data = await _http_post(url, body, headers, self.config.timeout)
        candidate = data.get("candidates", [{}])[0]
        text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []))
        return ChatCompletion(model=self.config.model, content=text, finish_reason=candidate.get("finishReason", "stop"), id=f"chatcmpl-{uuid.uuid4().hex[:12]}")


# ----- Ollama Provider -----

class OllamaProvider(BaseLLMClient):
    provider_type = "ollama"

    def __init__(self, config: LLMConfig | None = None) -> None:
        super().__init__(config or LLMConfig(model="llama3", base_url="http://localhost:11434"))

    async def chat(self, options: ChatOptions) -> ChatCompletion:
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in options.messages],
            "stream": False,
            "options": {"temperature": options.temperature, "num_predict": options.max_tokens},
        }
        headers = {"Content-Type": "application/json"}
        url = f"{self.config.base_url.rstrip('/')}/api/chat"
        data = await _http_post(url, body, headers, self.config.timeout)
        return ChatCompletion(
            model=data.get("model", self.config.model),
            content=data.get("message", {}).get("content", ""),
            finish_reason="stop",
            id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
            usage={"prompt_tokens": data.get("prompt_eval_count", 0), "completion_tokens": data.get("eval_count", 0), "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)},
        )

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        texts = request.input if isinstance(request.input, list) else [request.input]
        body = {"model": self.config.model, "input": texts}
        headers = {"Content-Type": "application/json"}
        url = f"{self.config.base_url.rstrip('/')}/api/embed"
        data = await _http_post(url, body, headers, self.config.timeout)
        return EmbedResponse(model=self.config.model, embeddings=data.get("embeddings", []))


# ----- Factory -----

class LLMClientFactory:
    _registry: dict[str, type[BaseLLMClient]] = {
        "openai": OpenAIProvider, "anthropic": AnthropicProvider,
        "google": GoogleProvider, "ollama": OllamaProvider,
    }

    @classmethod
    def register(cls, name: str, client_cls: type[BaseLLMClient]) -> None:
        cls._registry[name] = client_cls

    @classmethod
    def create(cls, provider: str, **kwargs: Any) -> BaseLLMClient:
        client_cls = cls._registry.get(provider.lower())
        if client_cls is None:
            msg = f"Unknown provider: {provider}. Known: {list(cls._registry)}"
            raise ValueError(msg)
        config = LLMConfig(**kwargs)
        return client_cls(config)
