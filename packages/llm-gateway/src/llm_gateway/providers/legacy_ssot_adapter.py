"""Adapter: ssot LLMBackend -> llm-gateway LLMProvider.

Wraps :class:`ssot_kernel.extractor.llm.LLMBackend` (with its concrete
implementations ``OllamaBackend`` and ``OpenAIBackend``) into the unified
:class:`llm_gateway.provider.LLMProvider` ABC.
"""

from __future__ import annotations

import logging

from llm_gateway.provider import LLMProvider, LLMRequest, LLMResponse

_log = logging.getLogger(__name__)


class SSOTProvider(LLMProvider):
    """Adapter wrapping ssot's LLMBackend into llm-gateway's ABC.

    Parameters
    ----------
    backend_type:
        Which backend to instantiate — ``"openai"`` (default) or ``"ollama"``.
    model:
        Model name (optional; each backend has its own default).
    api_key:
        API key (used for OpenAI backend).
    base_url:
        Base URL (e.g. ``http://localhost:11434`` for Ollama).
    """

    def __init__(
        self,
        backend_type: str = "openai",
        model: str = "",
        api_key: str = "",
        base_url: str = "",
    ) -> None:
        super().__init__()
        self._backend_type = backend_type
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._inner = None
        self._import_ok = False

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "ssot"

    # ------------------------------------------------------------------
    # Lazy init
    # ------------------------------------------------------------------

    def _get_backend(self):
        """Lazy-initialize the ssot LLM backend."""
        if self._inner is not None:
            return self._inner
        try:
            from ssot_kernel.extractor.llm import (  # type: ignore[import-not-found]
                OllamaBackend,
                OpenAIBackend,
            )

            if self._backend_type == "ollama":
                self._inner = OllamaBackend(
                    model=self._model,
                    base_url=self._base_url,
                )
            else:
                self._inner = OpenAIBackend(
                    model=self._model or "gpt-4o-mini",
                    api_key=self._api_key,
                    base_url=self._base_url or "https://api.openai.com/v1",
                )
            self._import_ok = True
        except ImportError:
            _log.debug(
                "ssot_kernel package not installed — SSOTProvider unavailable"
            )
        except Exception:
            _log.exception("Failed to create ssot backend")
        return self._inner

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self._get_backend() is not None and self._import_ok

    # ------------------------------------------------------------------
    # Generation (sync — ssot's LLMBackend is synchronous)
    # ------------------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMResponse:
        backend = self._get_backend()
        if backend is None:
            return LLMResponse(
                content="",
                provider=self.provider_name,
                model=request.model or self._model,
                finish_reason="error",
            )
        try:
            content = backend.complete(
                system=request.system_prompt,
                user=request.prompt,
                temperature=request.temperature,
            )
            return LLMResponse(
                content=content,
                provider=self.provider_name,
                model=request.model or self._model or backend.name,
            )
        except Exception as exc:
            _log.error("SSOTProvider.complete failed: %s", exc)
            return LLMResponse(
                content=f"[SSOT error: {exc}]",
                provider=self.provider_name,
                model=request.model or self._model,
                finish_reason="error",
            )

    # ------------------------------------------------------------------
    # Generation (async — delegates to sync via thread)
    # ------------------------------------------------------------------

    async def generate(self, request: LLMRequest) -> LLMResponse:
        import asyncio

        return await asyncio.to_thread(self.complete, request)
