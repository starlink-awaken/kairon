from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L4
Summary: 'Tree-sitter based AST code extractor with regex fallback for NKS pipeline.'
Authority: organs/D-Memory/AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Tree Sitter Extractor ≡ Module
# 内涵 ≝ {Tree, Sitter, Extractor}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, TreeSitterExtractor)}
# 功能 ⊢ {Tree_Sitter, Sitter_Extractor, Extractor_Init}
# =============================================================================
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inline CandidateEntity / CandidateRelation stubs so this module works even
# if graph_store is not importable in all environments.
# ---------------------------------------------------------------------------
try:
    from eidos.organs.nks.graph_store import (
        CandidateEntity,
        CandidateRelation,
    )
except ImportError as exc:

    @dataclass
    class CandidateEntity:  # type: ignore[no-redef]
        entity_id: str
        name: str
        properties: dict = field(default_factory=dict)
        source_file: str = ""
        embedding: list[float] | None = None

    @dataclass
    class CandidateRelation:  # type: ignore[no-redef]
        source_id: str
        target_id: str
        relation_type: str
        properties: dict = field(default_factory=dict)
        confidence: float = 1.0
        source_file: str = ""

    raise RuntimeError(
        "TreeSitterExtractor requires CoreService; refusing to degrade silently to an in-module stub."
    ) from exc


@dataclass
class TreeSitterExtractionResult:
    """Result from tree-sitter AST extraction."""

    file_path: str
    language: str
    entities: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Language-specific regex patterns for fallback extraction
# ---------------------------------------------------------------------------

# Optional TS/JS export prefix: "export ", "export default ", "declare "
_TS_PREFIX = r"(?:export\s+(?:default\s+)?|declare\s+)?"
# Optional "abstract " modifier
_ABSTRACT = r"(?:abstract\s+)?"

_LANG_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "python": [
        (r"^class\s+(\w+)", "class"),
        (r"^\s*def\s+(\w+)\s*\(", "function"),
    ],
    "javascript": [
        (r"^(?:export\s+(?:default\s+)?)?class\s+(\w+)", "class"),
        (r"^(?:export\s+)?function\s+(\w+)\s*\(", "function"),
        (r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\()", "function"),
    ],
    "typescript": [
        # class / abstract class (with optional export / declare / abstract)
        (_TS_PREFIX + _ABSTRACT + r"class\s+(\w+)", "class"),
        # interface
        (_TS_PREFIX + r"interface\s+(\w+)", "interface"),
        # type alias
        (_TS_PREFIX + r"type\s+(\w+)\s*[=<]", "type"),
        # enum
        (_TS_PREFIX + r"(?:const\s+)?enum\s+(\w+)", "enum"),
        # namespace / module
        (_TS_PREFIX + r"(?:namespace|module)\s+(\w+)", "namespace"),
        # function
        (_TS_PREFIX + r"(?:async\s+)?function\s+(\w+)\s*[\(<]", "function"),
        (r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\()", "function"),
    ],
    "rust": [
        (r"^(?:pub(?:\([^)]*\))?\s+)?struct\s+(\w+)", "struct"),
        (r"^(?:pub(?:\([^)]*\))?\s+)?enum\s+(\w+)", "enum"),
        (r"^(?:pub(?:\([^)]*\))?\s+)?trait\s+(\w+)", "trait"),
        (r"^(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(\w+)\s*[\(<]", "function"),
        (r"^impl\s+(?:<[^>]*>\s+)?(\w+)", "impl"),
        (r"^(?:pub(?:\([^)]*\))?\s+)?mod\s+(\w+)", "module"),
    ],
    "go": [
        (r"^func\s+(\w+)\s*[\(<]", "function"),
        (r"^func\s+\(\w+\s+\*?(\w+)\)\s+(\w+)", "method"),
        (r"^type\s+(\w+)\s+struct", "struct"),
        (r"^type\s+(\w+)\s+interface", "interface"),
        (r"^type\s+(\w+)", "type"),
    ],
}


def _extract_regex(source_code: str, language: str, file_path: str) -> tuple[list, list]:
    """Fallback regex-based entity extraction."""
    patterns = _LANG_PATTERNS.get(language, _LANG_PATTERNS["python"])
    entities: list[CandidateEntity] = []
    seen: set[str] = set()

    for line in source_code.splitlines():
        for pattern, kind in patterns:
            m = re.match(
                pattern,
                line.strip() if kind in ("struct", "enum", "trait", "impl", "module") else line,
            )
            if m is None:
                # also try stripped line for all patterns
                m = re.match(pattern, line.strip())
            if m:
                name = m.group(2) if (kind == "method" and m.lastindex and m.lastindex >= 2) else m.group(1)
                key = f"{kind}:{name}"
                if key not in seen:
                    seen.add(key)
                    eid = uuid.uuid4().hex[:12]
                    entities.append(
                        CandidateEntity(
                            entity_id=eid,
                            name=name,
                            properties={"type": kind},
                            source_file=file_path,
                        )
                    )
                break  # one match per line is enough

    return entities, []


class TreeSitterExtractor:
    """Tree-sitter based code extractor stub.

    Full implementation requires the ``tree_sitter`` and language grammar
    packages.  This stub falls back to regex-based extraction so that the
    rest of the NKS pipeline can be exercised without native dependencies.
    """

    SUPPORTED_LANGUAGES: dict = {
        "python": {
            "module": "tree_sitter_python",
            "extensions": [".py"],
            "entity_types": {
                "class_definition": "class",
                "function_definition": "function",
                "decorated_definition": "decorator",
            },
            "relation_types": {
                "inherits": "inherits_from",
                "calls": "calls",
                "imports": "imports",
            },
        },
        "javascript": {
            "module": "tree_sitter_javascript",
            "extensions": [".js", ".mjs", ".cjs"],
            "entity_types": {
                "class_declaration": "class",
                "function_declaration": "function",
                "arrow_function": "function",
            },
            "relation_types": {
                "extends": "extends",
                "calls": "calls",
                "imports": "imports",
            },
        },
        "typescript": {
            "module": "tree_sitter_typescript",
            "extensions": [".ts", ".tsx"],
            "entity_types": {
                "class_declaration": "class",
                "abstract_class_declaration": "class",
                "interface_declaration": "interface",
                "type_alias_declaration": "type",
                "enum_declaration": "enum",
                "namespace_declaration": "namespace",
                "function_declaration": "function",
            },
            "relation_types": {
                "implements": "implements",
                "extends": "extends",
                "has_decorator": "has_decorator",
                "calls": "calls",
                "imports": "imports",
            },
        },
        "rust": {
            "module": "tree_sitter_rust",
            "extensions": [".rs"],
            "entity_types": {
                "struct_item": "struct",
                "enum_item": "enum",
                "trait_item": "trait",
                "function_item": "function",
                "impl_item": "impl",
                "mod_item": "module",
            },
            "relation_types": {
                "implements": "implements",
                "calls": "calls",
                "imports": "imports",
            },
        },
        "go": {
            "module": "tree_sitter_go",
            "extensions": [".go"],
            "entity_types": {
                "function_declaration": "function",
                "method_declaration": "method",
                "type_spec": "type",
            },
            "relation_types": {
                "calls": "calls",
                "imports": "imports",
                "implements": "implements",
            },
        },
        "c": {
            "module": "tree_sitter_c",
            "extensions": [".c", ".h"],
            "entity_types": {"function_definition": "function"},
            "relation_types": {"calls": "calls"},
        },
        "cpp": {
            "module": "tree_sitter_cpp",
            "extensions": [".cpp", ".cc", ".cxx", ".hpp"],
            "entity_types": {
                "class_specifier": "class",
                "function_definition": "function",
            },
            "relation_types": {"calls": "calls", "inherits": "inherits_from"},
        },
    }

    # Language extension map used by _detect_language
    _EXT_MAP: dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cs": "csharp",
        ".java": "java",
        ".rb": "ruby",
    }

    def __init__(self, *, languages: list[str] | None = None) -> None:
        super().__init__()
        self.languages = languages or list(self.SUPPORTED_LANGUAGES.keys())
        self._parsers: dict = {}
        for lang in self.languages:
            if lang in self.SUPPORTED_LANGUAGES:
                mod_name = self.SUPPORTED_LANGUAGES[lang]["module"]
                try:
                    import importlib

                    import tree_sitter

                    mod = importlib.import_module(mod_name)

                    # Handle different versions and special cases (like typescript)
                    if lang == "typescript":
                        if hasattr(mod, "language_typescript"):
                            lang_func = mod.language_typescript
                        elif hasattr(mod, "language"):
                            lang_func = mod.language
                        else:
                            raise AttributeError(f"Module {mod_name} has no language entry point")
                    else:
                        lang_func = getattr(mod, "language", None) or getattr(mod, f"language_{lang}", None)

                    if lang_func is None:
                        _log.debug(f"Could not find language function in {mod_name}")
                        continue

                    # In 0.21+, Language() might take the result of the function call
                    # or the module might already be the language object.
                    try:
                        lang_obj = tree_sitter.Language(lang_func())
                    except (TypeError, ValueError):
                        # Some versions might already expose the language object or require different instantiation
                        lang_obj = lang_func() if callable(lang_func) else lang_func

                    parser = tree_sitter.Parser(lang_obj)
                    self._parsers[lang] = parser
                except (ImportError, AttributeError) as e:
                    _log.debug(f"Could not load tree-sitter parser for {lang}: {e}")
        _log.debug(f"TreeSitterExtractor initialised with parsers: {list(self._parsers.keys())}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Health-check: always True for the stub."""
        return True

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension.

        Returns the language name, defaulting to ``"python"`` for unknown
        extensions.
        """
        suffix = Path(file_path).suffix.lower()
        return self._EXT_MAP.get(suffix, "python")

    def extract_from_file(self, source_code: str, file_path: str, language: str) -> TreeSitterExtractionResult:
        """Extract entities and relations from *source_code*.

        Args:
            source_code: Raw source text to analyse.
            file_path: Logical file path (used as metadata / source_file).
            language: Language identifier (``"python"``, ``"rust"`` …).

        Returns:
            :class:`TreeSitterExtractionResult` with ``entities``,
            ``relations`` and ``metadata`` populated.
        """
        if not source_code or not source_code.strip():
            return TreeSitterExtractionResult(
                file_path=file_path,
                language=language,
                entities=[],
                relations=[],
                metadata={
                    "extraction_method": "none",
                    "language": language,
                    "functions_count": 0,
                },
            )

        parser = self._parsers.get(language)
        if not parser:
            entities, relations = _extract_regex(source_code, language, file_path)
            method = "fallback_regex"
        else:
            entities, relations = [], []
            method = "tree_sitter"
            try:
                tree = parser.parse(bytes(source_code, "utf8"))
                lang_config = self.SUPPORTED_LANGUAGES.get(language, {})
                entity_types = lang_config.get("entity_types", {})

                # Internal map to find entity ID by name within this file
                name_to_id = {}

                def traverse(node: Any) -> None:
                    if node.type in entity_types:
                        kind = entity_types[node.type]
                        name_node = None
                        # Find name node based on language specific structure
                        for child in node.children:
                            if child.type in ("identifier", "type_identifier", "name"):
                                name_node = child
                                break

                        if name_node:
                            name = source_code[name_node.start_byte : name_node.end_byte]
                            eid = uuid.uuid4().hex[:12]
                            entities.append(
                                CandidateEntity(
                                    entity_id=eid,
                                    name=name,
                                    properties={
                                        "type": kind,
                                        "start_line": node.start_point[0] + 1,
                                    },
                                    source_file=file_path,
                                )
                            )
                            name_to_id[name] = eid

                            # Simple Relation Extraction (Python example)
                            if language == "python" and kind == "class":
                                # Look for inheritance
                                for child in node.children:
                                    if child.type == "argument_list":
                                        for arg in child.children:
                                            if arg.type == "identifier":
                                                base_name = source_code[arg.start_byte : arg.end_byte]
                                                relations.append(
                                                    CandidateRelation(
                                                        source_id=eid,
                                                        target_id=base_name,  # Temporary name-based ID
                                                        relation_type="inherits_from",
                                                        source_file=file_path,
                                                    )
                                                )

                    for child in node.children:
                        traverse(child)

                traverse(tree.root_node)
            except (SyntaxError, ValueError, AttributeError) as e:
                _log.error(f"Tree-sitter parse error: {e}")
                entities, relations = _extract_regex(source_code, language, file_path)
                method = "fallback_regex_after_error"

        funcs_count = sum(1 for e in entities if e.properties.get("type") in ("function", "method"))

        return TreeSitterExtractionResult(
            file_path=file_path,
            language=language,
            entities=entities,
            relations=relations,
            metadata={
                "extraction_method": method,
                "language": language,
                "functions_count": funcs_count,
            },
        )

    def extract(
        self, source_code: str, *, language: str = "python", file_path: str = "<string>"
    ) -> TreeSitterExtractionResult:
        """Convenience alias for :meth:`extract_from_file`."""
        return self.extract_from_file(source_code, file_path, language)

    def extract_file(self, file_path: str | Path) -> TreeSitterExtractionResult:
        """Extract entities/relations by reading *file_path* from disk."""
        path = Path(file_path)
        language = self._detect_language(str(file_path))
        try:
            source_code = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return TreeSitterExtractionResult(
                file_path=str(file_path),
                language=language,
                entities=[],
                relations=[],
                metadata={"extraction_method": "fallback_regex", "language": language},
                error=f"Cannot read {file_path}",
            )
        return self.extract_from_file(source_code, str(file_path), language)

    def extract_batch(self, file_paths: list[str | Path]) -> list[TreeSitterExtractionResult]:
        return [self.extract_file(p) for p in file_paths]

    def extract_source(self, source_code: str, language: str = "python") -> TreeSitterExtractionResult:
        return self.extract_from_file(source_code, "<string>", language)
