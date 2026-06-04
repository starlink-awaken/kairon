from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Governance ≡ Module
# 内涵 ≝ {Governance}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Governance)}
# 功能 ⊢ {Init_Governance, Execute_Governance, Validate_Governance}
# =============================================================================

# ---
# domain: D-Logos
# layer: organ
# status: active
# version: 10.5.0
# owner: '@Architect'
# authority: organs/D-Logos/AGENTS.md
# ---
"""AlignmentEngine governance helpers."""


import hashlib as _hashlib
import json
import re as _re
from pathlib import Path

from engine.alignment_models import (  # type: ignore[import-not-found]
    AlignmentCategory,
    AlignmentIssue,
    AlignmentSeverity,
)


class IndexAuditor:
    """Structural governance contract: docs index ↔ filesystem reconciliation."""

    _LINK_RE = _re.compile(r"\[[^\]]*\]\(([^)#?]+)\)")

    def audit(self, docs_root: Path, index_path: Path) -> list[AlignmentIssue]:
        """Return a list of :class:`AlignmentIssue` for orphans and ghosts."""
        issues: list[AlignmentIssue] = []
        all_files: set[Path] = set()

        for md in docs_root.rglob("*.md"):
            if md.resolve() != index_path.resolve():
                all_files.add(md.resolve())

        referenced: set[Path] = set()
        if index_path.exists():
            content = index_path.read_text(encoding="utf-8", errors="replace")
            for match in self._LINK_RE.finditer(content):
                raw_target = match.group(1).strip()
                if raw_target.startswith(("http://", "https://", "mailto:")):
                    continue
                candidate = (index_path.parent / raw_target).resolve()
                referenced.add(candidate)

        issue_idx = 0

        for ref_path in sorted(referenced):
            if not ref_path.exists():
                issues.append(
                    AlignmentIssue(
                        id=f"GOV-IDX-{issue_idx:04d}",
                        category=AlignmentCategory.INDEX_GHOST,
                        severity=AlignmentSeverity.HIGH,
                        doc_source=index_path,
                        description=f"Index references non-existent file: {ref_path}",
                        suggestion="Remove or fix the broken link in the index.",
                    )
                )
                issue_idx += 1

        for file_path in sorted(all_files):
            if file_path not in referenced:
                issues.append(
                    AlignmentIssue(
                        id=f"GOV-IDX-{issue_idx:04d}",
                        category=AlignmentCategory.INDEX_ORPHAN,
                        severity=AlignmentSeverity.MEDIUM,
                        doc_source=file_path,
                        description=f"File not referenced in index: {file_path.relative_to(docs_root.resolve())}",
                        suggestion="Add a link to this file in the docs index (README.md).",
                    )
                )
                issue_idx += 1

        return issues


class DocFreshnessScanner:
    """Hash-based State doc freshness detection."""

    _UPDATED_RE = _re.compile(r"^Updated:.*$", _re.MULTILINE)
    _TYPE_RE = _re.compile(r"^Type:\s*(.+)$", _re.MULTILINE)

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir
        self._hash_cache: dict[str, str] = {}

    def compute_hash(self, path: Path) -> str:
        """Return SHA-256 hex of file content, excluding the ``Updated:`` line."""
        content = path.read_text(encoding="utf-8", errors="replace")
        normalised = self._UPDATED_RE.sub("Updated: <stripped>", content)
        return _hashlib.sha256(normalised.encode("utf-8")).hexdigest()

    def scan(
        self,
        docs_root: Path,
        cache_path: Path | None = None,
    ) -> list[AlignmentIssue]:
        """Compare current hashes against the cache; flag STALE docs."""
        issues: list[AlignmentIssue] = []
        effective_cache = cache_path or (self._state_dir / "freshness_cache.json" if self._state_dir else None)
        old_cache: dict[str, str] = {}

        if effective_cache and effective_cache.exists():
            try:
                old_cache = json.loads(effective_cache.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                old_cache = {}

        new_cache: dict[str, str] = {}
        issue_idx = 0

        for md_file in sorted(docs_root.rglob("*.md")):
            path_key = str(md_file.resolve())
            current_hash = self.compute_hash(md_file)
            new_cache[path_key] = current_hash

            if path_key not in old_cache or old_cache[path_key] == current_hash:
                continue

            content = md_file.read_text(encoding="utf-8", errors="replace")
            updated_match = _re.search(r"^Updated:\s*(.+)$", content, _re.MULTILINE)
            if updated_match is None:
                updated_date = None
            else:
                updated_date = updated_match.group(1).strip().strip("'\"")

            type_match = self._TYPE_RE.search(content)
            doc_type = type_match.group(1).strip().strip("'\"") if type_match else "Unknown"
            severity = AlignmentSeverity.HIGH if doc_type in ("State", "STATE") else AlignmentSeverity.MEDIUM

            issues.append(
                AlignmentIssue(
                    id=f"GOV-FRESH-{issue_idx:04d}",
                    category=AlignmentCategory.DOC_STALE,
                    severity=severity,
                    doc_source=md_file,
                    description=(
                        f"Content hash changed but Updated field ('{updated_date}') was not bumped. Doc may be stale."
                    ),
                    suggestion=(
                        "Run `DocGenerator.bump_updated()` or manually update "
                        "the 'Updated:' frontmatter field to today's date."
                    ),
                )
            )
            issue_idx += 1

        if effective_cache:
            try:
                effective_cache.parent.mkdir(parents=True, exist_ok=True)
                effective_cache.write_text(
                    json.dumps(new_cache, indent=2),
                    encoding="utf-8",
                )
            except OSError:
                pass

        self._hash_cache = new_cache
        return issues


__all__ = ["IndexAuditor", "DocFreshnessScanner"]
