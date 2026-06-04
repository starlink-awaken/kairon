"""OpenAI provider for LLM Gateway (agentmesh model-orchestrator migration)."""

from __future__ import annotations

from typing import Any

import httpx

from llm_gateway.providers.base import (
    BaseLLMProvider,
    checked_json,
    health_check,
    http_post,
)
from llm_gateway.types import ChatOptions, ChatResult, ModelDescriptor


class OpenAIProvider(BaseLLMProvider):
    """OpenAI-compatible provider (OpenAI API, Azure, local proxies)."""

    @property
    def name(self) -> str:
        return "openai"

    @property
    def provider_type(self) -> str:
        return "openai"

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = model

    async def discover(self) -> list[ModelDescriptor]:
        url = f"{self.base_url}/models"
        if not await health_check(url, timeout_ms=3000):
            return []
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        result: list[ModelDescriptor] = []
        for m in data.get("data", []):
            rid = m.get("id", "")
            if not rid:
                continue
            result.append(ModelDescriptor(
                id=f"openai/{rid}",
                name=rid,
                provider="openai",
                capabilities=["chat", "streaming"],
                context_window=128000 if "gpt-4" in rid else 16000,
                is_available=True,
                metadata={"owned_by": m.get("owned_by", "")},
            ))
        return result

    async def health(self) -> bool:
        return await health_check(f"{self.base_url}/models", timeout_ms=5000)

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> ChatResult:
        body: dict[str, Any] = {
            "model": model.removeprefix("openai/"),
            "messages": messages,
        }
        if options:
            if options.temperature is not None:
                body["temperature"] = options.temperature
            if options.max_tokens is not None:
                body["max_tokens"] = options.max_tokens
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = await http_post(  # type: ignore[call-arg]
            f"{self.base_url}/chat/completions",
            body,
            headers=headers,
        )
        data = await checked_json(resp, "OpenAI chat")
        choice = data["choices"][0]
        return ChatResult(
            model=model,
            content=choice["message"]["content"] or "",
            usage=data.get("usage"),
            finish_reason=choice.get("finish_reason"),
        )
