from __future__ import annotations

"""Execution context and context window trimming.

Migrated from agentmesh/packages/toolkit/src/context/.

Provides:
- ContextItem: a message in the context window
- ContextTrimmer: trim context using multiple strategies (head / tail / importance / summary)
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class TrimStrategy(Enum):
    HEAD = "head"          # keep beginning, drop middle
    TAIL = "tail"          # keep end, drop beginning
    IMPORTANCE = "importance"  # rank by importance score
    SUMMARY = "summary"    # compress to summary


class Role(str, Enum):  # noqa: UP042
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ContextItem:
    content: str
    role: Role = Role.USER
    importance: float = 0.5      # 0-1, higher = more important
    pinned: bool = False         # never trimmed when True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrimResult:
    messages: list[ContextItem]
    original_tokens: int = 0
    trimmed_tokens: int = 0
    removed_count: int = 0


# ---------------------------------------------------------------------------
# Token estimator
# ---------------------------------------------------------------------------

Tokenizer = callable[[str], int]  # type: ignore[misc, valid-type]


def default_tokenizer(text: str) -> int:
    """Estimate token count. Chinese chars ~1.3, others ~1/4 char per token."""
    if not text:
        return 0
    cn = len(re.findall(r"[一-鿿]", text))
    other = len(text) - cn
    return int(cn * 1.3 + other / 4) + 1


# ---------------------------------------------------------------------------
# ContextTrimmer
# ---------------------------------------------------------------------------

class ContextTrimmer:
    """Trim a message list to fit within a token budget."""

    def __init__(self, tokenizer: Tokenizer | None = None, default_max_tokens: int = 4096) -> None:  # type: ignore[valid-type]
        self._tokenizer = tokenizer or default_tokenizer
        self._default_max_tokens = default_max_tokens

    def estimate_tokens(self, text: str) -> int:
        return self._tokenizer(text)

    def total_tokens(self, messages: list[ContextItem]) -> int:
        return sum(self.estimate_tokens(m.content) for m in messages)

    def trim(self, messages: list[ContextItem], max_tokens: int | None = None, strategy: TrimStrategy = TrimStrategy.HEAD) -> TrimResult:
        max_tok = max_tokens or self._default_max_tokens
        if not messages:
            return TrimResult(messages=[], original_tokens=0)
        original = self.total_tokens(messages)
        if original <= max_tok:
            return TrimResult(messages=list(messages), original_tokens=original, trimmed_tokens=original)

        pinned = [m for m in messages if m.pinned or m.role == Role.SYSTEM]
        removable = [m for m in messages if m not in pinned]
        pinned_tokens = self.total_tokens(pinned)
        available = max_tok - pinned_tokens
        if available <= 0:
            removed = len(removable)
            return TrimResult(messages=pinned, original_tokens=original, trimmed_tokens=pinned_tokens, removed_count=removed)

        if strategy == TrimStrategy.HEAD:
            trimmed = self._trim_head(removable, available)
        elif strategy == TrimStrategy.TAIL:
            trimmed = self._trim_tail(removable, available)
        elif strategy == TrimStrategy.IMPORTANCE:
            trimmed = self._trim_by_importance(removable, available, messages)
        elif strategy == TrimStrategy.SUMMARY:
            trimmed = self._trim_summary(removable, available)
        else:
            trimmed = self._trim_head(removable, available)

        result_list = pinned + trimmed
        removed = len(messages) - len(result_list)
        return TrimResult(messages=result_list, original_tokens=original, trimmed_tokens=self.total_tokens(result_list), removed_count=removed)

    def _trim_head(self, msgs: list[ContextItem], budget: int) -> list[ContextItem]:
        result: list[ContextItem] = []
        used = 0
        for m in msgs:
            tok = self.estimate_tokens(m.content)
            if used + tok <= budget:
                result.append(m)
                used += tok
            else:
                break
        return result

    def _trim_tail(self, msgs: list[ContextItem], budget: int) -> list[ContextItem]:
        result: list[ContextItem] = []
        used = 0
        for m in reversed(msgs):
            tok = self.estimate_tokens(m.content)
            if used + tok <= budget:
                result.insert(0, m)
                used += tok
            else:
                break
        return result

    def _trim_by_importance(self, msgs: list[ContextItem], budget: int, all_msgs: list[ContextItem]) -> list[ContextItem]:
        scored = []
        for i, m in enumerate(msgs):
            imp = m.importance
            if m.role == Role.ASSISTANT:
                imp = max(imp, 0.6)
            recency = 1.0 + (all_msgs.index(m) / max(len(all_msgs), 1)) * 0.3
            scored.append((m, imp * recency, self.estimate_tokens(m.content)))
        scored.sort(key=lambda x: x[1], reverse=True)
        chosen: list[ContextItem] = []
        used = 0
        for m, _score, tok in scored:
            if used + tok <= budget:
                chosen.append(m)
                used += tok
        chosen.sort(key=lambda m: all_msgs.index(m))
        return chosen

    def _trim_summary(self, msgs: list[ContextItem], budget: int) -> list[ContextItem]:
        important = [m for m in msgs if m.importance >= 0.8]
        others = [m for m in msgs if m.importance < 0.8]
        result = list(important)
        used = self.total_tokens(important)
        for m in others:
            tok = self.estimate_tokens(m.content)
            if used + tok <= budget:
                result.append(m)
                used += tok
            elif budget - used > 10:
                ratio = (budget - used) / max(tok, 1)
                chars = int(len(m.content) * ratio * 0.8)
                result.append(ContextItem(content=m.content[:chars] + "...", role=m.role, importance=m.importance))
                break
        return result


def create_context_trimmer(tokenizer: Tokenizer | None = None, default_max_tokens: int = 4096) -> ContextTrimmer:  # type: ignore[valid-type]
    return ContextTrimmer(tokenizer, default_max_tokens)
