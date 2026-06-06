"""SSOT-compatible provider using llm-gateway's unified API.

Replaces the legacy :mod:`ssot_kernel.extractor.llm.LLMBackend` import
with :func:`llm_gateway.provider.LLMProvider` for future-compatible
LLM access through the unified gateway.

.. deprecated:: 0.3.1
    Use :func:`llm_gateway.detection.detect_backends` directly.
    This class is kept for backward compatibility with
    ``ssot_kernel/extractor/llm.py`` imports.
"""

from __future__ import annotations

import logging

from llm_gateway.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    _with_llm_retry,
    record_llm_cost,
)

_log = logging.getLogger(__name__)


class SSOTProvider(LLMProvider):
    """Unified LLM provider — backward-compatible alias for ssot consumers."""

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
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "ssot-compat"

    def available_models(self) -> list[str]:
        return [self._model]

    def is_available(self) -> bool:
        return True

    def _ollama_complete(self, request: LLMRequest) -> LLMResponse:
        import json as _json
        import urllib.request
        import urllib.error

        model = request.model or self._model
        payload = _json.dumps({
            "model": model.removeprefix("ssot/"),
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        try:
            resp = urllib.request.urlopen(req, timeout=self._timeout)
            body = _json.loads(resp.read())
            usage = body.get("usage", {})
            response = LLMResponse(
                content=body["choices"][0]["message"]["content"],
                provider="ssot-compat",
                model=body.get("model", model),
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                finish_reason=body["choices"][0].get("finish_reason", "stop"),
            )
            record_llm_cost(response.model, response.input_tokens, response.output_tokens)
            return response
        except urllib.error.URLError as e:
            _log.error("SSOTProvider request failed: %s", e)
            return LLMResponse(content="", provider="ssot-compat", finish_reason="error")

    def complete(self, request: LLMRequest) -> LLMResponse:
        return _with_llm_retry(lambda: self._ollama_complete(request))
