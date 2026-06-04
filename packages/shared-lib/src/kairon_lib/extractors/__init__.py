from __future__ import annotations

"""
Extractors package — structured knowledge extraction from raw content.

Provides ``StructuredKnowledge`` (the canonical output model) and
``HtmlContentExtractor``.
"""

from .base import StructuredKnowledge

__all__ = [
    "StructuredKnowledge",
]
