from __future__ import annotations

from typing import Any

import httpx

from llm_gateway.providers.base import (
    BaseLLMProvider,
    checked_json,
    health_check,
    http_post,
    parse_ollama_response,
)
from llm_gateway.types import ChatOptions, ChatResult, ModelDescriptor


class OllamaProvider(BaseLLMProvider):
    """Ollama provider -- local LLMs via ReST API."""

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def provider_type(self) -> str:
        return "ollama"

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")

    async def discover(self) -> list[ModelDescriptor]:
        url = f"{self.base_url}/api/tags"
        if not await health_check(url, timeout_ms=3000):
            return []
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        result: list[ModelDescriptor] = []
        for m in data.get("models", []):
            result.append(ModelDescriptor(
                id=f"ollama/{m['name']}",
                name=m['name'],
                provider="ollama",
                capabilities=["chat", "streaming"],
                context_window=4096,
                is_available=True,
                metadata={"size": m.get("size", 0), "modified_at": m.get("modified_at", "")},
            ))
        return result

    async def health(self) -> bool:
        return await health_check(f"{self.base_url}/api/tags")

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: ChatOptions | None = None,
    ) -> ChatResult:
        body: dict[str, Any] = {
            "model": model.removeprefix("ollama/"),
            "messages": messages,
            "stream": False,
        }
        if options and options.temperature is not None:
            body.setdefault("options", {})["temperature"] = options.temperature
        resp = await http_post(f"{self.base_url}/api/chat", body)
        data = await checked_json(resp, "Ollama chat")
        return parse_ollama_response(data, model)

