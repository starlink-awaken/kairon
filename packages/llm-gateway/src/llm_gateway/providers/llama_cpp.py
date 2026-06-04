"""llama.cpp provider (agentmesh model-orchestrator providers/llama-cpp.ts)."""

from __future__ import annotations

from llm_gateway.providers.base import BaseLLMProvider


class LlamaCppProvider(BaseLLMProvider):
    @property
    def name(self) -> str: return "llama.cpp"
    @property
    def provider_type(self) -> str: return "llama.cpp"
