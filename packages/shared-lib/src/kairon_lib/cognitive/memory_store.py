"""Memory store with embedding, retrieval, pattern loading.

Migrated from agentmesh toolkit/src/memory/ (MemoryStore, EmbeddingProvider,
ContextRetriever, types) and patterns/PatternLoader.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

_COSINE_EPS = 1e-10


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    denom = na * nb
    return dot / denom if denom > _COSINE_EPS else 0.0


def _generate_id(prefix: str = "mem") -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{uuid_short()}"


def uuid_short() -> str:
    import uuid
    return uuid.uuid4().hex[:8]


@dataclass
class MemoryMetadata:
    session_id: str = "default"
    timestamp: float = 0.0
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class MemoryEntry:
    id: str = ""
    content: str = ""
    embedding: list[float] | None = None
    metadata: MemoryMetadata = field(default_factory=MemoryMetadata)
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class RetrievalQuery:
    query: str = ""
    limit: int = 10
    threshold: float = 0.0
    filters: dict[str, Any] | None = None


@dataclass
class RetrievedContext:
    entries: list[MemoryEntry] = field(default_factory=list)
    total_tokens: int = 0
    query: str = ""


@dataclass
class MemoryStats:
    total_entries: int = 0
    total_sessions: int = 0
    average_importance: float = 0.0
    oldest_entry: float = 0.0
    newest_entry: float = 0.0


class MemoryStore:
    """In-memory memory store with indexing by session and tags."""

    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}
        self._sessions: dict[str, set[str]] = {}
        self._tag_index: dict[str, set[str]] = {}

    async def store(self, content: str, metadata: MemoryMetadata | None = None) -> MemoryEntry:
        if metadata is None:
            metadata = MemoryMetadata()
        now = time.time()
        entry = MemoryEntry(
            id=_generate_id(),
            content=content,
            metadata=metadata,
            created_at=now,
            updated_at=now,
        )
        entry.metadata.timestamp = now
        self._entries[entry.id] = entry
        self._index_entry(entry)
        return entry

    async def retrieve(self, query: RetrievalQuery) -> list[MemoryEntry]:
        entries = list(self._entries.values())
        if query.filters:
            entries = self._apply_filters(entries, query.filters)  # type: ignore[attr-defined]
        if query.query and entries:
            keywords = self._extract_keywords(query.query)
            scored = [(self._relevance(e, keywords), e) for e in entries]
            scored.sort(key=lambda x: x[0], reverse=True)
            entries = [e for score, e in scored if score >= query.threshold][: query.limit]
        else:
            entries = entries[: query.limit]
        return entries

    async def build_context(self, query: str, max_tokens: int) -> RetrievedContext:
        entries = await self.retrieve(RetrievalQuery(query=query, limit=20))
        selected: list[MemoryEntry] = []
        total = 0
        for e in entries:
            tokens = self._estimate_tokens(e.content)
            if total + tokens <= max_tokens:
                selected.append(e)
                total += tokens
            else:
                break
        return RetrievedContext(entries=selected, total_tokens=total, query=query)

    async def update(self, entry_id: str, content: str | None = None, importance: float | None = None) -> MemoryEntry | None:
        entry = self._entries.get(entry_id)
        if not entry:
            return None
        if content is not None:
            entry.content = content
        if importance is not None:
            entry.metadata.importance = importance
        entry.updated_at = time.time()
        return entry

    async def delete(self, entry_id: str) -> bool:
        entry = self._entries.pop(entry_id, None)
        if entry:
            self._unindex_entry(entry)
            return True
        return False

    def get_by_session(self, session_id: str) -> list[MemoryEntry]:
        ids = self._sessions.get(session_id, set())
        return [self._entries[eid] for eid in ids if eid in self._entries]

    def get_stats(self) -> MemoryStats:
        entries = list(self._entries.values())
        sessions = set(e.metadata.session_id for e in entries)
        avg_imp = sum(e.metadata.importance for e in entries) / max(len(entries), 1)
        times = [e.created_at for e in entries] or [0]
        return MemoryStats(
            total_entries=len(entries),
            total_sessions=len(sessions),
            average_importance=avg_imp,
            oldest_entry=min(times),
            newest_entry=max(times),
        )

    def _index_entry(self, entry: MemoryEntry) -> None:
        sid = entry.metadata.session_id
        self._sessions.setdefault(sid, set()).add(entry.id)
        for tag in entry.metadata.tags:
            self._tag_index.setdefault(tag, set()).add(entry.id)

    def _unindex_entry(self, entry: MemoryEntry) -> None:
        self._sessions.get(entry.metadata.session_id, set()).discard(entry.id)
        for tag in entry.metadata.tags:
            self._tag_index.get(tag, set()).discard(entry.id)

    def _extract_keywords(self, text: str) -> set[str]:
        stop = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "to", "and", "or", "it",
        }
        words = text.lower().split()
        return {w for w in words if len(w) > 2 and w not in stop}

    def _relevance(self, entry: MemoryEntry, keywords: set[str]) -> float:
        content_kw = self._extract_keywords(entry.content)
        matches = sum(1 for k in keywords if k in content_kw)
        base = matches / max(len(keywords), 1)
        return min(base + entry.metadata.importance * 0.2, 1.0)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        words = text.split()
        chinese = sum(1 for c in text if "一" <= c <= "鿿")
        return max(1, len(words) + chinese)


class LocalEmbeddingProvider:
    """Local embedding provider using TF-IDF-style hashing."""

    def __init__(self, dimensions: int = 128) -> None:
        self._dim = dimensions
        self._cache: dict[str, list[float]] = {}

    async def embed(self, text: str) -> list[float]:
        if text in self._cache:
            return self._cache[text]
        vec = self._generate(text)
        self._cache[text] = vec
        return vec

    def _generate(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        tokens = text.lower().split()
        for token in tokens:
            h = hash(token)
            for i in range(4):
                pos = abs(h * (i + 1) * 2654435761) % self._dim
                vec[pos] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    async def similarity(self, a: str, b: str) -> float:
        va, vb = await asyncio_gather(self.embed(a), self.embed(b))
        return cosine_similarity(va, vb)


class ContextRetriever:
    """Context builder backed by MemoryStore with short-term memory."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store
        self._stm: dict[str, list[MemoryEntry]] = {}

    async def build_context(self, query: str, max_tokens: int) -> RetrievedContext:
        return await self._store.build_context(query, max_tokens)

    def add_stm(self, session_id: str, content: str) -> None:
        entry = MemoryEntry(
            id=_generate_id("stm"),
            content=content,
            metadata=MemoryMetadata(session_id=session_id),
        )
        self._stm.setdefault(session_id, []).append(entry)

    def get_stm(self, session_id: str) -> list[MemoryEntry]:
        return self._stm.get(session_id, [])

    def clear_stm(self, session_id: str | None = None) -> None:
        if session_id:
            self._stm.pop(session_id, None)
        else:
            self._stm.clear()


async def asyncio_gather(*coros):
    import asyncio
    return await asyncio.gather(*coros)


class PatternExecutor:
    """Simple pattern (template) executor, ported from PatternLoader."""

    def __init__(self, template: str, variables: list[str] | None = None) -> None:
        self._template = template
        self._variables = variables or []

    def execute(self, **kwargs: str) -> str:
        result = self._template
        for var in self._variables:
            val = kwargs.get(var, f"{{{{{var}}}}}")
            result = result.replace(f"{{{{{var}}}}}", val)
        return result
