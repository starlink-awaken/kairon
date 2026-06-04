from __future__ import annotations

import logging

_log = logging.getLogger(__name__)
"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Logos/AGENTS.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Meta Evolve ≡ Module
# 内涵 ≝ {Meta, Evolve}
# 外延 ≝ {e | e ∈ D-Logos ∧ implements(e, MetaEvolve)}
# 功能 ⊢ {Meta_Evolve, Init_Meta, Validate_Evolve}
# =============================================================================

"""
---
Type: Organ
Status: Active
Layer: L3-Logos
Summary: MetaEvolveEngine - analyze code-change semantics to suggest document updates
---

Meta-Evolve Engine (元演化引擎)

Observes diffs between ``before`` and ``after`` source code, classifies the
semantic *type* of change (e.g. API_ADD, PARAM_REMOVE, REFACTOR …), estimates
the documentation impact, and generates prioritised *UpdateSuggestion* objects
that tell a human (or automation) exactly how the accompanying docs should
evolve.

Pipeline::

    Code Change
        ↓  ChangeSemanticsAnalyzer
    ChangeSemantics
        ↓  UpdateSuggestionGenerator
    list[UpdateSuggestion]
        ↓  UpdatePatternLearner   (optional, improves future suggestions)
    UpdatePattern stored

Public API
----------
MetaEvolveEngine.analyze_code_changes(before, after, filepath) → ChangeSemantics
MetaEvolveEngine.generate_update_suggestions(semantics, current_doc) → list[UpdateSuggestion]
MetaEvolveEngine.predict_impact(semantics) → ImpactPrediction
MetaEvolveEngine.learn_update_pattern(code_change, doc_update) → UpdatePattern
MetaEvolveEngine.auto_update(suggestions, approve_callback) → UpdateResult
"""

import ast
import difflib
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ChangeType(Enum):
    """Semantic type of a code change."""

    API_ADD = "api_add"
    API_REMOVE = "api_remove"
    API_RENAME = "api_rename"
    API_SIGNATURE_CHANGE = "api_signature_change"
    API_DEPRECATED = "api_deprecated"
    PARAM_ADD = "param_add"
    PARAM_REMOVE = "param_remove"
    PARAM_RENAME = "param_rename"
    PARAM_TYPE_CHANGE = "param_type_change"
    PARAM_DEFAULT_CHANGE = "param_default_change"
    RETURN_TYPE_CHANGE = "return_type_change"
    BEHAVIOR_CHANGE = "behavior_change"
    REFACTOR = "refactor"
    BUGFIX = "bugfix"
    PERFORMANCE = "performance"
    DOC_UPDATE = "doc_update"


class ImpactLevel(Enum):
    """Documentation impact level."""

    BREAKING = "breaking"  # API removed / signature broken
    MAJOR = "major"  # New API / default behaviour changed
    MINOR = "minor"  # Optional param added / minor behaviour tweak
    PATCH = "patch"  # Bug-fix / doc-only change


class UpdateType(Enum):
    """Type of documentation update required."""

    ADD_SECTION = "add_section"
    UPDATE_SECTION = "update_section"
    REMOVE_SECTION = "remove_section"
    UPDATE_EXAMPLE = "update_example"
    UPDATE_PARAM = "update_param"
    UPDATE_RETURN = "update_return"
    ADD_DEPRECATED_NOTE = "add_deprecated_note"
    NO_UPDATE_NEEDED = "no_update_needed"


# ---------------------------------------------------------------------------
# Data-classes
# ---------------------------------------------------------------------------


@dataclass
class ChangeSemantics:
    """Result of analysing a code change."""

    change_type: ChangeType
    impact_level: ImpactLevel
    confidence: float  # 0.0 – 1.0
    changes: list[dict[str, Any]]
    affected_entities: list[str]
    description: str
    filepath: str = ""
    breaking: bool = False


@dataclass
class UpdateSuggestion:
    """A single document-update recommendation."""

    id: str = field(default_factory=lambda: f"SUGG-{uuid.uuid4().hex[:8]}")
    update_type: UpdateType = UpdateType.NO_UPDATE_NEEDED
    section: str = ""
    description: str = ""
    content_hint: str = ""
    priority: int = 5  # 1 (highest) – 10 (lowest)
    auto_applicable: bool = False
    rationale: str = ""


@dataclass
class UpdatePattern:
    """A learned mapping from ChangeType → UpdateType."""

    id: str = field(default_factory=lambda: f"PAT-{uuid.uuid4().hex[:8]}")
    change_type: ChangeType = ChangeType.REFACTOR
    update_type: UpdateType = UpdateType.NO_UPDATE_NEEDED
    confidence: float = 0.5
    occurrences: int = 1
    last_seen: float = field(default_factory=time.time)


@dataclass
class ImpactPrediction:
    """Predicted downstream impact of a change."""

    estimated_effort: str = "low"  # "low" | "medium" | "high"
    priority: str = "normal"  # "low" | "normal" | "high" | "critical"
    affected_doc_sections: list[str] = field(default_factory=list)
    review_required: bool = False
    notes: str = ""


@dataclass
class CodeChange:
    """A raw before/after code change."""

    before: str
    after: str
    filepath: str = ""
    commit_sha: str = ""
    author: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class DocumentUpdate:
    """Record of a documentation update that was actually applied."""

    id: str = field(default_factory=lambda: f"DU-{uuid.uuid4().hex[:8]}")
    doc_path: str = ""
    before: str = ""
    after: str = ""
    update_type: UpdateType = UpdateType.UPDATE_SECTION
    applied_at: float = field(default_factory=time.time)
    author: str = ""


@dataclass
class UpdateResult:
    """Aggregate result after running auto_update."""

    applied: list[UpdateSuggestion] = field(default_factory=list)
    rejected: list[UpdateSuggestion] = field(default_factory=list)
    pending: list[UpdateSuggestion] = field(default_factory=list)
    success: bool = True
    message: str = ""


# ---------------------------------------------------------------------------
# ChangeSemanticsAnalyzer
# ---------------------------------------------------------------------------


class ChangeSemanticsAnalyzer:
    """
    Analyses a before/after source diff and classifies the *semantic* meaning
    of the change (rather than just the textual diff).
    """

    # Impact map: ChangeType → (ImpactLevel, is_breaking)
    _IMPACT_MAP: dict[ChangeType, tuple[ImpactLevel, bool]] = {
        ChangeType.API_REMOVE: (ImpactLevel.BREAKING, True),
        ChangeType.API_RENAME: (ImpactLevel.BREAKING, True),
        ChangeType.PARAM_REMOVE: (ImpactLevel.BREAKING, True),
        ChangeType.RETURN_TYPE_CHANGE: (ImpactLevel.BREAKING, True),
        ChangeType.API_SIGNATURE_CHANGE: (ImpactLevel.MAJOR, False),
        ChangeType.API_ADD: (ImpactLevel.MAJOR, False),
        ChangeType.API_DEPRECATED: (ImpactLevel.MAJOR, False),
        ChangeType.PARAM_ADD: (ImpactLevel.MINOR, False),
        ChangeType.PARAM_TYPE_CHANGE: (ImpactLevel.MINOR, False),
        ChangeType.PARAM_DEFAULT_CHANGE: (ImpactLevel.MINOR, False),
        ChangeType.PARAM_RENAME: (ImpactLevel.MINOR, False),
        ChangeType.BEHAVIOR_CHANGE: (ImpactLevel.MINOR, False),
        ChangeType.REFACTOR: (ImpactLevel.PATCH, False),
        ChangeType.BUGFIX: (ImpactLevel.PATCH, False),
        ChangeType.PERFORMANCE: (ImpactLevel.PATCH, False),
        ChangeType.DOC_UPDATE: (ImpactLevel.PATCH, False),
    }

    # Confidence map
    _CONFIDENCE_MAP: dict[ChangeType, float] = {
        ChangeType.API_ADD: 0.95,
        ChangeType.API_REMOVE: 0.95,
        ChangeType.PARAM_ADD: 0.90,
        ChangeType.PARAM_REMOVE: 0.90,
        ChangeType.API_SIGNATURE_CHANGE: 0.85,
        ChangeType.RETURN_TYPE_CHANGE: 0.85,
        ChangeType.REFACTOR: 0.70,
        ChangeType.BEHAVIOR_CHANGE: 0.60,
        ChangeType.BUGFIX: 0.65,
        ChangeType.DOC_UPDATE: 0.95,
        ChangeType.PERFORMANCE: 0.60,
    }

    def analyze(
        self,
        before: str,
        after: str,
        filepath: str = "",
    ) -> ChangeSemantics:
        """Full analysis pipeline: classify → assess → build ChangeSemantics."""
        change_type, raw_changes = self._classify_change(before, after)
        impact, breaking = self._assess_impact(change_type, raw_changes)
        confidence = self._calculate_confidence(change_type, raw_changes)
        affected = self._extract_affected_entities(raw_changes)
        description = self._build_description(change_type, raw_changes)

        return ChangeSemantics(
            change_type=change_type,
            impact_level=impact,
            confidence=confidence,
            changes=raw_changes,
            affected_entities=affected,
            description=description,
            filepath=filepath,
            breaking=breaking,
        )

    # ------------------------------------------------------------------
    # "Private" helpers that tests call directly
    # ------------------------------------------------------------------

    def _classify_change(self, before: str, after: str) -> tuple[ChangeType, list[dict[str, Any]]]:
        """Classify the dominant change type and enumerate individual changes."""
        before_funcs = self._extract_all_functions(before)
        after_funcs = self._extract_all_functions(after)
        before_classes = self._extract_all_classes(before)
        after_classes = self._extract_all_classes(after)

        changes: list[dict[str, Any]] = []

        # ---- API add / remove ----
        added_funcs = set(after_funcs) - set(before_funcs)
        removed_funcs = set(before_funcs) - set(after_funcs)

        for name in added_funcs:
            changes.append({"type": "add", "entity": "function", "name": name})
        for name in removed_funcs:
            changes.append({"type": "remove", "entity": "function", "name": name})

        added_classes = set(after_classes) - set(before_classes)
        removed_classes = set(before_classes) - set(after_classes)
        for name in added_classes:
            changes.append({"type": "add", "entity": "class", "name": name})
        for name in removed_classes:
            changes.append({"type": "remove", "entity": "class", "name": name})

        # ---- Signature changes on existing functions ----
        for name in set(before_funcs) & set(after_funcs):
            b_sig = self._extract_function_signature(before, name)
            a_sig = self._extract_function_signature(after, name)
            if b_sig and a_sig and b_sig != a_sig:
                b_params = self._parse_params(b_sig)
                a_params = self._parse_params(a_sig)
                if len(a_params) > len(b_params):
                    changes.append(
                        {
                            "type": "param_add",
                            "entity": "function",
                            "name": name,
                            "added": list(set(a_params) - set(b_params)),
                        }
                    )
                elif len(a_params) < len(b_params):
                    changes.append(
                        {
                            "type": "param_remove",
                            "entity": "function",
                            "name": name,
                            "removed": list(set(b_params) - set(a_params)),
                        }
                    )
                else:
                    changes.append({"type": "signature_change", "entity": "function", "name": name})

        # ---- Pure doc-string change ----
        if not changes and before.strip() != after.strip():
            changes.append({"type": "text_change", "entity": "content", "name": ""})

        # ---- Classify dominant type ----
        return self._dominant_change_type(changes, before, after), changes

    def _dominant_change_type(
        self,
        changes: list[dict[str, Any]],
        before: str,
        after: str,
    ) -> ChangeType:
        if not changes:
            return ChangeType.REFACTOR

        types = [c["type"] for c in changes]

        if "remove" in types and not before.strip():
            return ChangeType.API_REMOVE
        if "add" in types and not before.strip():
            return ChangeType.API_ADD
        if "remove" in types and "add" not in types:
            return ChangeType.API_REMOVE
        if "add" in types and "remove" not in types:
            return ChangeType.API_ADD
        if "param_add" in types and "param_remove" not in types:
            return ChangeType.PARAM_ADD
        if "param_remove" in types:
            return ChangeType.PARAM_REMOVE
        if "signature_change" in types:
            return ChangeType.API_SIGNATURE_CHANGE

        # Heuristic: if only internal lines changed → refactor / behaviour
        diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm=""))
        added_lines = [ln for ln in diff if ln.startswith("+") and not ln.startswith("+++")]
        removed_lines = [ln for ln in diff if ln.startswith("-") and not ln.startswith("---")]
        if len(added_lines) == len(removed_lines):
            return ChangeType.REFACTOR
        return ChangeType.BEHAVIOR_CHANGE

    # ------------------------------------------------------------------

    def _extract_function_signature(self, code: str, func_name: str) -> str | None:
        """Return the ``def func_name(...)`` signature line, or None."""
        pattern = re.compile(
            rf"^def\s+{re.escape(func_name)}\s*\([^)]*\)(?:\s*->\s*[^:]+)?:",
            re.MULTILINE,
        )
        m = pattern.search(code)
        return m.group(0).rstrip(":").strip() if m else None

    def _parse_params(self, signature: str) -> list[str]:
        """Extract parameter names from a signature string."""
        m = re.search(r"\(([^)]*)\)", signature)
        if not m:
            return []
        raw = m.group(1)
        params = []
        for p in raw.split(","):
            p = p.strip().split(":")[0].split("=")[0].strip().lstrip("*")
            if p and p not in ("self", "cls"):
                params.append(p)
        return params

    def _extract_affected_entities(self, changes: list[dict[str, Any]]) -> list[str]:
        """Return ``["function:name", "class:Name", …]`` for non-empty changes."""
        seen: list[str] = []
        for c in changes:
            entity = c.get("entity", "")
            name = c.get("name", "")
            if entity and name:
                key = f"{entity}:{name}"
                if key not in seen:
                    seen.append(key)
        return seen

    def _assess_impact(
        self,
        change_type: ChangeType,
        changes: list[dict[str, Any]],
    ) -> tuple[ImpactLevel, bool]:
        """Return (ImpactLevel, is_breaking)."""
        return self._IMPACT_MAP.get(change_type, (ImpactLevel.PATCH, False))

    def _calculate_confidence(
        self,
        change_type: ChangeType,
        changes: list[dict[str, Any]],
    ) -> float:
        """Return classifier confidence in [0, 1]."""
        base = self._CONFIDENCE_MAP.get(change_type, 0.5)
        # Boost confidence when we have many signal-rich changes
        if len(changes) >= 3:
            base = min(1.0, base + 0.05)
        return round(base, 4)

    # ------------------------------------------------------------------
    # AST helpers
    # ------------------------------------------------------------------

    def _extract_all_functions(self, code: str) -> list[str]:
        try:
            tree = ast.parse(code)
            return [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        except SyntaxError:
            return re.findall(r"^def (\w+)\s*\(", code, re.MULTILINE)

    def _extract_all_classes(self, code: str) -> list[str]:
        try:
            tree = ast.parse(code)
            return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        except SyntaxError:
            return re.findall(r"^class (\w+)\s*[:(]", code, re.MULTILINE)

    def _build_description(self, change_type: ChangeType, changes: list[dict[str, Any]]) -> str:
        names = [c.get("name", "") for c in changes if c.get("name")]
        entity_str = ", ".join(names[:3]) + ("…" if len(names) > 3 else "")
        return f"{change_type.value}: {entity_str}" if entity_str else change_type.value


# ---------------------------------------------------------------------------
# UpdateSuggestionGenerator
# ---------------------------------------------------------------------------


class UpdateSuggestionGenerator:
    """
    Converts a *ChangeSemantics* into a ranked list of *UpdateSuggestion*
    objects telling the author what to update in the documentation.
    """

    # Mapping change → (update_type, priority, auto_applicable)
    _RULES: dict[ChangeType, tuple[UpdateType, int, bool]] = {
        ChangeType.API_ADD: (UpdateType.ADD_SECTION, 2, False),
        ChangeType.API_REMOVE: (UpdateType.REMOVE_SECTION, 1, False),
        ChangeType.API_RENAME: (UpdateType.UPDATE_SECTION, 1, False),
        ChangeType.API_SIGNATURE_CHANGE: (UpdateType.UPDATE_SECTION, 2, True),
        ChangeType.API_DEPRECATED: (UpdateType.ADD_DEPRECATED_NOTE, 2, True),
        ChangeType.PARAM_ADD: (UpdateType.UPDATE_PARAM, 3, True),
        ChangeType.PARAM_REMOVE: (UpdateType.UPDATE_PARAM, 2, True),
        ChangeType.PARAM_RENAME: (UpdateType.UPDATE_PARAM, 3, True),
        ChangeType.PARAM_TYPE_CHANGE: (UpdateType.UPDATE_PARAM, 3, True),
        ChangeType.PARAM_DEFAULT_CHANGE: (UpdateType.UPDATE_PARAM, 4, True),
        ChangeType.RETURN_TYPE_CHANGE: (UpdateType.UPDATE_RETURN, 2, True),
        ChangeType.BEHAVIOR_CHANGE: (UpdateType.UPDATE_SECTION, 3, False),
        ChangeType.REFACTOR: (UpdateType.NO_UPDATE_NEEDED, 9, True),
        ChangeType.BUGFIX: (UpdateType.UPDATE_SECTION, 5, False),
        ChangeType.PERFORMANCE: (UpdateType.UPDATE_SECTION, 6, False),
        ChangeType.DOC_UPDATE: (UpdateType.NO_UPDATE_NEEDED, 10, True),
    }

    def generate(
        self,
        semantics: ChangeSemantics,
        current_doc: str,
    ) -> list[UpdateSuggestion]:
        """Generate a list of update suggestions for *semantics*."""
        update_type, priority, auto = self._RULES.get(
            semantics.change_type,
            (UpdateType.UPDATE_SECTION, 5, False),
        )

        suggestions: list[UpdateSuggestion] = []

        for entity in semantics.affected_entities or [""]:
            section = entity.split(":")[-1] if ":" in entity else entity
            sugg = UpdateSuggestion(
                update_type=update_type,
                section=section,
                description=self._describe(semantics, entity),
                content_hint=self._content_hint(semantics, current_doc, entity),
                priority=priority,
                auto_applicable=auto,
                rationale=f"Detected {semantics.change_type.value} with confidence {semantics.confidence:.0%}",
            )
            suggestions.append(sugg)

        if not suggestions:
            # At least one generic suggestion
            suggestions.append(
                UpdateSuggestion(
                    update_type=update_type,
                    section="",
                    description=semantics.description,
                    priority=priority,
                    auto_applicable=auto,
                )
            )

        return suggestions

    # ------------------------------------------------------------------

    def _describe(self, semantics: ChangeSemantics, entity: str) -> str:
        name = entity.split(":")[-1] if ":" in entity else entity
        ct = semantics.change_type.value
        return f"{ct} detected on '{name}'" if name else ct

    def _content_hint(self, semantics: ChangeSemantics, current_doc: str, entity: str) -> str:
        name = entity.split(":")[-1] if ":" in entity else entity
        if semantics.change_type == ChangeType.API_ADD:
            return f"Add documentation section for `{name}`."
        if semantics.change_type == ChangeType.API_REMOVE:
            return f"Remove or mark as deprecated documentation for `{name}`."
        if semantics.change_type in (ChangeType.PARAM_ADD, ChangeType.PARAM_REMOVE):
            return f"Update parameters section for `{name}`."
        return ""


# ---------------------------------------------------------------------------
# UpdatePatternLearner
# ---------------------------------------------------------------------------


class UpdatePatternLearner:
    """
    Learns from observed (CodeChange, DocumentUpdate) pairs and improves
    future suggestion accuracy by building a pattern library.
    """

    def __init__(self) -> None:
        super().__init__()
        self._patterns: list[UpdatePattern] = []

    def learn(self, code_change: CodeChange, doc_update: DocumentUpdate) -> UpdatePattern:
        """Record a new pattern (or update confidence of an existing one)."""
        # Derive ChangeType from code_change content
        analyzer = ChangeSemanticsAnalyzer()
        semantics = analyzer.analyze(code_change.before, code_change.after, code_change.filepath)

        existing = next(
            (
                p
                for p in self._patterns
                if p.change_type == semantics.change_type and p.update_type == doc_update.update_type
            ),
            None,
        )
        if existing:
            existing.occurrences += 1
            existing.confidence = min(1.0, existing.confidence + 0.02)
            existing.last_seen = time.time()
            return existing

        pattern = UpdatePattern(
            change_type=semantics.change_type,
            update_type=doc_update.update_type,
            confidence=0.6,
        )
        self._patterns.append(pattern)
        return pattern

    def best_pattern(self, change_type: ChangeType) -> UpdatePattern | None:
        """Return the highest-confidence pattern for *change_type*."""
        candidates = [p for p in self._patterns if p.change_type == change_type]
        return max(candidates, key=lambda p: p.confidence) if candidates else None

    @property
    def patterns(self) -> list[UpdatePattern]:
        return list(self._patterns)


# ---------------------------------------------------------------------------
# MetaEvolveEngine  (top-level façade)
# ---------------------------------------------------------------------------


class MetaEvolveEngine:
    """
    ---
    Type: Organ
    Status: Active
    Layer: L3-Logos
    Summary: High-level façade that coordinates change analysis and doc evolution
    ---

    MetaEvolveEngine ties together ChangeSemanticsAnalyzer, UpdateSuggestionGenerator,
    UpdatePatternLearner, and auto-update to provide a single entry point for
    evolving documentation in response to code changes.
    """

    def __init__(self) -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)
        self._analyzer = ChangeSemanticsAnalyzer()
        self._generator = UpdateSuggestionGenerator()
        self._learner = UpdatePatternLearner()

    def health_check(self) -> dict:
        """Return operational health metrics."""
        return {
            "status": "healthy",
            "organ": "MetaEvolveEngine",
            "plugins_loaded": len(self._learner.get_patterns()) if hasattr(self._learner, "get_patterns") else 0,
        }

    # ------------------------------------------------------------------
    # Primary public API
    # ------------------------------------------------------------------

    def analyze_code_changes(
        self,
        before_code: str,
        after_code: str,
        filepath: str = "",
    ) -> ChangeSemantics:
        """Analyse a before/after diff and return semantic change metadata."""
        _log.debug("MetaEvolveEngine.analyze_code_changes filepath=%r", filepath)
        return self._analyzer.analyze(before_code, after_code, filepath)

    def generate_update_suggestions(
        self,
        change_semantics: ChangeSemantics,
        current_doc: str,
    ) -> list[UpdateSuggestion]:
        """Generate prioritised doc-update suggestions for the given semantics."""
        return self._generator.generate(change_semantics, current_doc)

    def learn_update_pattern(
        self,
        code_change: CodeChange,
        doc_update: DocumentUpdate,
    ) -> UpdatePattern:
        """Record an observed (code change → doc update) pair."""
        return self._learner.learn(code_change, doc_update)

    def predict_impact(
        self,
        change_semantics: ChangeSemantics,
    ) -> ImpactPrediction:
        """Predict the downstream impact on documentation effort."""
        level = change_semantics.impact_level
        breaking = change_semantics.breaking

        effort_map = {
            ImpactLevel.BREAKING: "high",
            ImpactLevel.MAJOR: "high",
            ImpactLevel.MINOR: "medium",
            ImpactLevel.PATCH: "low",
        }
        priority_map = {
            ImpactLevel.BREAKING: "critical",
            ImpactLevel.MAJOR: "high",
            ImpactLevel.MINOR: "normal",
            ImpactLevel.PATCH: "low",
        }

        affected_sections = [e.split(":")[-1] for e in change_semantics.affected_entities]

        return ImpactPrediction(
            estimated_effort=effort_map.get(level, "medium"),
            priority=priority_map.get(level, "normal"),
            affected_doc_sections=affected_sections,
            review_required=breaking or level in (ImpactLevel.BREAKING, ImpactLevel.MAJOR),
            notes=change_semantics.description,
        )

    def breakdown_vision_to_symphony(self, vision_intent: str, domain: str = "general") -> list[dict]:
        """将顶层愿景拆解为 Symphony Protocol 任务流 (Anchoring, Scaffolding, Implementation, Polishing)。

        Args:
            vision_intent: 愿景描述
            domain: 业务领域

        Returns:
            子任务字典列表
        """
        _log.info(f"🧬 [MetaEvolve] 正在执行分形拆解: {vision_intent[:50]}...")

        # 核心 Symphony 模板
        tasks = [
            {
                "intent": f"[Anchoring] {domain} 愿景锚定: {vision_intent}",
                "caps": ["architect", "theory.modeling"],
                "eu": 0.5,
                "phase": 1,
                "deps": [],
            },
            {
                "intent": f"[Scaffolding] {domain} 骨架生成: {vision_intent}",
                "caps": ["architect", "interface.design"],
                "eu": 0.8,
                "phase": 2,
                "deps": [0],
            },
            {
                "intent": f"[Implementation] {domain} 核心实现: {vision_intent}",
                "caps": ["code.implementation", "engineering"],
                "eu": 2.5,
                "phase": 3,
                "deps": [1],
            },
            {
                "intent": f"[Polishing] {domain} 验收打磨: {vision_intent}",
                "caps": ["qa", "documentation", "refinement"],
                "eu": 0.7,
                "phase": 4,
                "deps": [2],
            },
        ]

        return tasks

    def auto_update(
        self,
        suggestions: list[UpdateSuggestion],
        approve_callback: Callable[[UpdateSuggestion], bool],
    ) -> UpdateResult:
        """
        Semi-automatically apply suggestions that pass *approve_callback*.

        ``approve_callback(suggestion) → bool``:  return True to apply,
        False to reject, raise to leave as pending.
        """
        result = UpdateResult()
        for sugg in suggestions:
            try:
                approved = approve_callback(sugg)
                if approved:
                    result.applied.append(sugg)
                else:
                    result.rejected.append(sugg)
            except Exception as exc:
                _log.warning("auto_update: suggestion %s left pending: %s", sugg.id, exc)
                result.pending.append(sugg)

        result.success = True
        result.message = (
            f"Applied {len(result.applied)}, rejected {len(result.rejected)}, pending {len(result.pending)}"
        )
        return result
