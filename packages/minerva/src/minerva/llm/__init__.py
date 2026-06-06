"""Minerva LLM client module."""

from minerva.llm.client import (
    OpenAICompatibleClient as _OriginalOpenAICompatibleClient,  # type: ignore[import-not-found]  # noqa: F401
)

__all__ = ["OpenAICompatibleClient"]
