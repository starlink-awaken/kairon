"""LM Studio provider (agentmesh model-orchestrator providers/lm-studio.ts)."""

from __future__ import annotations

from llm_gateway.providers.base import BaseLLMProvider


class LMStudioProvider(BaseLLMProvider):
    @property
    def name(self) -> str: return "lm-studio"
    @property
    def provider_type(self) -> str: return "lm-studio"
