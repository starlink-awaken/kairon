"""Adapter: minerva OpenAICompatibleClient -> llm-gateway LLMProvider.

Wraps :class:`minerva.llm.OpenAICompatibleClient` (an async OpenAI-compatible
HTTP client) into the unified :class:`llm_gateway.provider.LLMProvider` ABC.
"""

from __future__ import annotations

import logging

from llm_gateway.provider import LLMProvider, LLMRequest, LLMResponse

_log = logging.getLogger(__name__)


class MinervaProvider(LLMProvider):
    """Adapter wrapping minerva's OpenAICompatibleClient into llm-gateway's ABC.

    Parameters
    ----------
    base_url:
        OpenAI-compatible endpoint (e.g. ``http://localhost:11434/v1``).
    api_key:
        API key (default ``"ollama"`` for local Ollama).
    model:
        Model identifier (``default "qwen3.6:35b-a3b-coding-nvfp4"``).
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        model: str = "qwen3.6:35b-a3b-coding-nvfp4",
        timeout: int = 120,
    ) -> None:
        super().__init__()
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = None
        self._import_ok = False

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "minerva"

    # ------------------------------------------------------------------
    # Lazy client
    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazy-initialize the minerva HTTP client."""
        if self._client is not None:
            return self._client
        try:
            from minerva.llm import (  # type: ignore[import-not-found]
                OpenAICompatibleClient,
            )

            self._client = OpenAICompatibleClient(
                base_url=self._base_url,
                api_key=self._api_key,
                model=self._model,
                timeout=self._timeout,
            )
            self._import_ok = True
        except ImportError:
            _log.debug("minerva package not installed — MinervaProvider unavailable")
        except Exception:
            _log.exception("Failed to create minerva client")
        return self._client

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self._get_client() is not None and self._import_ok

    # ------------------------------------------------------------------
    # Generation (async — delegates to minerva's native async method)
    # ------------------------------------------------------------------

    async def generate(self, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        if client is None:
            return LLMResponse(
                content="",
                provider=self.provider_name,
                model=request.model or self._model,
                finish_reason="error",
            )
        try:
            content = await client.generate(
                system=request.system_prompt or None,
                prompt=request.prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            return LLMResponse(
                content=content,
                provider=self.provider_name,
                model=request.model or self._model,
            )
        except Exception as exc:
            _log.error("MinervaProvider.generate failed: %s", exc)
            return LLMResponse(
                content=f"[Minerva error: {exc}]",
                provider=self.provider_name,
                model=request.model or self._model,
                finish_reason="error",
            )

    # ------------------------------------------------------------------
    # Generation (sync — run async in event loop)
    # ------------------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMResponse:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            # Already inside an async context — run via a new thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self.generate(request)).result()
        return asyncio.run(self.generate(request))
