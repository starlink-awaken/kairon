"""Anthropic provider — Claude models via the Anthropic Messages API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from llm_gateway.providers.base import (
    BaseLLMProvider,
    checked_json,
    health_check,
    http_post,
    parse_anthropic_response,
)
from llm_gateway.types import ChatOptions, ChatResult, ModelDescriptor, StreamChunk


class AnthropicProvider(BaseLLMProvider):
    """Provider for Anthropic's Claude models."""

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def provider_type(self) -> str:
        return "anthropic"

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def discover(self) -> list[ModelDescriptor]:
        known: list[tuple[str, int, float, float]] = [
            ("claude-opus-4-6", 200000, 0.015, 0.075),
            ("claude-sonnet-4-6", 200000, 0.003, 0.015),
            ("claude-haiku-4-5", 200000, 0.0008, 0.004),
        ]
        return [
            ModelDescriptor(
                id=f"anthropic/{model_id}",
                name=model_id,
                provider="anthropic",
                capabilities=["chat", "streaming", "tools"],
                context_window=ctx,
                is_available=True,
                cost_per_1k_tokens={"input": inp, "output": out},
            )
            for model_id, ctx, inp, out in known
        ]

    async def health(self) -> bool:
        return await health_check(
            f"{self.base_url}/models",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            timeout_ms=5000,
        )

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> ChatResult:
        model_name = model.removeprefix("anthropic/")
        system_msg: str | None = None
        chat_messages: list[dict[str, str]] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
            else:
                chat_messages.append({"role": msg["role"], "content": msg.get("content", "")})

        body: dict[str, Any] = {
            "model": model_name,
            "max_tokens": (options and options.max_tokens) or 4096,
            "messages": chat_messages,
        }
        if options and options.temperature is not None:
            body["temperature"] = options.temperature
        if system_msg:
            body["system"] = system_msg

        resp = await http_post(f"{self.base_url}/messages", body)
        data = await checked_json(resp, "Anthropic chat")
        return parse_anthropic_response(data, model)

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        raise NotImplementedError("AnthropicProvider streaming not yet implemented")
