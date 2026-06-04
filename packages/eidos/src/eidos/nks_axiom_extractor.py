from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

from eidos.graph_store import CandidateEntity, CandidateRelation

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "Extracts entities from axiom files"
Summary: "AxiomExtractor - Extract knowledge from axiom and rule files"
Tags:
- nks
- extractor
- axiom
- rules
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Axiom Extractor ≡ Module
# 内涵 ≝ {Axiom, Extractor}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, AxiomExtractor)}
# 功能 ⊢ {Axiom_Extractor, Init_Axiom, Validate_Extractor}
# =============================================================================

_log = logging.getLogger(__name__)


@dataclass
class AxiomExtractionResult:
    """Result of axiom extraction."""

    entities: list[CandidateEntity] = field(default_factory=list)
    relations: list[CandidateRelation] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class AxiomExtractor:
    """
    AxiomExtractor - Extracts knowledge from axiom and rule files.

    Extracts rules, constraints, and their relationships from system
    axiom files to feed into the NKS knowledge graph.
    """

    def __init__(self) -> None:
        """Initialize AxiomExtractor."""
        self._deduct_metabolic_tax(amount=3.0)

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount

    def _generate_entity_id(self, name: str, source_file: str) -> str:
        """Generate unique entity ID."""
        input_str = f"{source_file}:{name}"
        return hashlib.sha256(input_str.encode()).hexdigest()[:16]

    def extract_from_axioms(self, content: str, source_file: str) -> AxiomExtractionResult:
        """
        Extract entities and relations from axiom/rule files.

        Args:
            content: Axiom file content
            source_file: Source file path

        Returns:
            AxiomExtractionResult
        """
        result = AxiomExtractionResult()
        entities: dict[str, CandidateEntity] = {}

        # Extract rule definitions
        rules = self._extract_rules(content)
        for rule_id, rule_type, rule_body in rules:
            entity_id = self._generate_entity_id(rule_id, source_file)
            entities[rule_id] = CandidateEntity(
                entity_id=entity_id,
                name=rule_id,
                properties={
                    "type": "rule",
                    "rule_type": rule_type,
                    "description": self._extract_description(rule_body),
                    "constraints": self._extract_constraints(rule_body),
                },
                source_file=source_file,
            )

        # Extract axiom definitions
        axioms = self._extract_axioms(content)
        for axiom_name, axiom_body in axioms:
            entity_id = self._generate_entity_id(axiom_name, source_file)
            entities[axiom_name] = CandidateEntity(
                entity_id=entity_id,
                name=axiom_name,
                properties={"type": "axiom", "description": self._extract_description(axiom_body)},
                source_file=source_file,
            )

        # Extract references/dependencies
        references = self._extract_references(content)
        for source_ref, target_ref, ref_type in references:
            if source_ref in entities and target_ref in entities:
                result.relations.append(
                    CandidateRelation(
                        source_id=entities[source_ref].entity_id,
                        target_id=entities[target_ref].entity_id,
                        relation_type=ref_type,
                        properties={},
                        source_file=source_file,
                    )
                )

        result.entities = list(entities.values())
        result.metadata = {
            "rules_count": len(rules),
            "axioms_count": len(axioms),
            "relations_count": len(result.relations),
        }

        return result

    def _extract_rules(self, content: str) -> list[tuple[str, str, str]]:
        """Extract rule definitions."""
        # Match patterns like:
        # Rule-ID: R0-ACT-SYS-01
        # Type: Constraint
        # or: def rule_xxx()
        patterns = [
            r"Rule-ID:\s*([Rr]\d+-[A-Z]+-[A-Z]+-\d+)[\s\S]*?Type:\s*(\w+)",
            r"def\s+(rule_\w+)[\s\S]*?(?=\ndef rule_|$)",
            r"class\s+(\w*Rule)\s*:",
        ]

        results = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                if len(match) == 2:
                    rule_id, rule_type = match
                    body = self._get_rule_body(content, rule_id)
                    results.append((rule_id, rule_type, body))
                elif len(match) == 1:
                    rule_name = match[0]
                    body = self._get_rule_body(content, rule_name)
                    results.append((rule_name, "code_rule", body))

        return results

    def _extract_axioms(self, content: str) -> list[tuple[str, str]]:
        """Extract axiom definitions."""
        patterns = [r"Axiom:\s*(\w+)", r"class\s+(\w*Axiom)\s*:", r"def\s+(axiom_\w+)\("]

        results = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                axiom_name = match if isinstance(match, str) else match[0]
                body = self._get_axiom_body(content, axiom_name)
                results.append((axiom_name, body))

        return results

    def _extract_references(self, content: str) -> list[tuple[str, str, str]]:
        """Extract references between rules/axioms."""
        references = []

        # Find mentions of other rules (e.g., "see R0-ACT-SYS-01")
        pattern = r"(?:see|refers to|references|depends on)\s+([Rr]\d+-[A-Z]+-[A-Z]+-\d+)"
        mentions = re.findall(pattern, content, re.IGNORECASE)

        for mention in mentions:
            # In a real implementation, we'd track the source rule
            # For now, add a generic relation
            references.append(("unknown", mention, "references"))

        # Find import statements in Python
        import_pattern = r"from\s+([^\s]+)\s+import|import\s+([^\s]+)"
        imports = re.findall(import_pattern, content)

        for import_match in imports:
            module = import_match[0] if import_match[0] else import_match[1]
            references.append(("unknown", module, "imports"))

        return references

    def _extract_description(self, body: str) -> str:
        """Extract description from rule/axiom body."""
        # Look for docstring or comment
        patterns = [
            r'"""([\s\S]*?)"""',
            r"'''([\s\S]*?)'''",
            r"# Description:\s*(.+)",
            r"#\s*(.+)(?=\n#|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, body)
            if match:
                desc = match.group(1).strip()
                if desc and len(desc) > 10:  # Avoid very short matches
                    return desc

        return ""

    def _extract_constraints(self, body: str) -> list[str]:
        """Extract constraint expressions from rule body."""
        constraints = []

        # Look for constraint-like patterns
        patterns = [
            r"constraint[:\s]+(.+)",
            r"ensure[:\s]+(.+)",
            r"assert\s+(.+)",
            r"validate[:\s]+(.+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            constraints.extend([m.strip() for m in matches if m.strip()])

        return constraints

    def _get_rule_body(self, content: str, rule_id: str) -> str:
        """Extract the body of a rule."""
        # Simple implementation - find content after rule ID
        pattern = rf"{re.escape(rule_id)}[\s\S]*?(?=Rule-ID:|def rule_|class|\Z)"
        match = re.search(pattern, content)
        if match:
            return match.group(0)
        return ""

    def _get_axiom_body(self, content: str, axiom_name: str) -> str:
        """Extract the body of an axiom."""
        pattern = rf"{re.escape(axiom_name)}[\s\S]*?(?=Rule-ID:|def rule_|class|Axiom:|\Z)"
        match = re.search(pattern, content)
        if match:
            return match.group(0)
        return ""

    def ping(self) -> bool:
        """Health check for AxiomExtractor."""
        return True
