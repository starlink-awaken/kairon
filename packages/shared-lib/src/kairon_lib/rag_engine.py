"""RAG (Retrieval Augmented Generation) engine.

Provides Chunker, Embedder, Retriever, and RAGPipeline for building
retrieval-augmented generation workflows.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


def _simple_hash_embed(text: str, dim: int = 64) -> list[float]:
    """Produce a deterministic float vector from text."""
    vec = [0.0] * dim
    for i, ch in enumerate(text):
        vec[i % dim] += (ord(ch) / 127.0) * ((-1) ** (i // dim))
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class Chunker:
    """Split text into overlapping chunks."""

    def __init__(self, chunk_size: int = 512, overlap: int = 64) -> None:
        if overlap >= chunk_size:
            raise ValueError("overlap must be less than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
        """Split *text* into chunks of *chunk_size* characters with *overlap*."""
        size = chunk_size or self.chunk_size
        olap = overlap or self.overlap
        step = size - olap
        if step <= 0:
            raise ValueError("chunk_size - overlap must be positive")
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += step
        return chunks

    def chunk_by_sentences(self, text: str, max_chars: int = 512) -> list[str]:
        """Split on sentence boundaries, merging until *max_chars*."""
        sentences = re.split(r"(?<=[。.!?])\s+", text)
        chunks: list[str] = []
        buffer = ""
        for sent in sentences:
            if len(buffer) + len(sent) <= max_chars:
                buffer += sent
            else:
                if buffer:
                    chunks.append(buffer)
                buffer = sent
        if buffer:
            chunks.append(buffer)
        return chunks


@dataclass
class Embedder:
    """Simple deterministic embedder using hash-based vectors."""

    dimension: int = 64

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into float vectors."""
        return [_simple_hash_embed(t, self.dimension) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        return _simple_hash_embed(query, self.dimension)


@dataclass
class Chunk:
    """A single chunk with its embedding vector."""

    text: str
    vector: list[float] = field(default_factory=list)


class Retriever:
    """Retrieve top-k chunks by cosine similarity to a query embedding."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []

    def index(self, texts: list[str], embedder: Embedder) -> None:
        """Index texts by computing their embeddings."""
        vectors = embedder.embed(texts)
        self._chunks = [Chunk(text=t, vector=v) for t, v in zip(texts, vectors)]

    def retrieve(
        self,
        chunks: list[Chunk],
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[str]:
        """Return top-k chunk texts sorted by cosine similarity."""
        scored: list[tuple[float, str]] = []
        for chunk in chunks:
            sim = sum(a * b for a, b in zip(query_embedding, chunk.vector))
            scored.append((sim, chunk.text))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in scored[:top_k]]


@dataclass
class RAGPipeline:
    """High-level RAG pipeline combining chunking, embedding, and retrieval."""

    chunker: Chunker = field(default_factory=Chunker)
    embedder: Embedder = field(default_factory=Embedder)
    retriever: Retriever = field(default_factory=Retriever)

    def run(self, document: str, query: str, top_k: int = 5) -> list[str]:
        """Chunk *document*, embed both chunks and *query*, return top-k texts."""
        chunks = self.chunker.chunk_text(document)
        vectors = self.embedder.embed(chunks)
        chunk_objs = [Chunk(text=t, vector=v) for t, v in zip(chunks, vectors)]
        qvec = self.embedder.embed_query(query)
        return self.retriever.retrieve(chunk_objs, qvec, top_k)
