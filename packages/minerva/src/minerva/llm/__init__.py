"""Minerva LLM client module."""

# ── 向后兼容 ──────────────────────────────────────────
# 新代码推荐使用 llm-gateway，旧代码通过此别名继续工作
from llm_gateway.providers.legacy_minerva_adapter import (
    MinervaProvider as OpenAICompatibleClient,
)

from minerva.llm.client import (
    OpenAICompatibleClient as _OriginalOpenAICompatibleClient,  # type: ignore[import-not-found]  # noqa: F401
)

__all__ = ["OpenAICompatibleClient"]
