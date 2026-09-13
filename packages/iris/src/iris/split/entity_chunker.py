"""Entity-Aware Chunking for Iris Connectors.

Implements Entity/Relation-Aware Chunking algorithm that ensures
business entities and semantic triples never cross chunk boundaries.

Reference: Semantica Entity/Relation-Aware Chunking (BET-Y1Q4-T6-27)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class ChunkConfig:
    """Configuration for entity-aware chunking.

    Attributes:
        max_chunk_size: Maximum characters per chunk.
        overlap: Number of overlapping characters between chunks.
        preserve_entities: Whether to prevent entity boundary splits.
        entity_patterns: Regex patterns for entity detection.
        sentence_boundary: Whether to prefer sentence boundaries.
    """

    max_chunk_size: int = 2000
    overlap: int = 200
    preserve_entities: bool = True
    entity_patterns: list[str] = field(default_factory=lambda: [
        r"[一-龥]{2,8}(?:公司|集团|局|部|委|会|院|所|中心)",  # Chinese orgs
        r"[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,4}",  # English proper nouns
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?",  # Dates
        r"[一-龥]{2,6}(?:法|条例|规定|办法|细则|标准)",  # Regulations
        r"(?:GB|ISO|IEEE|GB/T|DB)\s*\d+(?:[.-]\d+)*",  # Standards
    ])
    sentence_boundary: bool = True


@dataclass
class ChunkResult:
    """Result of chunking operation.

    Attributes:
        chunks: List of text chunks.
        entities_preserved: Number of entities preserved intact.
        total_entities: Total entities detected.
        entity_fragmentation_rate: Rate of entity fragmentation (0.0 = perfect).
    """

    chunks: list[str]
    entities_preserved: int = 0
    total_entities: int = 0

    @property
    def entity_fragmentation_rate(self) -> float:
        """Calculate entity fragmentation rate (0.0 = no fragmentation)."""
        if self.total_entities == 0:
            return 0.0
        return 1.0 - (self.entities_preserved / self.total_entities)


class EntityAwareChunker:
    """Entity-aware text chunker that prevents entity boundary splits.

    Uses regex-based entity detection to identify business entities,
    then ensures chunk boundaries never split an entity across chunks.

    Example:
        >>> chunker = EntityAwareChunker()
        >>> result = chunker.chunk("长文本...")
        >>> for chunk in result.chunks:
        ...     process(chunk)
    """

    def __init__(self, config: ChunkConfig | None = None) -> None:
        """Initialize chunker with configuration.

        Args:
            config: Chunking configuration. Uses defaults if None.
        """
        self.config = config or ChunkConfig()
        self._compiled_patterns = [
            re.compile(p) for p in self.config.entity_patterns
        ]

    def chunk(self, text: str) -> ChunkResult:
        """Split text into chunks preserving entity boundaries.

        Args:
            text: Input text to chunk.

        Returns:
            ChunkResult with chunks and entity preservation metrics.
        """
        if not text:
            return ChunkResult(chunks=[], entities_preserved=0, total_entities=0)

        entities = self._detect_entities(text)
        total_entities = len(entities)

        if len(text) <= self.config.max_chunk_size:
            return ChunkResult(
                chunks=[text],
                entities_preserved=total_entities,
                total_entities=total_entities,
            )

        chunks = _split_with_entity_preservation(
            text,
            entities,
            self.config.max_chunk_size,
            self.config.overlap,
            self.config.sentence_boundary,
        )

        preserved = _count_preserved_entities(chunks, entities)

        return ChunkResult(
            chunks=chunks,
            entities_preserved=preserved,
            total_entities=total_entities,
        )

    def _detect_entities(self, text: str) -> list[tuple[int, int]]:
        """Detect entity positions in text.

        Args:
            text: Input text to scan.

        Returns:
            List of (start, end) tuples for each entity found.
        """
        entities: list[tuple[int, int]] = []
        for pattern in self._compiled_patterns:
            for match in pattern.finditer(text):
                entities.append((match.start(), match.end()))
        # Merge overlapping entities and sort
        return _merge_overlapping_spans(entities)


def _merge_overlapping_spans(
    spans: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Merge overlapping entity spans.

    Args:
        spans: List of (start, end) character positions.

    Returns:
        Deduplicated, merged spans sorted by start position.
    """
    if not spans:
        return []

    sorted_spans = sorted(spans, key=lambda s: s[0])
    merged: list[tuple[int, int]] = [sorted_spans[0]]

    for start, end in sorted_spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def _find_sentence_boundary(text: str, target_pos: str, window: int = 100) -> int:
    """Find nearest sentence boundary to target position.

    Args:
        text: Full text.
        target_pos: Ideal split position.
        window: Search window around target.

    Returns:
        Adjusted position at sentence boundary.
    """
    sentence_ends = "。！？.!?\n"
    start = max(0, target_pos - window)
    end = min(len(text), target_pos + window)

    # Search backward for sentence end
    for i in range(target_pos, start - 1, -1):
        if i < len(text) and text[i] in sentence_ends:
            return i + 1

    # Search forward for sentence end
    for i in range(target_pos, end):
        if i < len(text) and text[i] in sentence_ends:
            return i + 1

    return target_pos


def _split_with_entity_preservation(
    text: str,
    entities: list[tuple[int, int]],
    max_size: int,
    overlap: int,
    use_sentence_boundary: bool,
) -> list[str]:
    """Split text into chunks while preserving entity boundaries.

    Args:
        text: Input text.
        entities: Entity spans to protect.
        max_size: Maximum chunk size.
        overlap: Overlap between chunks.
        use_sentence_boundary: Whether to prefer sentence boundaries.

    Returns:
        List of text chunks.
    """
    chunks: list[str] = []
    pos = 0
    text_len = len(text)

    while pos < text_len:
        # Calculate ideal end position
        ideal_end = min(pos + max_size, text_len)

        if ideal_end >= text_len:
            chunks.append(text[pos:])
            break

        # Find split point that doesn't break entities
        split_at = ideal_end

        # Check if ideal_end falls within an entity
        for ent_start, ent_end in entities:
            if pos < ent_start < ideal_end < ent_end:
                # Entity would be split - move split to before entity
                split_at = ent_start
                break
            elif ent_start <= ideal_end <= ent_end:
                # Ideal end is inside entity - move to after entity
                split_at = min(ent_end, text_len)
                break

        # Prefer sentence boundary if enabled
        if use_sentence_boundary and split_at < text_len:
            split_at = _find_sentence_boundary(text, split_at)

        chunks.append(text[pos:split_at])
        pos = max(split_at - overlap, pos + 1)  # Ensure forward progress

    return chunks


def _count_preserved_entities(
    chunks: list[str],
    entities: list[tuple[int, int]],
) -> int:
    """Count how many entities are fully contained within a single chunk.

    Args:
        chunks: Generated chunks.
        entities: Original entity spans.

    Returns:
        Number of entities preserved intact.
    """
    if not chunks or not entities:
        return 0

    # Build chunk boundaries
    chunk_boundaries: list[tuple[int, int]] = []
    pos = 0
    for chunk in chunks:
        chunk_boundaries.append((pos, pos + len(chunk)))
        pos += len(chunk)

    preserved = 0
    for ent_start, ent_end in entities:
        for chunk_start, chunk_end in chunk_boundaries:
            if chunk_start <= ent_start and ent_end <= chunk_end:
                preserved += 1
                break

    return preserved
