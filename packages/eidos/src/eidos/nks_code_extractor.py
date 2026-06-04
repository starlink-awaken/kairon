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
Constraint: "Extracts entities from Python code"
Summary: "CodeExtractor - Extract knowledge from Python source code"
Tags:
- nks
- extractor
- python-code
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Code Extractor ≡ Module
# 内涵 ≝ {Code, Extractor}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, CodeExtractor)}
# 功能 ⊢ {Code_Extractor, Init_Code, Validate_Extractor}
# =============================================================================

_log = logging.getLogger(__name__)


@dataclass
class CodeExtractionResult:
    """Result of code extraction."""

    entities: list[CandidateEntity] = field(default_factory=list)
    relations: list[CandidateRelation] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class CodeExtractor:
    """
    CodeExtractor - Extracts knowledge from Python source code.

    Extracts classes, functions, and their relationships from Python
    files to feed into the NKS knowledge graph.
    """

    def __init__(self) -> None:
        """Initialize CodeExtractor."""
        self._deduct_metabolic_tax(amount=3.0)

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount

    def _generate_entity_id(self, name: str, source_file: str) -> str:
        """Generate unique entity ID."""
        input_str = f"{source_file}:{name}"
        return hashlib.sha256(input_str.encode()).hexdigest()[:16]

    def extract_from_python(self, content: str, source_file: str) -> CodeExtractionResult:
        """
        Extract entities and relations from Python code.

        Args:
            content: Python source code
            source_file: Source file path

        Returns:
            CodeExtractionResult
        """
        result = CodeExtractionResult()
        entities: dict[str, CandidateEntity] = {}

        # Extract classes
        classes = self._extract_classes(content)
        for class_name, bases, class_body in classes:
            entity_id = self._generate_entity_id(f"class_{class_name}", source_file)
            entities[class_name] = CandidateEntity(
                entity_id=entity_id,
                name=class_name,
                properties={
                    "type": "class",
                    "bases": bases,
                    "methods": self._extract_methods(class_body),
                    "docstring": self._extract_docstring(class_body),
                },
                source_file=source_file,
            )

            # Create inheritance relations
            for base in bases:
                if base not in entities:
                    base_id = self._generate_entity_id(f"class_{base}", source_file)
                    entities[base] = CandidateEntity(
                        entity_id=base_id,
                        name=base,
                        properties={"type": "class"},
                        source_file=source_file,
                    )
                result.relations.append(
                    CandidateRelation(
                        source_id=entities[class_name].entity_id,
                        target_id=entities[base].entity_id,
                        relation_type="inherits_from",
                        properties={},
                        source_file=source_file,
                    )
                )

        # Extract top-level functions
        functions = self._extract_functions(content, include_nested=False)
        for func_name, params, func_body in functions:
            entity_id = self._generate_entity_id(f"func_{func_name}", source_file)
            entities[f"func_{func_name}"] = CandidateEntity(
                entity_id=entity_id,
                name=func_name,
                properties={
                    "type": "function",
                    "parameters": params,
                    "docstring": self._extract_docstring(func_body),
                    "is_top_level": True,
                },
                source_file=source_file,
            )

        # Extract function calls (potential relations)
        all_functions = self._extract_functions(content, include_nested=True)
        for caller_name, _, caller_body in all_functions:
            caller_key = (
                f"func_{caller_name}"
                if caller_name in [f.split("func_")[1] for f in entities.keys() if f.startswith("func_")]
                else caller_name
            )

            if caller_key not in entities:
                continue

            called_functions = self._extract_function_calls(caller_body)
            for called_name in called_functions:
                called_key = f"func_{called_name}" if f"func_{called_name}" in entities else called_name

                if called_key in entities and called_key != caller_key:
                    result.relations.append(
                        CandidateRelation(
                            source_id=entities[caller_key].entity_id,
                            target_id=entities[called_key].entity_id,
                            relation_type="calls",
                            properties={},
                            source_file=source_file,
                        )
                    )

        result.entities = list(entities.values())
        result.metadata = {
            "classes_count": len(classes),
            "functions_count": len(functions),
            "relations_count": len(result.relations),
        }

        return result

    def _extract_classes(self, content: str) -> list[tuple[str, list[str], str]]:
        """Extract class definitions."""
        pattern = r"class\s+(\w+)\s*(?:\(([^)]*)\))?\s*:\s*([^{]*(?=\n(?:class|def|\Z)))"
        matches = re.findall(pattern, content, re.MULTILINE)

        results = []
        for class_name, bases, body in matches:
            base_list = [b.strip() for b in bases.split(",") if b.strip()] if bases else []
            # Get full body (until next class or top-level)
            results.append((class_name, base_list, body))

        return results

    def _extract_functions(self, content: str, include_nested: bool = False) -> list[tuple[str, list[str], str]]:
        """Extract function definitions."""
        if include_nested:
            pattern = r"def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^:]+))?\s*:"
        else:
            # Top-level only (not indented)
            pattern = r"^(?!class)def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^:]+))?\s*:"

        matches = re.findall(pattern, content, re.MULTILINE)

        results = []
        for func_name, params, _return_type in matches:
            param_list = [p.strip() for p in params.split(",") if p.strip()] if params else []
            body = ""  # Simplified - in real impl would extract full body
            results.append((func_name, param_list, body))

        return results

    def _extract_methods(self, class_body: str) -> list[str]:
        """Extract method names from class body."""
        pattern = r"def\s+(\w+)\s*\("
        return re.findall(pattern, class_body)

    def _extract_function_calls(self, content: str) -> list[str]:
        """Extract function calls from code."""
        # Match function calls: name(args)
        pattern = r"(\w+)\s*\("
        return list(set(re.findall(pattern, content)))

    def _extract_docstring(self, content: str) -> str | None:
        """Extract docstring from code."""
        # Match triple-quoted strings
        patterns = [r'"""([\s\S]*?)"""', r"'''([\s\S]*?)'''"]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        return None

    def ping(self) -> bool:
        """Health check for CodeExtractor."""
        return True
