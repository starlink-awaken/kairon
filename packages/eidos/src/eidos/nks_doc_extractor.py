from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

from eidos.graph_store import CandidateEntity, CandidateRelation  # type: ignore[import-not-found]

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "Extracts entities from markdown documents"
Summary: "DocExtractor - Extract knowledge from markdown documents"
Tags:
- nks
- extractor
- markdown
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Doc Extractor ≡ Module
# 内涵 ≝ {Doc, Extractor}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, DocExtractor)}
# 功能 ⊢ {Doc_Extractor, Init_Doc, Validate_Extractor}
# =============================================================================

_log = logging.getLogger(__name__)


@dataclass
class DocExtractionResult:
    """Result of document extraction."""

    entities: list[CandidateEntity] = field(default_factory=list)
    relations: list[CandidateRelation] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DocExtractor:
    """
    DocExtractor - Extracts knowledge from markdown documents.

    Extracts entities (concepts, terms) and relations from markdown
    files to feed into the NKS knowledge graph.
    """

    def __init__(self) -> None:
        """Initialize DocExtractor."""
        self._deduct_metabolic_tax(amount=3.0)

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount

    def _generate_entity_id(self, name: str, source_file: str) -> str:
        """Generate unique entity ID."""
        input_str = f"{source_file}:{name}"
        return hashlib.sha256(input_str.encode()).hexdigest()[:16]

    def extract_from_markdown(self, content: str, source_file: str) -> DocExtractionResult:
        """
        Extract entities and relations from markdown content.

        Args:
            content: Markdown content
            source_file: Source file path

        Returns:
            DocExtractionResult
        """
        result = DocExtractionResult()
        entities: dict[str, CandidateEntity] = {}

        # Extract headers (potential entities)
        headers = self._extract_headers(content)
        for header in headers:
            entity_id = self._generate_entity_id(header, source_file)
            entities[header] = CandidateEntity(
                entity_id=entity_id,
                name=header,
                properties={"type": "header", "level": self._get_header_level(content, header)},
                source_file=source_file,
            )

        # Extract bold terms (potential entities)
        bold_terms = self._extract_bold_terms(content)
        for term in bold_terms:
            if term not in entities:
                entity_id = self._generate_entity_id(term, source_file)
                entities[term] = CandidateEntity(
                    entity_id=entity_id,
                    name=term,
                    properties={"type": "bold_term"},
                    source_file=source_file,
                )

        # Extract links (potential relations)
        links = self._extract_links(content)
        for source_text, target_url in links:
            # Create entities if they don't exist
            if source_text not in entities:
                entity_id = self._generate_entity_id(source_text, source_file)
                entities[source_text] = CandidateEntity(
                    entity_id=entity_id,
                    name=source_text,
                    properties={"type": "link_source"},
                    source_file=source_file,
                )

            # Create relation
            target_entity = target_url.split("/")[-1] if "/" in target_url else target_url
            if target_entity not in entities:
                target_id = self._generate_entity_id(target_entity, source_file)
                entities[target_entity] = CandidateEntity(
                    entity_id=target_id,
                    name=target_entity,
                    properties={"type": "link_target"},
                    source_file=source_file,
                )

            result.relations.append(
                CandidateRelation(
                    source_id=entities[source_text].entity_id,
                    target_id=entities[target_entity].entity_id,
                    relation_type="links_to",
                    properties={"url": target_url},
                    source_file=source_file,
                )
            )

        # Extract code blocks (potential entities)
        code_blocks = self._extract_code_blocks(content)
        for i, code in enumerate(code_blocks):
            entity_id = self._generate_entity_id(f"code_block_{i}", source_file)
            entities[f"code_block_{i}"] = CandidateEntity(
                entity_id=entity_id,
                name=f"Code Block {i}",
                properties={
                    "type": "code_block",
                    "language": self._get_code_language(code),
                    "content_hash": hashlib.sha256(code.encode()).hexdigest()[:16],
                },
                source_file=source_file,
            )

        result.entities = list(entities.values())
        result.metadata = {
            "headers_count": len(headers),
            "bold_terms_count": len(bold_terms),
            "links_count": len(links),
            "code_blocks_count": len(code_blocks),
        }

        return result

    def _extract_headers(self, content: str) -> list[str]:
        """Extract all headers from markdown."""
        pattern = r"^#{1,6}\s+(.+)$"
        matches = re.findall(pattern, content, re.MULTILINE)
        return [m.strip() for m in matches]

    def _get_header_level(self, content: str, header: str) -> int:
        """Get header level (1-6)."""
        pattern = f"^#{{1,6}}\\s+{re.escape(header)}$"
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            line = match.group(0)
            return len(line) - len(line.lstrip("#"))
        return 1

    def _extract_bold_terms(self, content: str) -> list[str]:
        """Extract bold terms from markdown."""
        # Match **bold** and __bold__
        patterns = [r"\*\*(.+?)\*\*", r"__(.+?)__"]
        terms = []

        for pattern in patterns:
            matches = re.findall(pattern, content)
            terms.extend([m.strip() for m in matches if m.strip()])

        return list(set(terms))  # Deduplicate

    def _extract_links(self, content: str) -> list[tuple[str, str]]:
        """Extract markdown links [text](url)."""
        pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        matches = re.findall(pattern, content)
        return [(m[0].strip(), m[1].strip()) for m in matches]

    def _extract_code_blocks(self, content: str) -> list[str]:
        """Extract code blocks from markdown."""
        pattern = r"```[\w\W]*?```"
        matches = re.findall(pattern, content)
        return [m.strip("`").strip() for m in matches if m.strip()]

    def _get_code_language(self, code_block: str) -> str:
        """Extract language from code block."""
        lines = code_block.split("\n")
        if lines and lines[0].strip():
            first_line = lines[0].strip()
            # Check if first line is a language marker
            if re.match(r"^[a-z]+$", first_line.lower()):
                return first_line.lower()
        return "text"

    def ping(self) -> bool:
        """Health check for DocExtractor."""
        return True
