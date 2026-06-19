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
# ---
# domain: D-Logos
# layer: organ
# status: active
# ---

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Context Compiler ≡ Compiler
# 内涵 ≝ {Context, Compiler}
# 外延 ≝ {e | e ∈ D-Logos ∧ implements(e, ContextCompiler)}
# 功能 ⊢ {Context_Compiler, Init_Context, Validate_Compiler, Compile_Contexts}
# =============================================================================

"""Context compiler — validates and compiles AGENTS.md files.

AGENTS.md files form the directory self-management system:
each directory gets an AGENTS.md that tells AI agents what to do there.

Usage:
    python3 -m organs.D_Logos.organs.context_compiler --validate [path]
    python3 -m organs.D_Logos.organs.context_compiler --find-missing
    python3 -m organs.D_Logos.organs.context_compiler --check-all
    python3 -m organs.D_Logos.organs.context_compiler --compile [root]

The Context DocType (per AGENTS.md Mechanism 1) is handled here:
    DocType.CONTEXT — for AGENTS.md files, compiled from child directories.
"""

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = [
    "## 🗺️ 位置与职责",
    "## 📁 路由表",
    "## ✍️ 操作规范",
    "## 🔗 依赖关系",
    "## ✅ 验证与测试",
    "## 📚 文档位置",
    "## 🔄 如何更新本文件",
]

REQUIRED_FRONTMATTER_KEYS = ["Type", "Layer", "Domain", "Status", "Updated"]

VALID_TYPES = {"RootNavigator", "DomainNavigator", "ModuleNavigator", "LeafNavigator"}
VALID_LAYERS = {"L0", "L1", "L2", "L3"}

FIRST_RUNTIME_SLICE_MARKERS = (
    "Multimodal Surface Mesh × Continuity Plane",
    "First runtime slice",
)
FIRST_RUNTIME_SLICE_VOCAB_PATTERNS = {
    "truth object": re.compile(r"\btruth object(?:s)?\b", re.IGNORECASE),
    "owner domain": re.compile(r"\bowner domain\b", re.IGNORECASE),
    "blast radius": re.compile(r"\bblast radius\b", re.IGNORECASE),
}
FIRST_RUNTIME_SLICE_STRUCTURED_VALUE_PATTERNS = {
    "truth object": re.compile(r"\btruth object(?:s)?\s*[:：]\s*\S", re.IGNORECASE),
    "owner domain": re.compile(r"\bowner domain\s*[:：]\s*\S", re.IGNORECASE),
    "blast radius": re.compile(r"\bblast radius\s*[:：]\s*\S", re.IGNORECASE),
}
FIRST_RUNTIME_SLICE_SEAM_RULES = (
    "surface != truth",
    "ingress != ownership",
    "continuity != silent fallback",
)
ARCHITECTURE_PATH_VALIDATION_DOCS = {
    "41-hive-continuum-contract-map.md",
    "42-semantic-physical-mapping-matrix.md",
}
REPO_ROOT_REFERENCE_PREFIXES = {
    "AGENTS",
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "README.md",
    "docs/archive/root_cleanup_20260428/SOUL.md",
    "api",
    "bin",
    "config",
    "conductor",
    "data",
    "demos",
    "docs",
    "knowledge",
    "nucleus",
    "organs",
    "tests",
    "ui",
}
MARKDOWN_LINK_REFERENCE_PATTERN = re.compile(r"\[[^\]]+]\(([^)\s]+\.md(?:#[^)]+)?)\)")
MARKDOWN_CODE_REFERENCE_PATTERN = re.compile(r"`([^`\n]+\.md)`")

# Directories that SHOULD have AGENTS.md (top-level domains and key modules)
REQUIRED_AGENTS_DIRS = [
    ".",  # root
    "nucleus",
    "organs",
    "bos_daemon",
    "bin",
    "docs",
    "tests",
    "conductor",
    "config",
    "demos",
    # Nucleus sub-modules
    "nucleus/Z-Microkernel",
    "nucleus/Z-Core",
    "nucleus/Z-Spore",
    # Organ modules
    "organs/D-Gateway",
    "organs/D-Memory",
    "organs/D-Logos",
    "organs/D-Execution",
    "organs/D-Immunity",
    "organs/D-Genesis",
    "organs/D-Economy",
    "organs/D-Excretion",
    # Key tool dirs
    "bin/devtools",
    "bin/devtools/governance",
    # Key doc dirs
    "docs/50-reference",
    "docs/90-internal",
    "tests/unit",
    # Deep implementation layers (L3)
    "organs/D-Execution/organs",
    "organs/D-Memory/organs",
    "nucleus/Z-Core/L0-Genome",
    "nucleus/Z-Core/L1-Intent",
    "nucleus/Z-Core/L2-Law",
]

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """A single validation finding for an AGENTS.md file."""

    path: Path
    severity: str  # "error" | "warning"
    message: str


@dataclass
class AgentContextFile:
    """Parsed representation of an AGENTS.md file."""

    path: Path
    frontmatter: dict[str, Any]
    sections: list[str]
    content_hash: str


@dataclass
class ValidationResult:
    """Aggregated validation outcome for one AGENTS.md file."""

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_agents_file(path: Path) -> AgentContextFile | None:
    """Parse an AGENTS.md file into structured data.

    Returns ``None`` if the file does not exist.
    """
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    # Parse YAML frontmatter (simple key: value, no nested structures)
    frontmatter: dict[str, Any] = {}
    sections: list[str] = []
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            fm_text = content[3:end].strip()
            for line in fm_text.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    frontmatter[k.strip()] = v.strip()

    # Extract all level-2 section headings
    sections = re.findall(r"^##\s+.+", content, re.MULTILINE)

    return AgentContextFile(
        path=path,
        frontmatter=frontmatter,
        sections=sections,
        content_hash=content_hash,
    )


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validate_agents_file(path: Path) -> ValidationResult:
    """Validate a single AGENTS.md file against the schema.

    Checks:
    - File existence
    - Required frontmatter keys
    - Valid ``Type`` and ``Layer`` values
    - All required Chinese-headed sections are present
    """
    result = ValidationResult()

    if not path.exists():
        result.issues.append(ValidationIssue(path, "error", "AGENTS.md does not exist"))
        return result

    ctx = parse_agents_file(path)
    if ctx is None:
        result.issues.append(ValidationIssue(path, "error", "Failed to parse AGENTS.md"))
        return result
    content = path.read_text(encoding="utf-8")

    # ── Frontmatter keys ───────────────────────────────────────────────────
    for key in REQUIRED_FRONTMATTER_KEYS:
        if key not in ctx.frontmatter:
            result.issues.append(ValidationIssue(path, "error", f"Missing frontmatter key: {key}"))

    # ── Type validity ──────────────────────────────────────────────────────
    if "Type" in ctx.frontmatter and ctx.frontmatter["Type"] not in VALID_TYPES:
        result.issues.append(
            ValidationIssue(
                path,
                "warning",
                f"Unknown Type: {ctx.frontmatter['Type']} (expected one of: {VALID_TYPES})",
            )
        )

    # ── Layer validity ─────────────────────────────────────────────────────
    if "Layer" in ctx.frontmatter and ctx.frontmatter["Layer"] not in VALID_LAYERS:
        result.issues.append(
            ValidationIssue(
                path,
                "error",
                f"Invalid Layer: {ctx.frontmatter['Layer']} (expected one of: {VALID_LAYERS})",
            )
        )

    # ── Required sections ──────────────────────────────────────────────────
    section_texts = [s.strip() for s in ctx.sections]
    for required in REQUIRED_SECTIONS:
        found = any(required.rstrip() in s for s in section_texts)
        if not found:
            result.issues.append(ValidationIssue(path, "error", f"Missing required section: {required}"))

    result.issues.extend(_validate_architecture_path_references(path, ctx, content))

    if _mentions_first_runtime_slice(content):
        for label, pattern in FIRST_RUNTIME_SLICE_VOCAB_PATTERNS.items():
            if not pattern.search(content):
                result.issues.append(
                    ValidationIssue(
                        path,
                        "warning",
                        f"First runtime slice vocabulary missing explicit {label}",
                    )
                )

        lowered = content.lower()
        if not any(rule in lowered for rule in FIRST_RUNTIME_SLICE_SEAM_RULES):
            result.issues.append(
                ValidationIssue(
                    path,
                    "warning",
                    "First runtime slice vocabulary missing explicit seam rule "
                    "(`surface != truth`, `ingress != ownership`, or "
                    "`continuity != silent fallback`)",
                )
            )

        if _is_first_runtime_slice_planning_doc(path):
            slice_block = _first_runtime_slice_block(content)
            for label, pattern in FIRST_RUNTIME_SLICE_STRUCTURED_VALUE_PATTERNS.items():
                if not pattern.search(slice_block):
                    result.issues.append(
                        ValidationIssue(
                            path,
                            "warning",
                            f"First runtime slice planning doc missing explicit {label}: value freeze",
                        )
                    )

    return result


def _mentions_first_runtime_slice(content: str) -> bool:
    """Return whether a document declares the first runtime slice."""
    lowered = content.lower()
    return any(marker.lower() in lowered for marker in FIRST_RUNTIME_SLICE_MARKERS)


def _is_first_runtime_slice_planning_doc(path: Path) -> bool:
    """Return whether a path is a planning doc that should freeze slice values."""
    normalized = path.as_posix().lower()
    return "docs/25-implementation/" in normalized and "plan" in path.name.lower()


def _first_runtime_slice_block(content: str) -> str:
    """Extract the closest markdown block for the first runtime slice."""
    heading_patterns = (
        re.compile(r"^#{2,6}\s+.*first runtime slice.*$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^#{2,6}\s+.*第一实施 slice.*$", re.MULTILINE),
    )
    start = None
    for pattern in heading_patterns:
        match = pattern.search(content)
        if match is not None:
            start = match.start()
            break

    if start is None:
        lowered = content.lower()
        start_positions = [
            lowered.rfind(marker.lower()) for marker in FIRST_RUNTIME_SLICE_MARKERS if marker.lower() in lowered
        ]
        if not start_positions:
            return content
        start = max(start_positions)

    line_end = content.find("\n", start)
    if line_end == -1:
        return content[start:]

    remaining = content[line_end + 1 :]
    next_heading = re.search(r"^#{2,6}\s+.+", remaining, re.MULTILINE)
    if next_heading is None:
        return content[start:]
    end = line_end + 1 + next_heading.start()
    return content[start:end]


def _validate_architecture_path_references(path: Path, ctx: AgentContextFile, content: str) -> list[ValidationIssue]:
    """Validate markdown file references for targeted architecture docs only."""
    if path.name not in ARCHITECTURE_PATH_VALIDATION_DOCS:
        return []

    validation_root = _find_validation_root(path)
    issues: list[ValidationIssue] = []
    seen_references: set[str] = set()

    for reference in _collect_architecture_markdown_references(ctx, content):
        normalized = reference.split("#", 1)[0].strip()
        if not normalized or normalized in seen_references:
            continue
        seen_references.add(normalized)
        resolved = _resolve_markdown_reference(path, validation_root, normalized)
        if not resolved.exists():
            issues.append(ValidationIssue(path, "error", f"Referenced path does not exist: {normalized}"))

    return issues


def _collect_architecture_markdown_references(ctx: AgentContextFile, content: str) -> list[str]:
    """Collect markdown-path references relevant to targeted architecture docs."""
    references: list[str] = []

    authority = ctx.frontmatter.get("Authority")
    if isinstance(authority, str) and authority.strip().endswith(".md"):
        references.append(authority.strip())

    references.extend(match.group(1) for match in MARKDOWN_LINK_REFERENCE_PATTERN.finditer(content))
    references.extend(match.group(1) for match in MARKDOWN_CODE_REFERENCE_PATTERN.finditer(content))
    return references


def _find_validation_root(path: Path) -> Path:
    """Best-effort repository root detection for markdown reference resolution."""
    current = path.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    for candidate in (current, *current.parents):
        if (candidate / "docs").is_dir() and (candidate / "ARCHITECTURE.md").exists():
            return candidate
    return current


def _resolve_markdown_reference(path: Path, root: Path, reference: str) -> Path:
    """Resolve a markdown reference relative to the doc or repository root."""
    reference_path = Path(reference)
    if reference_path.is_absolute():
        return reference_path

    if reference.startswith("./") or reference.startswith("../") or "/" not in reference:
        return (path.parent / reference_path).resolve(strict=False)

    if reference_path.parts and reference_path.parts[0] in REPO_ROOT_REFERENCE_PREFIXES:
        return (root / reference_path).resolve(strict=False)

    return (path.parent / reference_path).resolve(strict=False)


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------


def find_missing_contexts(root: Path) -> list[Path]:
    """Return a list of directories that should have AGENTS.md but don't.

    Only reports directories that actually exist on disk.
    """
    missing = []
    for rel_path in REQUIRED_AGENTS_DIRS:
        dir_path = root / rel_path
        agents_path = dir_path / "AGENTS.md"
        if dir_path.is_dir() and not agents_path.exists():
            missing.append(dir_path)
    return missing


def check_all_contexts(root: Path) -> dict[Path, ValidationResult]:
    """Validate every AGENTS.md found recursively under *root*.

    Hidden directories and ``__pycache__`` are skipped.
    """
    results: dict[Path, ValidationResult] = {}
    for agents_file in root.rglob("AGENTS.md"):
        # Skip hidden dirs and __pycache__
        if any(p.startswith(".") or p == "__pycache__" for p in agents_file.parts):
            continue
        results[agents_file] = validate_agents_file(agents_file)
    return results


# ---------------------------------------------------------------------------
# Compilation engine
# ---------------------------------------------------------------------------


@dataclass
class CompileResult:
    """Result of compiling one AGENTS.md file."""

    path: Path
    compiled_from: list[str]  # relative paths of child AGENTS.md files
    updated: bool  # whether the file was modified
    error: str | None = None


def _collect_child_agents(dir_path: Path, root: Path, visited: set[Path]) -> list[str]:
    """Return sorted list of relative paths to child AGENTS.md under *dir_path*.

    Skips hidden dirs, __pycache__, and already-visited paths to avoid cycles.
    """
    children: list[str] = []
    try:
        entries = sorted(dir_path.iterdir())
    except OSError:
        return children

    for entry in entries:
        if entry.name in (".", "..") or entry.name.startswith("."):
            continue
        agents = entry / "AGENTS.md"
        if agents.is_file() and agents not in visited:
            visited.add(agents)
            children.append(str(agents.relative_to(root)))
            # recurse into subdirs too
            if entry.is_dir():
                children.extend(_collect_child_agents(entry, root, visited))
    return children


def _read_frontmatter(content: str) -> dict[str, str]:
    """Parse minimal YAML frontmatter from markdown content."""
    fm: dict[str, str] = {}
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            for line in content[3:end].strip().splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    fm[k.strip()] = v.strip()
    return fm


def compile_agents_file(agents_path: Path, root: Path) -> CompileResult:
    """Compile an AGENTS.md: aggregate child AGENTS.md paths into Compiled-From.

    If the file's Compiled-From frontmatter already matches the current set of
    child AGENTS.md files, the file is left untouched.
    """
    if not agents_path.exists():
        return CompileResult(path=agents_path, compiled_from=[], updated=False, error="not found")

    content = agents_path.read_text(encoding="utf-8")
    fm = _read_frontmatter(content)

    visited: set[Path] = {agents_path}
    child_paths = _collect_child_agents(agents_path.parent, root, visited)
    # sort for stable ordering
    child_paths_sorted = sorted(child_paths)

    existing_raw = fm.get("Compiled-From", "").strip("[] ")
    existing_list = [p.strip() for p in existing_raw.split(",") if p.strip()] if existing_raw else []
    if sorted(existing_list) == child_paths_sorted:
        # Already up-to-date
        return CompileResult(path=agents_path, compiled_from=child_paths_sorted, updated=False)

    # Rebuild frontmatter block
    new_fm_lines = []
    for key in ["Type", "Layer", "Domain", "Status", "Authority"]:
        if key in fm:
            new_fm_lines.append(f"{key}: {fm[key]}")

    compiled_str = "[" + ", ".join(child_paths_sorted) + "]"
    new_fm_lines.append(f"Compiled-From: {compiled_str}")

    # Bump Updated
    from datetime import date

    new_fm_lines.append(f"Updated: {date.today().isoformat()}")

    new_fm = "---\n" + "\n".join(new_fm_lines) + "\n---\n"

    # Replace old frontmatter block (or prepend if none)
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            new_content = new_fm + content[end + 3 :]
        else:
            new_content = new_fm + content
    else:
        new_content = new_fm + content

    agents_path.write_text(new_content, encoding="utf-8")
    return CompileResult(path=agents_path, compiled_from=child_paths_sorted, updated=True)


def compile_all_contexts(root: Path) -> dict[Path, CompileResult]:
    """Compile every AGENTS.md under *root*, aggregating child paths into parents.

    Hidden directories and __pycache__ are skipped.
    Returns a map of file path -> compile result.
    """
    results: dict[Path, CompileResult] = {}
    for agents_file in sorted(root.rglob("AGENTS.md")):
        if any(p.startswith(".") or p == "__pycache__" for p in agents_file.parts):
            continue
        result = compile_agents_file(agents_file, root)
        results[agents_file] = result
    return results


# ---------------------------------------------------------------------------
# Pipeline step — integrates with D-Logos governance pipeline
# ---------------------------------------------------------------------------


class ContextCompileStep:
    """Pipeline step that compiles AGENTS.md files.

    Usage in a pipeline::

        from ontoderive.organs.context_compiler import ContextCompileStep

        step = ContextCompileStep()
        result = step.execute(context={"root": Path(".")}, progress={})
    """

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def execute(self, context: dict, progress: object) -> dict:
        """Run the compilation step and update *progress* in-place."""
        root = context.get("root", Path(__file__).parent.parent.parent.parent)
        start = time.time()
        results = compile_all_contexts(root)

        updated_count = sum(1 for r in results.values() if r.updated)
        elapsed = time.time() - start

        if self.dry_run:
            for r in results.values():
                if r.updated:
                    print(f"  [dry-run] would update {r.path.relative_to(root)}")

        result = {
            "step_name": "context_compile",
            "status": "completed",
            "start_time": start,
            "duration": elapsed,
            "output": {
                "total": len(results),
                "updated": updated_count,
                "skipped": len(results) - updated_count,
                "errors": [r.error for r in results.values() if r.error],
            },
            "items_processed": len(results),
        }

        if hasattr(progress, "completed"):
            progress.completed = len(results)
        elif isinstance(progress, dict):
            progress["completed"] = len(results)

        return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="AGENTS.md context compiler and validator")
    parser.add_argument(
        "--validate",
        metavar="PATH",
        help="Validate a single AGENTS.md file (accepts file or parent directory)",
    )
    parser.add_argument(
        "--find-missing",
        action="store_true",
        help="Find required directories that are missing AGENTS.md",
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Validate all AGENTS.md files discovered in the repo",
    )
    parser.add_argument(
        "--compile",
        metavar="ROOT",
        nargs="?",
        const=".",
        help="Compile all AGENTS.md files under ROOT (default: repo root)",
    )
    args = parser.parse_args()

    # Root is four levels up from this file: organs/D-Logos/organs/context_compiler.py
    root = Path(__file__).parent.parent.parent.parent  # → SharedBrain root

    if args.validate:
        path = Path(args.validate)
        if path.is_dir():
            path = path / "AGENTS.md"
        result = validate_agents_file(path)
        if result.is_valid:
            print(f"✅ {path}: valid ({result.warning_count} warnings)")
            for issue in result.issues:
                if issue.severity == "warning":
                    print(f"  ⚠️ {issue.message}")
        else:
            print(f"❌ {path}: {result.error_count} errors, {result.warning_count} warnings")
            for issue in result.issues:
                prefix = "  ❌" if issue.severity == "error" else "  ⚠️"
                print(f"{prefix} {issue.message}")
        sys.exit(0 if result.is_valid else 1)

    elif args.find_missing:
        missing = find_missing_contexts(root)
        if missing:
            print(f"⚠️  {len(missing)} directories missing AGENTS.md:")
            for p in missing:
                print(f"  - {p.relative_to(root)}")
        else:
            print("✅ All required directories have AGENTS.md")
        sys.exit(len(missing))

    elif args.check_all:
        results = check_all_contexts(root)
        total = len(results)
        errors = sum(1 for r in results.values() if not r.is_valid)
        print(f"\nAGENTS.md validation: {total} files checked, {errors} with errors\n")
        for path, result in sorted(results.items()):
            if not result.is_valid:
                rel = path.relative_to(root)
                print(f"❌ {rel}: {result.error_count} errors")
                for issue in result.issues:
                    if issue.severity == "error":
                        print(f"   • {issue.message}")
        sys.exit(1 if errors > 0 else 0)

    elif args.compile:
        compile_root = Path(args.compile)
        compile_results = compile_all_contexts(compile_root)
        updated = [r for r in compile_results.values() if r.updated]
        skipped = len(compile_results) - len(updated)
        print(f"\nAGENTS.md compilation ({compile_root}):")
        print(f"  Total: {len(compile_results)}  |  Updated: {len(updated)}  |  Skipped: {skipped}")
        for r in sorted(updated, key=lambda x: str(x.path)):
            print(f"  ✅ {r.path.relative_to(compile_root)}")
        for r in sorted(compile_results.values(), key=lambda x: str(x.path)):
            if r.error:
                print(f"  ❌ {r.path.relative_to(compile_root)}: {r.error}")
        sys.exit(0)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
