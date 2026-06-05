from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from llm_gateway.types import ChatOptions, ChatResult, ModelDescriptor, StreamChunk


# ── X3 Cost tracking ─────────────────────────────────────────────────────
_COST_LOG = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data" / "llm_cost.jsonl"


def record_llm_cost(model: str, input_tokens: int, output_tokens: int) -> None:
    """Record an LLM call's token usage to the cost log (non-blocking)."""
    try:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        _COST_LOG.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        import os as _os
        fd = _os.open(str(_COST_LOG), _os.O_WRONLY | _os.O_CREAT | _os.O_APPEND, 0o644)
        try:
            _os.write(fd, line)
        finally:
            _os.close(fd)
    except Exception:
        pass  # non-blocking — logging failure must not break LLM calls


class BaseLLMProvider(ABC):
    """Abstract base class for LLM model providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Provider type string."""

    @abstractmethod
    async def discover(self) -> list[ModelDescriptor]:
        """Discover and return available models from this provider."""

    @abstractmethod
    async def health(self) -> bool:
        """Check provider health/availability."""

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> ChatResult:
        """Send a chat completion request."""

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion response.

        Default raises NotImplementedError. Providers that support
        streaming should override this.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support streaming")


# ---------------------------------------------------------------------------
# Shared HTTP utilities
# ---------------------------------------------------------------------------


async def http_get(
    url: str,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 5000,
) -> httpx.Response:
    """Send an HTTP GET request with a timeout."""
    async with httpx.AsyncClient(timeout=timeout_ms / 1000) as client:
        return await client.get(url, headers=headers or {})


async def http_post(
    url: str,
    body: Any,
    auth_header: str | None = None,
    timeout_ms: int = 60000,
) -> httpx.Response:
    """Send an HTTP POST request with JSON body and optional auth."""
    request_headers: dict[str, str] = {"Content-Type": "application/json"}
    if auth_header:
        request_headers["Authorization"] = auth_header
    async with httpx.AsyncClient(timeout=timeout_ms / 1000) as client:
        return await client.post(url, json=body, headers=request_headers)


async def health_check(
    url: str,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 3000,
) -> bool:
    """Quick health check: returns True if the endpoint responds OK."""
    try:
        async with httpx.AsyncClient(timeout=timeout_ms / 1000) as client:
            response = await client.get(url, headers=headers or {})
            return response.is_success
    except httpx.HTTPError:
        return False


async def checked_json(response: httpx.Response, label: str) -> Any:
    """Raise on HTTP error, then return parsed JSON."""
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------


def parse_openai_response(body: dict[str, Any], model: str) -> ChatResult:
    """Parse an OpenAI-compatible chat completions response."""
    choices = body.get("choices", [])
    message = choices[0].get("message", {}) if choices else {}
    finish_reason = choices[0].get("finish_reason", "stop") if choices else "stop"
    usage_raw = body.get("usage")
    usage = None
    if usage_raw:
        usage = {
            "prompt_tokens": usage_raw.get("prompt_tokens", 0),
            "completion_tokens": usage_raw.get("completion_tokens", 0),
            "total_tokens": usage_raw.get("total_tokens", 0),
        }
        record_llm_cost(
            body.get("model", model),
            usage_raw.get("prompt_tokens", 0),
            usage_raw.get("completion_tokens", 0),
        )
    return ChatResult(
        id=body.get("id", "ai-0"),
        model=body.get("model", model),
        content=message.get("content", ""),
        finish_reason=finish_reason,
        usage=usage,
    )


def parse_anthropic_response(body: dict[str, Any], model: str) -> ChatResult:
    """Parse an Anthropic messages API response."""
    content_blocks = body.get("content", [])
    content = ""
    for block in content_blocks:
        if block.get("type") == "text":
            content = block.get("text", "")
            break
    usage_raw = body.get("usage")
    usage = None
    if usage_raw:
        input_tok = usage_raw.get("input_tokens", 0)
        output_tok = usage_raw.get("output_tokens", 0)
        usage = {
            "prompt_tokens": input_tok,
            "completion_tokens": output_tok,
            "total_tokens": input_tok + output_tok,
        }
    return ChatResult(
        id=body.get("id", "anthropic-0"),
        model=body.get("model", model),
        content=content,
        finish_reason=body.get("stop_reason", "stop"),
        usage=usage,
    )


def parse_ollama_response(body: dict[str, Any], model: str) -> ChatResult:
    """Parse an Ollama chat API response."""
    message = body.get("message", {})
    return ChatResult(
        id="ollama-0",
        model=model,
        content=message.get("content", ""),
        finish_reason="stop" if body.get("done") else "unknown",
    )
