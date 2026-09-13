"""Text splitting module for Iris connectors.

Provides entity-aware chunking to prevent business entities and triples
from being split across chunk boundaries.
"""

from iris.split.entity_chunker import EntityAwareChunker, ChunkConfig, ChunkResult

__all__ = ["EntityAwareChunker", "ChunkConfig", "ChunkResult"]
