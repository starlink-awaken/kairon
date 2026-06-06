"""Ontoderive-compatible provider using llm-gateway's unified API.

Replaces the legacy :mod:`ontoderive` backend import with
:func:`llm_gateway.provider.LLMProvider` for future-compatible
LLM access through the unified gateway.

.. deprecated:: 0.3.1
    Use :func:`llm_gateway.detection.detect_backends` directly.
    This class is kept for backward compatibility with
    ``ontoderive/engine/intelligence/providers.py`` imports.
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


class OntoderiveProvider(LLMProvider):
    """Unified LLM provider — backward-compatible alias for ontoderive consumers."""

    DEFAULT_MODEL = "gpt-4"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
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

    def _openai_complete(self, request: LLMRequest) -> LLMResponse:
        import json as _json
        import urllib.request
        import urllib.error

        model = request.model or self._model
        payload = _json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        try:
            resp = urllib.request.urlopen(req, timeout=120)
            body = _json.loads(resp.read())
            usage = body.get("usage", {})
            response = LLMResponse(
                content=body["choices"][0]["message"]["content"],
                provider="ontoderive-compat",
                model=body.get("model", model),
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                finish_reason=body["choices"][0].get("finish_reason", "stop"),
            )
            record_llm_cost(response.model, response.input_tokens, response.output_tokens)
            return response
        except urllib.error.URLError as e:
            _log.error("OntoderiveProvider request failed: %s", e)
            return LLMResponse(content="", provider="ontoderive-compat", finish_reason="error")

    def complete(self, request: LLMRequest) -> LLMResponse:
        return _with_llm_retry(lambda: self._openai_complete(request))
