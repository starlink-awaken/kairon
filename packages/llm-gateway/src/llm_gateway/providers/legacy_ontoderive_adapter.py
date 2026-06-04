"""Adapter: ontoderive BaseProvider -> llm-gateway LLMProvider.

Wraps :class:`ontoderive.engine.intelligence.providers.BaseProvider` and its
concrete backends (OpenAI, Anthropic, Ollama, Local) into the unified
:class:`llm_gateway.provider.LLMProvider` ABC.
"""

from __future__ import annotations

import logging
from typing import Any

from llm_gateway.provider import LLMProvider, LLMRequest, LLMResponse

_log = logging.getLogger(__name__)


class OntoderiveProvider(LLMProvider):
    """Adapter wrapping ontoderive's BaseProvider into llm-gateway's ABC.

    Parameters
    ----------
    backend:
        Which ontoderive backend to use ("openai", "anthropic", "ollama",
        "local", "none").
    model:
        Model identifier passed through to the backend.
    base_url:
        Base URL for the backend (e.g. ``http://localhost:11434`` for Ollama).
    **kwargs:
        Extra arguments forwarded to the backend constructor.
    """

    def __init__(
        self,
        backend: str = "openai",
        model: str = "",
        base_url: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self._backend_name = backend
        self._model = model
        self._base_url = base_url
        self._kwargs = kwargs
        self._inner: Any = None

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "ontoderive"

    # ------------------------------------------------------------------
    # Lazy init
    # ------------------------------------------------------------------

    def _ensure_backend(self) -> None:
        """Lazy-initialize the ontoderive backend."""
        if self._inner is not None:
            return
        try:
            from engine.intelligence.providers import (  # type: ignore[import-not-found]
                BACKENDS,
            )

            backend_cls = BACKENDS.get(self._backend_name)
            if backend_cls is None:
                raise ValueError(
                    f"Unknown ontoderive backend: {self._backend_name!r}. "
                    f"Available: {list(BACKENDS)}"
                )
            self._inner = backend_cls(
                model=self._model,
                base_url=self._base_url,
                **self._kwargs,
            )
        except ImportError:
            _log.debug(
                "ontoderive package not installed — OntoderiveProvider unavailable"
            )
        except Exception:
            _log.exception("Failed to initialize ontoderive backend")
            self._inner = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        self._ensure_backend()
        if self._inner is None:
            return False
        try:
            return bool(self._inner.probe())
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Generation (sync)
    # ------------------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMResponse:
        self._ensure_backend()
        if self._inner is None:
            return LLMResponse(
                content="",
                provider=self.provider_name,
                model=request.model or self._model,
                finish_reason="error",
            )
        try:
            content = self._inner.call(
                prompt=request.prompt,
                system=request.system_prompt,
                temperature=request.temperature,
            )
            return LLMResponse(
                content=content or "",
                provider=self.provider_name,
                model=request.model or self._model,
            )
        except Exception as exc:
            _log.error("OntoderiveProvider.complete failed: %s", exc)
            return LLMResponse(
                content=f"[Ontoderive error: {exc}]",
                provider=self.provider_name,
                model=request.model or self._model,
                finish_reason="error",
            )

    # ------------------------------------------------------------------
    # Generation (async, delegates to sync via thread)
    # ------------------------------------------------------------------

    async def generate(self, request: LLMRequest) -> LLMResponse:
        import asyncio

        return await asyncio.to_thread(self.complete, request)
