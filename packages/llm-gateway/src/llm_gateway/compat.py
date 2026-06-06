"""Backward-compatible provider aliases for minerva/ssot/ontoderive consumers.

These classes delegate to :func:`llm_gateway.detection.create_provider`
and implement the :class:`llm_gateway.provider.LLMProvider` interface.

Usage (for backward compatibility)::

    from llm_gateway.compat import MinervaProvider
    provider = MinervaProvider()
    response = provider.complete(LLMRequest(prompt="..."))

.. deprecated:: 0.4.0
    Use :func:`llm_gateway.detection.create_provider` directly.
    These aliases are kept for backward compatibility with
    minerva/ssot/ontoderive that import by class name.
"""
from __future__ import annotations

import logging

from llm_gateway.detection import create_provider
from llm_gateway.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
)

_log = logging.getLogger(__name__)


def _create_and_complete(
    provider_name: str,
    base_url: str,
    api_key: str,
    model: str,
    request: LLMRequest,
) -> LLMResponse:
    """Create a provider on-the-fly and call complete()."""
    try:
        provider = create_provider(
            provider_name,
            base_url=base_url,
            api_key=api_key,
            default_model=model,
        )
        return provider.complete(request)
    except Exception as e:
        _log.error("%sProvider.complete() failed: %s", provider_name, e)
        return LLMResponse(
            content="",
            provider=provider_name,
            finish_reason="error",
        )


class MinervaProvider(LLMProvider):
    """Minerva-compatible provider — delegates to ollama via unified API.

    Backward-compatible with ``minerva/llm/__init__.py``.
    """

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "qwen3.6:35b-a3b-coding-nvfp4"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = "ollama",
        model: str = DEFAULT_MODEL,
        timeout: int = 120,
    ) -> None:
        super().__init__()
        self._base_url = base_url
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "minerva-compat"

    def available_models(self) -> list[str]:
        return [self._model]

    def is_available(self) -> bool:
        return True

    def complete(self, request: LLMRequest) -> LLMResponse:
        return _create_and_complete(
            "ollama", self._base_url, self._api_key, self._model, request
        )


class SSOTProvider(LLMProvider):
    """SSOT-compatible provider — delegates to ollama via unified API.

    Backward-compatible with ``ssot_kernel/extractor/llm.py``.
    """

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "qwen3.6:35b-a3b-coding-nvfp4"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = "ollama",
        model: str = DEFAULT_MODEL,
        timeout: int = 120,
    ) -> None:
        super().__init__()
        self._base_url = base_url
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "ssot-compat"

    def available_models(self) -> list[str]:
        return [self._model]

    def is_available(self) -> bool:
        return True

    def complete(self, request: LLMRequest) -> LLMResponse:
        return _create_and_complete(
            "ollama", self._base_url, self._api_key, self._model, request
        )


class OntoderiveProvider(LLMProvider):
    """Ontoderive-compatible provider — delegates to openai via unified API.

    Backward-compatible with ``ontoderive/engine/intelligence/providers.py``.
    """

    DEFAULT_MODEL = "gpt-4"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__()
        self._api_key = api_key or ""
        self._model = model or self.DEFAULT_MODEL

    @property
    def provider_name(self) -> str:
        return "ontoderive-compat"

    def available_models(self) -> list[str]:
        return [self._model]

    def is_available(self) -> bool:
        return bool(self._api_key)

    def complete(self, request: LLMRequest) -> LLMResponse:
        return _create_and_complete(
            "openai",
            "https://api.openai.com/v1",
            self._api_key,
            self._model,
            request,
        )