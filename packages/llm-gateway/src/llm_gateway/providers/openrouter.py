"""OpenRouter provider (agentmesh model-orchestrator providers/openrouter.ts)."""

from __future__ import annotations

from llm_gateway.providers.base import BaseLLMProvider


class OpenRouterProvider(BaseLLMProvider):
    @property
    def name(self) -> str: return "openrouter"
    @property
    def provider_type(self) -> str: return "openrouter"
