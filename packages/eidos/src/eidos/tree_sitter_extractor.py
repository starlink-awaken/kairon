"""Tree-sitter based AST code extractor with regex fallback for NKS pipeline.

Provides entity/relation extraction from source code. Full tree-sitter
parsing backend is planned; current implementation returns empty results
with a stable interface for downstream consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TreeSitterExtractionResult:
    """Result of a tree-sitter extraction."""

    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    functions: list[dict[str, Any]] = field(default_factory=list)
    classes: list[dict[str, Any]] = field(default_factory=list)


class TreeSitterExtractor:
    """Tree-sitter based AST code extractor.

    Current implementation returns empty results. Integrate tree-sitter
    bindings (e.g. tree-sitter-python) for production use.
    """

    def __init__(self, language: str = "python") -> None:
        self.language = language

    def extract(self, source_code: str, file_path: str = "") -> TreeSitterExtractionResult:
        """Extract entities and relations from source code.

        Returns empty result; integrate tree-sitter for production use.
        """
        return TreeSitterExtractionResult()

    def extract_file(self, file_path: str) -> TreeSitterExtractionResult:
        """Extract entities and relations from a file."""
        return TreeSitterExtractionResult()


__all__ = [
    "TreeSitterExtractionResult",
    "TreeSitterExtractor",
]
